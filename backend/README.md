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
