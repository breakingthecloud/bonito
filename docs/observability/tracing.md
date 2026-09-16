# Tracing (OTLP / Tempo)

The collector emits **OpenTelemetry spans** (OTLP) so slow queries and lock
blocks are traceable end-to-end — a "Database APM" view.

## Enable

Set `BONITO_OTLP_ENDPOINT` to an OTLP (gRPC) endpoint. Without it, tracing
is a no-op.

```bash
export BONITO_OTLP_ENDPOINT=http://tempo:4317   # Tempo OTLP gRPC
bonito-collector
```

## Spans

| Span name | Attributes |
|-----------|------------|
| `query.<fingerprint>` | `query_text`, `mean_ms`, `max_ms`, `calls`, `rows`, `buffer_hit_ratio`, `db.instance` |
| `lock.blocking.<blocker>-><blocked>` | `wait_event`, `db.instance` |

## Tempo in the stack

`obs/tempo.yaml` configures Tempo (2.x) with OTLP gRPC on `:4317`. Grafana
gets a Tempo datasource for the **Traces / Drilldown** view.

### PITFALL — TraceQL metrics (`rate()`)

Grafana Traces' drilldown runs TraceQL metrics (`{...} | rate() by(...)`),
which requires Tempo's **metrics-generator** with the **`local-blocks`**
processor:

```yaml
overrides:
  metrics_generator_processors: ['service-graphs', 'span-metrics', 'local-blocks']
metrics_generator:
  traces_storage:
    path: /var/tempo/metrics-generator
```

Plus remote-write to Prometheus (`--web.enable-remote-write-receiver`).
Without `local-blocks` you get:
`failed to execute TraceQL query ... error finding generators in
Querier.queryRangeRecent: empty ring`.

!!! note
    `storage.trace.metrics_generator` does **not** exist in Tempo 2.x — it
    crashes config parsing. Configure the generator at top level + overrides.

## Verified

`{...} | rate() by(resource.service.name)` returns the `bonito-collector`
series, and Prometheus receives `traces_spanmetrics_*` (RED metrics) via
remote-write.