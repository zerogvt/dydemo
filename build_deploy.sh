set -eo pipefail

# Build the four component images locally and deploy them to the dydemo
# namespace. No registry is involved: the cluster is expected to see the local
# Docker daemon (Docker Desktop Kubernetes, or minikube after
# `eval $(minikube docker-env)`).
#
# Usage:
#   ./build_deploy.sh                    build fresh images and deploy them
#   ./build_deploy.sh --no-build         redeploy the newest images already built
#   ./build_deploy.sh --tag <tag>        redeploy one specific build

BUILD=1
TAG=""
NS=dydemo
SVCS="gateway backend jumpbox loadgen"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --no-build) BUILD=0 ;;
    --tag)      shift; TAG="$1"; BUILD=0 ;;
    -h|--help)  sed -n '8,11p' "$0"; exit 0 ;;
    *)          echo "Unknown option: $1" >&2; exit 1 ;;
  esac
  shift
done

echo "* * * Ensuring namespace ${NS} * * *"
# Created here rather than relying on the Namespace resource inside
# gateway/Deployment.yaml, so the components can be applied in any order.
kubectl create namespace "$NS" --dry-run=client -o yaml | kubectl apply -f -

if [ "$BUILD" -eq 1 ]; then
  echo "* * * Building * * *"
  TAG="$(date +%Y%m%d%H%M%S)"
  for svc in $SVCS; do
    docker build -t "dydemo.${svc}:${TAG}" "${svc}/"
  done
elif [ -z "$TAG" ]; then
  # Reuse the newest build. Only timestamp tags count, and only a tag present
  # on ALL components — a half-finished build would otherwise deploy a mix of
  # generations. Timestamps are fixed-width, so lexical order is chronological.
  want="$(echo $SVCS | wc -w)"
  TAG="$(for svc in $SVCS; do
           docker images "dydemo.${svc}" --format '{{.Tag}}' | grep -E '^[0-9]{14}$' | sort -u
         done | sort | uniq -c | awk -v n="$want" '$1 == n {print $2}' | sort -r | head -1)"
  if [ -z "$TAG" ]; then
    echo "No build found covering all of: $SVCS" >&2
    echo "Run without --no-build to build them, or pass --tag <tag>." >&2
    exit 1
  fi
  echo "* * * Reusing newest build ${TAG} * * *"
else
  for svc in $SVCS; do
    if ! docker image inspect "dydemo.${svc}:${TAG}" >/dev/null 2>&1; then
      echo "Image dydemo.${svc}:${TAG} not found locally" >&2
      exit 1
    fi
  done
  echo "* * * Reusing build ${TAG} * * *"
fi

# Deploy each component with $TAG applied by a Kustomize overlay generated
# fresh in a temp dir. This is what guarantees a fresh image actually gets
# picked up: the tag changes every build, so the Deployment's pod template
# changes and Kubernetes rolls the pods. (With a stable tag plus
# imagePullPolicy: IfNotPresent, a rebuilt image is silently ignored.)
# None of the checked-in yamls are modified — only the throwaway overlay
# carries the tag. --load-restrictor is needed because the overlay's resource
# path points back into the repo, outside the temp dir Kustomize treats as its
# root.
echo "* * * Deploying ${TAG} * * *"
for svc in $SVCS; do
  tmp="$(mktemp -d)"
  cat > "${tmp}/kustomization.yaml" <<EOF
resources:
  - $(pwd)/${svc}/Deployment.yaml
images:
  - name: dydemo.${svc}
    newTag: "${TAG}"
EOF
  kubectl kustomize --load-restrictor LoadRestrictionsNone "${tmp}" | kubectl apply -f -
  rm -rf "${tmp}"
done

echo "* * * Waiting for rollout * * *"
for svc in $SVCS; do
  case "$svc" in
    jumpbox) dep="jumpbox-curl" ;;
    *)       dep="dydemo-${svc}" ;;
  esac
  kubectl rollout status "deployment/${dep}" -n "$NS" --timeout=3m
done

kubectl get pods -n "$NS"
