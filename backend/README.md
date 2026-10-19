Holds every endpoint of the demo; the [gateway](../gateway/) in front of it
only forwards requests. Every log line carries the call's `X-Request-ID`
(taken from the request, or generated if it came in without one), and every
response returns it.

## Build and Deploy

Normally you deploy all three components together, from the repo root:

`bash ../build_deploy.sh`

That builds `dydemo.backend` locally with a timestamp tag and applies it via a
Kustomize overlay. To build just this image by hand:

`docker build . -t dydemo.backend:$(date +%Y%m%d%H%M%S)`

Note that `kubectl apply -f Deployment.yaml` on its own deploys the *untagged*
image name, i.e. `:latest`, which won't exist locally — use the script.


## Run dev server
`. ../venv/bin/activate`
`env FLASK_APP=backend.py python -m flask run`

## Tests

`python -m unittest` from this directory.

## Endpoints

Each one simulates a different failure mode, for generating observability
signals. The full contract is in [openapi.yaml](../openapi.yaml).

| Endpoint | Behaviour |
|----------|-----------|
| `/` | 200 |
| `/server_error` | 500, always |
| `/client_error` | 400, always |
| `/latency` | 200, with a p90 of 2s and a p99 of 5s |
| `/blowup` | 200, but a 30% chance of killing the worker via `os._exit(1)`; the gateway then answers 502. (`sys.exit` would not do it: gunicorn catches it and answers 500.) |
| `/transaction` | 201, JSON with a new `transaction_id` and the call's `request_id`; GET or POST |
