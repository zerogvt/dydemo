## Build and Deploy
`docker build . -t regga-h6e5btbnffaee8c7.azurecr.io/dydemo.backend`
`docker push regga-h6e5btbnffaee8c7.azurecr.io/dydemo.backend` 
`kubectl delete -f Deployment.yaml && kubectl apply -f Deployment.yaml`


## Run dev server
`. ../venv/bin/activate`
`env FLASK_APP=backend.py python -m flask run`
