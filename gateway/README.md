## Build and deploy

Normally you deploy all three components together, from the repo root:

`bash ../build_deploy.sh`

That builds `dydemo.gateway` locally with a timestamp tag and applies it via a
Kustomize overlay. To build just this image by hand:

`docker build . -t dydemo.gateway:$(date +%Y%m%d%H%M%S)`

Note that `kubectl apply -f Deployment.yaml` on its own deploys the *untagged*
image name, i.e. `:latest`, which won't exist locally — use the script.


## Configuration

Both settings are read from the environment, so the same image runs in-cluster
and locally. `Deployment.yaml` sets `BACKEND_URL` explicitly.

| Variable | Default | Purpose |
|----------|---------|---------|
| `BACKEND_URL` | `http://dydemo-backend-service/` | Where `/transaction` forwards to. Namespace-relative, so it resolves via the pod's DNS search path and survives a namespace change. |
| `BACKEND_TIMEOUT` | `5` | Seconds to wait on the backend. `/transaction` returns 504 on timeout, 502 if the backend is unreachable. |

Change one without rebuilding:
`kubectl set env deployment/dydemo-gateway -n dydemo BACKEND_TIMEOUT=1`


## Run dev server

Needs the backend running too, otherwise `/transaction` returns 502.

Backend, in one shell:
`. ../venv/bin/activate`
`cd ../backend && env FLASK_APP=backend.py python -m flask run --port 5000`

Gateway, in another:
`. ../venv/bin/activate`
`env FLASK_APP=gateway.py BACKEND_URL=http://127.0.0.1:5000/ python -m flask run --port 8000`


## Endpoints

Each one simulates a different failure mode, for generating observability
signals:

| Endpoint | Behaviour |
|----------|-----------|
| `/` | 200 |
| `/server_error` | 500, always |
| `/client_error` | 400, always |
| `/latency` | 200, with a p90 of 2s and a p99 of 5s |
| `/blowup` | 200, but a 30% chance of killing the worker via `sys.exit(1)` |
| `/transaction` | POSTs a UUID to the backend and relays its 201 — the one endpoint that crosses a service boundary |
