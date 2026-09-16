# Grafana "Deep DB View"

The demo tenant ships a provisioned Grafana dashboard (folder *Bonito*)
that turns the `bonito_*` metrics into a DBA view: **stats, top queries,
blocking, waits, bloat and anomaly**, with per-instance series.

Dashboard source: `deploy/cloud/lightsail/obs/grafana/provisioning/dashboards/bonito.json`
(live at `grafana-demo.sofe.dev`).

## Panels (v3 — 19 panels)

| Panel | Source metric |
|-------|---------------|
| Active sessions | `bonito_active_sessions` |
| Blocking sessions | `bonito_blocking_sessions` |
| Idle-in-transaction | `bonito_idle_in_transaction` |
| VM CPU / MEM | `node-exporter` |
| Scrape duration / errors | `bonito_collector_scrape_duration_seconds`, `bonito_collector_errors_total` |
| Top queries — mean ms (bar gauge) | `bonito_query_mean_ms` |
| Top queries — calls | `bonito_query_calls` |
| Buffer hit ratio | `bonito_query_buffer_hit_ratio` |
| Seq-scan detector (→ CREATE INDEX) | `bonito_table_seq_scan` |
| Live / dead rows | `bonito_table_live_rows`, `bonito_table_dead_rows` |
| Query mean over time | `bonito_query_mean_ms` |
| **Query regression % (anomaly)** | `bonito_query_regression_pct` |
| **Anomaly flag** | `bonito_query_anomaly` |
| Active sessions by instance | `bonito_sessions_by_state` (per `db_instance`) |
| Wait breakdown | `bonito_wait_events_total` |
| Table bloat | `bonito_table_bloat_pct` |

## Provisioning

Datasources and dashboards are provisioned from
`obs/grafana/provisioning/`. The Prometheus datasource is referenced **by
type, without a hardcoded UID** — a hardcoded UID caused a "data source not
found" race on first boot.

## Tempo (traces)

The same Grafana instance exposes a **Tempo** datasource for trace-level
drilldown. Grafana Traces (TraceQL metrics) needs Tempo's
**metrics-generator** with the `local-blocks` processor enabled — see
[tracing](tracing.md).