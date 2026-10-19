## Continuous load generator

Alpine + curl, walking every endpoint the gateway exposes in a loop at roughly
one request per second. Deployed along with the other components by the root
build script: `bash ../build_deploy.sh`.

This exists because most of what makes the demo interesting only shows up under
*sustained* traffic. A one-off burst gives you a single spike; percentiles,
error rates, Davis baselining and anomaly detection all need a steady baseline
to measure against.

### What it does

Cycles through the six gateway paths in order, one request at a time:

```
/  →  /client_error  →  /server_error  →  /latency  →  /blowup  →  /transaction
```

Each request is logged with its status code, duration and the `X-Request-ID`
the gateway returned, so `kubectl logs` doubles as a quick check that the
system is behaving as advertised, and any line can be followed into the
gateway's and backend's logs by its `request_id`:

```bash
kubectl logs -n dydemo deployment/dydemo-loadgen -f
```

```
2026-10-19T12:16:02Z / -> 200 (0s) request_id=572d12a04d8148719e62d98523a33eed
2026-10-19T12:16:03Z /client_error -> 400 (0s) request_id=bf8cf46a3d7c4008a886e280c299ff3a
2026-10-19T12:16:04Z /server_error -> 500 (0s) request_id=c6a94da57bb740dcae57be2299654c8d
2026-10-19T12:16:07Z /latency -> 200 (2s) request_id=ef73b46d8bad4ec2b5a128072bcae553
2026-10-19T12:16:08Z /blowup -> 502 (0s) request_id=6be2f243a82b4b3d81b0b72509c88dd3
2026-10-19T12:16:09Z /transaction -> 201 (0s) request_id=c903b01a13e945d89b1ff35757d42da4
```

A `502` from `/blowup` means the backend worker handling that request was
killed, which is exactly the signal that endpoint exists to produce; the
gateway answers 502 for the dropped connection. A `000` with `request_id=-`
means curl got no response at all, i.e. the gateway itself was unreachable.

### Configuration

All via env in [Deployment.yaml](Deployment.yaml), so the same image can be
retuned without a rebuild:

| Variable | Default | Purpose |
|----------|---------|---------|
| `GATEWAY_URL` | `http://dydemo-gateway-service` | Where to send requests. Namespace-relative, so it resolves in whichever namespace this lands. |
| `INTERVAL` | `1` | Target **seconds per request**. |
| `PATHS` | all six | Space-separated list to cycle through. |
| `MAX_TIME` | `10` | curl timeout. Must stay above `/latency`'s 5s worst case, or you'd truncate the very tail you want to observe. |

### On the actual rate

`INTERVAL` is a target period, not an added delay: the loop measures how long
each request took and sleeps only the remainder. So a fast 200 sleeps ~1s, and
a `/latency` response that blocked for 2s sleeps not at all and moves straight
on. The result holds close to one request per second overall rather than
drifting slower as request times vary.

It can't hold exactly 1/sec when a request outruns the interval — `/latency`
returns 5s responses 1% of the time, and the loop simply proceeds late rather
than trying to catch up. Over a full cycle that costs a fraction of a second.

### Turning it down

To pause the load without deleting anything:

```bash
kubectl scale deployment/dydemo-loadgen -n dydemo --replicas=0
```

To stop only the crash traffic, drop `/blowup` from `PATHS` in
[Deployment.yaml](Deployment.yaml) and re-apply. At one request per second the
whole cycle repeats every ~6s, so `/blowup`'s 30% crash rate kills a worker
roughly every 20 seconds — deliberate, but disruptive if you're trying to
demonstrate something else at the time.

### Why not the jumpbox?

[jumpbox/](../jumpbox/) is for interactive poking — exec in and run whatever
you want by hand. This runs unattended, which is what the observability half of
the demo needs.
