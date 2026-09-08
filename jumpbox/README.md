## Utility pod that allows easy troubleshooting and testing.

Deployed along with the other components by the root build script:
`bash ../build_deploy.sh`

Get pod name:
`kubectl get po ....`

Then connect to it:
`kubectl exec -n dydemo -it deployment-curl-5b7c9798b4-mgbr6 -- sh`

Run requests to gateway service in a loop:
`/app # while true; do curl  dydemo-gateway-service/latency; done`
