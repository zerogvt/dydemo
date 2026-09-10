# dydemo

A deliberately misbehaving system on Kubernetes, used as a demo and test bed
for Dynatrace observability.

The point isn't the app — it's the signals. Every endpoint simulates a
different failure mode (errors, latency tails, crashes, a cross-service call)
so there is something real to detect, alert on, and trace. Instrumentation is
agent-injected by the Dynatrace Operator; there is no OpenTelemetry SDK or
tracing code in the app itself.

## Architecture

```
                  ┌──────────────┐        ┌──────────────┐
  you ────────────▶   gateway     ───────▶    backend   │
  (NodePort :80)  │  (Flask,     │  POST  │   (Flask,    │
                  │   :5000)     │  JSON  │    :5000)    │
                  └──────────────┘        └──────────────┘
                     ▲          ▲
       1 req/sec ────┘          └──── curl, by hand
                     │          │
              ┌──────────────┐  ┌──────────────┐
              │   loadgen    │  │   jumpbox    │
              └──────────────┘  └──────────────┘

  all in namespace `dydemo`; the Operator injects OneAgent into these pods
```

## Components

| Component | What it is | Role |
|-----------|------------|------|
| [gateway/](gateway/) | Flask + gunicorn (2 workers) | The interesting one. Every endpoint is a different failure mode. Entry point via NodePort. |
| [backend/](backend/) | Flask + gunicorn (2 workers) | A POST-only JSON echo. Exists so `/transaction` produces a two-service distributed trace. |
| [loadgen/](loadgen/) | Alpine + curl | Walks every gateway endpoint in a loop at ~1 req/sec, unattended. Sustained traffic is what makes percentiles, error rates and baselining meaningful. |
| [jumpbox/](jumpbox/) | Alpine + curl | Utility pod for poking the services by hand from inside the cluster. |
| [dynakube.yaml](dynakube.yaml) | Secret + DynaKube CR + RBAC | **The live Dynatrace config.** App-only OneAgent injection into `dydemo`, log monitoring, KSPM, and a single ActiveGate holding both `kubernetes-monitoring` and `routing`. References the token Secret by name only, so it holds no credentials itself. See [Install Dynatrace](#3-install-dynatrace). |
| `dynatrace-tokens.yaml` | Secret | Your `apiToken` and `dataIngestToken`. **Gitignored** — not in this repo; create it yourself, see [Install Dynatrace](#3-install-dynatrace). |
| [dashboards/](dashboards/) | Exported dashboard JSON | Throughput, latency and error dashboards for the `dydemo` services, ready to upload through the Dynatrace UI. |

## The endpoints

All on the gateway. This table is the whole purpose of the project:

| Endpoint | Behaviour | Signal it produces |
|----------|-----------|--------------------|
| `/` | 200 | Baseline / control |
| `/server_error` | 500, always | Server-side failure rate |
| `/client_error` | 400, always | Client-side failure rate |
| `/latency` | 200, p90 of 2s and p99 of 5s | A response-time *tail*, not uniform slowness — what makes percentiles and baselining interesting |
| `/blowup` | 200, but 30% chance of `sys.exit(1)` | Real worker death, pod restarts, dropped connections |
| `/transaction` | POSTs a UUID to the backend, relays its 201 | A distributed trace crossing a service boundary |

`/transaction` also returns 504 if the backend times out and 502 if it's
unreachable — see [gateway/README.md](gateway/README.md) for its config.

## Prerequisites

- A local Kubernetes cluster — Docker Desktop or minikube.
- Docker, with the cluster sharing the local daemon — no registry is involved.
  That's the case on Docker Desktop Kubernetes; on minikube, run
  `eval $(minikube docker-env)` first so the images land where the cluster can
  see them.
- `kubectl` with Kustomize support (built in since v1.14).
- `helm` 3.8 or newer (for OCI registry support), to install the Dynatrace
  Operator.
- A Dynatrace tenant, if you want the observability half.

## How to run

### 1. Build and deploy

```bash
bash build_deploy.sh
```

[build_deploy.sh](build_deploy.sh) builds all four images locally, tags them
with a timestamp, and applies them to the `dydemo` namespace through a
throwaway Kustomize overlay. The timestamp tag is the point: it changes on
every build, so the pod template changes and Kubernetes actually rolls the
pods. A stable tag plus `imagePullPolicy: IfNotPresent` would silently keep
running the old image. The checked-in `Deployment.yaml` files stay untagged and
are never modified by a deploy — only the temp overlay carries the tag.

To redeploy the images you already built, without rebuilding:

```bash
bash build_deploy.sh --no-build          # newest build present for all four
bash build_deploy.sh --tag 20260907162543  # one specific build
```

`--no-build` only considers a tag that exists for *all four* components, so a
half-finished build can't deploy a mix of generations.

### 2. Generate traffic

[loadgen/](loadgen/) is deployed by the build script and starts on its own, so
there is nothing to do here — it walks all six gateway endpoints in a loop at
about one request per second, indefinitely. Watch it:

```bash
kubectl logs -n dydemo deployment/dydemo-loadgen -f
```

That steady baseline is the point: percentiles, error rates and Davis
baselining need sustained traffic to measure against, not a one-off burst.

To pause it, or to stop only the crash traffic:

```bash
kubectl scale deployment/dydemo-loadgen -n dydemo --replicas=0
# or drop /blowup from PATHS in loadgen/Deployment.yaml and re-apply
```

For driving one failure mode by hand, exec into the jumpbox instead:

```bash
kubectl exec -n dydemo -it deployment/jumpbox-curl -- sh

# inside the pod:
while true; do curl -s dydemo-gateway-service/latency; done
while true; do curl -s dydemo-gateway-service/transaction; done
while true; do curl -s dydemo-gateway-service/blowup; done
```

Watch the crash-and-restart behaviour that `/blowup` causes with:

```bash
kubectl get pods -n dydemo -w
```

### 3. Install Dynatrace

Two steps: the Operator via Helm, then the DynaKube that tells it what to
monitor.

```bash
helm install dynatrace-operator \
  oci://public.ecr.aws/dynatrace/dynatrace-operator \
  --create-namespace --namespace dynatrace --atomic
```

That brings up the Operator, both admission webhooks, and the CSI driver.
`--atomic` waits for them to be ready and rolls back if they aren't.

Next the tokens, then the DynaKube. They are two separate files, applied in
that order:

```bash
kubectl apply -f dynatrace-tokens.yaml   # the Secret
kubectl apply -f dynakube.yaml           # the DynaKube
```

`dynatrace-tokens.yaml` holds your credentials and is **gitignored** — it is
not in this repository, so create it yourself. The easiest way is to let
`kubectl` generate it:

```bash
kubectl create secret generic dydemo -n dynatrace \
  --from-literal=apiToken='dt0c01....' \
  --from-literal=dataIngestToken='dt0c01....' \
  --dry-run=client -o yaml > dynatrace-tokens.yaml
```
Use k8s app in your dynatrace tenant to [create these tokens](https://docs.dynatrace.com/docs/ingest-from/setup-on-k8s/quickstart). 

Two constraints on that Secret: its name must match `spec.tokens` in
`dynakube.yaml` (`dydemo`), and it must exist **before** the DynaKube is
applied — the DynaKube never comes up otherwise. `dynakube.yaml` only
references it by name, which is why that file carries no credentials and is
safe to commit.

`dataIngestToken` is only needed if you're ingesting metrics or events;
`apiToken` alone is enough for the rest.

Finally, restart the app — pods created before the Operator was installed have
no agent, and only get injected when they're recreated:

```bash
kubectl rollout restart deployment -n dydemo
kubectl get dynakube -n dynatrace          # want STATUS: Running
kubectl get pods -n dynatrace              # ActiveGate should be 1/1, 0 restarts
```

What to change for your own environment:

- **`apiUrl`** — your tenant, including the trailing `/api`.
- **`networkZone`** — `dydemo` as written. It shows up in your tenant once the
  ActiveGate registers with that name.
- **`activeGate.resources`** — sized for a laptop: 512Mi request, 1.5Gi limit.
  Keep the *CPU* limit generous. ActiveGate startup runs a series of
  short-lived JVMs (`agctl`), and throttling it below roughly one core stretches
  startup past the liveness probe's ~150s budget, which crashloops the pod with
  `exit 143` and no OOM in sight.

A single ActiveGate carries both roles (again due to being sized for a small laptop):

```yaml
  activeGate:
    capabilities:
      - kubernetes-monitoring   # polls the K8s API: topology, events, KSPM
      - routing                 # the data path injected OneAgents report to
```

Splitting those across two DynaKubes only pays off when the agent-facing tier (routing)
needs to scale independently; on one node it just doubles the footprint. 

Teardown:

```bash
kubectl delete -f dynakube.yaml
helm uninstall dynatrace-operator -n dynatrace
```

`helm uninstall` deliberately leaves the CRDs in place; a later reinstall
adopts them rather than failing on them.

### 4. Import the dashboards

[dashboards/](dashboards/) holds exported dashboard definitions. In the
Dynatrace **Dashboards** app, use **Upload** and pick
`dashboards/dydemo-throughput-latency-errors.json` — throughput, latency and
errors for both `dydemo` services, broken down per endpoint.

The tiles stay empty until the Operator is injecting *and* traffic is flowing,
so do this after step 3. See [dashboards/README.md](dashboards/README.md) for
what the dashboard assumes and how to point it at a different namespace.

## Running locally, without Kubernetes

Useful for changing app behaviour without a build-push-deploy cycle. Both
services are plain Flask apps; the gateway finds the backend via `BACKEND_URL`:

```bash
# shell 1
. venv/bin/activate
cd backend && env FLASK_APP=backend.py python -m flask run --port 5000

# shell 2
. venv/bin/activate
cd gateway && env FLASK_APP=gateway.py BACKEND_URL=http://127.0.0.1:5000/ \
  python -m flask run --port 8000
```

Then `curl localhost:8000/transaction`.

## Notes

- To restart the pods without any rebuild — e.g. after editing a ConfigMap —
  use `kubectl rollout restart deployment -n dydemo`. Don't `kubectl apply -f`
  the checked-in yamls to force it: they carry untagged images, so an apply
  would rewrite the live Deployment from `dydemo.gateway:20260907162543` back
  to `:latest`, which doesn't exist locally, and the pods would land in
  `ErrImagePull`.
- Both Services are `NodePort`. `port-forward` is usually easier:
  `kubectl port-forward -n dydemo service/dydemo-gateway-service 8080:80`.

