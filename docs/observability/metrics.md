# Prometheus metrics

Every collector run exports **numeric gauges** to `:9187/metrics`
(`BONITO_PROM_PORT`). The store exposes its anomaly metrics on `:8000/metrics`.
All metrics carry a `db_instance` label (BON-013 multi-instance).

## Collector metrics (`bonito-collector` :9187)

### Per top query (labels: `fingerprint`, `db_instance`)

| Metric | Meaning |
|--------|---------|
| `bonito_query_mean_ms` | Mean execution time (ms) per top query |
| `bonito_query_calls` | Total calls per top query |
| `bonito_query_max_ms` | Max execution time (ms) per top query |
| `bonito_query_rows` | Total rows returned per top query |
| `bonito_query_buffer_hit_ratio` | Buffer hit ratio (0–100) per top query |

### Sessions / waits (labels: `db_instance`)

| Metric | Meaning |
|--------|---------|
| `bonito_blocking_sessions` | Number of blocking session pairs |
| `bonito_active_sessions` | Active (non-idle) sessions |
| `bonito_sessions_by_state{state}` | Sessions by state |
| `bonito_wait_events_total{type}` | Sessions waiting by event type |
| `bonito_idle_in_transaction` | Idle-in-transaction sessions |

### Per table (labels: `table`, `db_instance`)

| Metric | Meaning |
|--------|---------|
| `bonito_table_bloat_pct` | Dead-tuple bloat percentage |
| `bonito_table_live_rows` | Live rows |
| `bonito_table_dead_rows` | Dead rows |
| `bonito_table_seq_scan` | Sequential scans |
| `bonito_table_idx_scan` | Index scans |

### Collector health

| Metric | Meaning |
|--------|---------|
| `bonito_collector_scrape_duration_seconds` | Seconds per collector run |
| `bonito_collector_errors_total` | Collector loop errors (counter) |

## Store metrics (`bonito-store` :8000/metrics) — anomaly engine

| Metric | Labels | Meaning |
|--------|--------|---------|
| `bonito_query_regression_pct` | `fingerprint` | Regression % vs 7-day baseline |
| `bonito_query_anomaly` | `fingerprint` | Anomaly flag (1 = regression) |

Example:

```text
# HELP bonito_query_mean_ms Mean execution time per top query (ms)
# TYPE bonito_query_mean_ms gauge
bonito_query_mean_ms{fingerprint="1978432790045853480",db_instance="app"} 299467.79
bonito_blocking_sessions{db_instance="app"} 1.0
bonito_query_anomaly{fingerprint="sim-regression-001"} 1.0
bonito_query_regression_pct{fingerprint="sim-regression-001"} 1100.0
```

## Scraping

```yaml
scrape_configs:
  - job_name: bonito-collector
    static_configs:
      - targets: ['bonito-collector:9187']
        labels: { instance: my-db-host }
  - job_name: bonito-store
    static_configs:
      - targets: ['bonito-store:8000']
        labels: { instance: my-db-host }
```

## Alerting on these metrics

Pair these with the bundled [alert rules](alerting.md) — blocking,
idle-in-transaction, slow queries, regressions and collector down — and route
them to Remo for AI triage.