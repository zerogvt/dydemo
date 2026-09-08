#!/bin/sh
# Walks every endpoint the gateway exposes, in a loop, at a steady rate.
#
# The point is a continuous, predictable baseline: percentiles, error rates and
# baselining in Dynatrace only mean something against sustained traffic, not a
# one-off burst. One request per second is enough to keep every signal alive
# without generating noise.
#
# Everything is overridable so the same image can be pointed elsewhere or
# retuned without a rebuild:
#   GATEWAY_URL  where to send requests
#   INTERVAL     target seconds per request (the loop self-corrects, see below)
#   PATHS        space-separated list of paths to cycle through
#   MAX_TIME     curl timeout; must exceed /latency's 5s worst case
set -u

GATEWAY_URL="${GATEWAY_URL:-http://dydemo-gateway-service}"
INTERVAL="${INTERVAL:-1}"
PATHS="${PATHS:-/ /client_error /server_error /latency /blowup /transaction}"
MAX_TIME="${MAX_TIME:-10}"

echo "loadgen: target=${GATEWAY_URL} interval=${INTERVAL}s max_time=${MAX_TIME}s"
echo "loadgen: paths=${PATHS}"

# Wait for the gateway before starting. On a cold deploy all four pods come up
# together, so without this the first cycle is just connection failures - which
# would show up in Dynatrace as a spike of real errors that nothing caused.
until curl -s -o /dev/null --max-time 5 "${GATEWAY_URL}/"; do
  echo "loadgen: waiting for ${GATEWAY_URL} ..."
  sleep 2
done
echo "loadgen: gateway is up, starting loop"

while true; do
  for p in $PATHS; do
    start="$(date +%s)"

    # 000 means curl never got a response - connection refused or reset. That
    # is a real signal here, not a script bug: /blowup kills a gunicorn worker
    # outright, so in-flight requests get dropped.
    code="$(curl -s -o /dev/null --max-time "${MAX_TIME}" -w '%{http_code}' "${GATEWAY_URL}${p}")"

    elapsed="$(( $(date +%s) - start ))"
    echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') ${p} -> ${code} (${elapsed}s)"

    # Sleep only the remainder of INTERVAL, so the loop holds ~1 request/sec
    # overall instead of 1/sec *plus* however long each request took. When a
    # request outruns the interval - /latency's deliberate 2s and 5s tails - we
    # simply move on rather than falling further behind.
    rest="$(( INTERVAL - elapsed ))"
    if [ "${rest}" -gt 0 ]; then
      sleep "${rest}"
    fi
  done
done
