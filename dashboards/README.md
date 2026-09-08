## Dynatrace dashboards

Exported dashboard definitions, checked in so they can be recreated in any
tenant without rebuilding them by hand.

| File | Dashboard |
|------|-----------|
| [dydemo-throughput-latency-errors.json](dydemo-throughput-latency-errors.json) | Throughput, latency and errors for the `gateway` and `backend` services in namespace `dydemo`. |

### Uploading through the UI

1. Open the **Dashboards** app in your Dynatrace environment.
2. Use **Upload** (top right, next to *Create dashboard*) and pick the `.json`
   file.
3. The new dashboard takes its name from the filename, so rename it afterwards
   if you want the original — `dydemo. Throughput, Latency & Errors`.

The file is the dashboard *content* document — `version`, `tiles`, `layouts`,
`variables`, `settings` — which is exactly what the UI's own export produces,
so it round-trips: upload, edit in the UI, export, and commit the result back
here.

It is pretty-printed rather than minified on purpose. A tile is a DQL query
plus a visualisation type, and those are worth reviewing in a diff when
somebody changes one.

### What you need for it to show data

- **Dynatrace monitoring the `dydemo` namespace.** Every tile is scoped with
  `filter: { k8s.namespace.name == "dydemo" }`, so nothing renders until the
  Operator is installed and injecting. See
  [Install Dynatrace](../README.md#3-install-dynatrace).
- **Traffic.** Dynatrace only detects a service once it handles a request, and
  percentiles need a continuous baseline. [loadgen/](../loadgen/) provides it
  at ~1 request/sec and starts on its own.

### Two things about this dashboard that aren't obvious

**Why it filters on namespace and not service name.** OneAgent names these
services `gateway` and `backend` — not `dydemo-gateway`. Those are generic
enough to collide with anything else in the tenant, so the tiles scope on
`k8s.namespace.name` instead, which is a real dimension on
`dt.service.request.*` once metadata enrichment is active. It also survives a
service being renamed or re-detected.

**Why there is a separate "4xx responses" tile.** Dynatrace counts only
server-side failures in `dt.service.request.failure_count`. The `/client_error`
endpoint returns HTTP 400 every time, and it shows up as `0 failures` and a
`0%` error rate — correctly, by that definition. Without the dedicated 4xx tile
the dashboard would look clean while a sixth of the traffic was erroring. The
`/server_error` endpoint, returning 500, does register as 100% failures.

### Adapting it to another namespace

Search and replace `dydemo` in the query strings. If you also renamed the
endpoints, note that `endpoint.name` here is method-prefixed (`GET /latency`),
which is how OneAgent reports it — an OpenTelemetry-instrumented service would
report a bare `/latency` instead.
