## Build and deploy

`docker build . -t regga-h6e5btbnffaee8c7.azurecr.io/dydemo.gateway`
`docker push regga-h6e5btbnffaee8c7.azurecr.io/dydemo.gateway`
`kubectl delete -f Deployment.yaml && kubectl apply -f Deployment.yaml`


## Run dev server
`. ../venv/bin/activate`
`env FLASK_APP=gateway.py python -m flask run --port 8000`
