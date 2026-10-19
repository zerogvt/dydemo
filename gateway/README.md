A plain reverse proxy in front of the backend, where all the endpoints live.
Each backend endpoint has its own route here that forwards the request
unchanged and relays the backend's answer, so every call is a two-service
distributed trace.

The routes are deliberately one per endpoint, not a single catch-all:
OneAgent names a request after its Flask route rule, so a `/<path:path>` route
would put every call under one endpoint in Dynatrace. The cost is that a new
backend endpoint needs a matching route in `gateway.py`; until it has one, the
gateway answers 404 for it.

The gateway adds only two things of its own:

- **`X-Request-ID`**: kept from the caller or generated, forwarded to the
  backend, returned in the response, and printed in every log line.
- **502 / 504**: when the backend is unreachable (including when `/blowup`
  kills a backend worker mid-request) or slower than `BACKEND_TIMEOUT`.

It runs gunicorn with threaded workers (`gthread`, 2 x 8 threads), because it
spends its time waiting on the backend: with plain sync workers, two slow
`/latency` calls would block every other request.

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
| `BACKEND_URL` | `http://dydemo-backend-service/` | Where every request is forwarded to. Namespace-relative, so it resolves via the pod's DNS search path and survives a namespace change. |
| `BACKEND_TIMEOUT` | `8` | Seconds to wait on the backend before answering 504; 502 if the backend is unreachable. Keep it above the backend's 5s `/latency` tail and below loadgen's 10s `MAX_TIME`. |

Change one without rebuilding:
`kubectl set env deployment/dydemo-gateway -n dydemo BACKEND_TIMEOUT=1`


## Run dev server

Needs the backend running too, otherwise every request returns 502.

Backend, in one shell:
`. ../venv/bin/activate`
`cd ../backend && env FLASK_APP=backend.py python -m flask run --port 5000`

Gateway, in another:
`. ../venv/bin/activate`
`env FLASK_APP=gateway.py BACKEND_URL=http://127.0.0.1:5000/ python -m flask run --port 8000`


## Tests

`python -m unittest` from this directory. The backend is mocked, so they run
on their own.

## Endpoints

The backend's, one route each: see [backend/README.md](../backend/README.md)
and [openapi.yaml](../openapi.yaml).
