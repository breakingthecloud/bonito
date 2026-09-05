# Bonito v0.1.0 — Metrics & Events

Every collector run produces **two** outputs (BON-001 deliverable 7):

1. **Prometheus gauges** — scraped at `http://localhost:9187/metrics`
2. **Structured JSON events** — POSTed to `BONITO_STORE_URL/events` (if set)

## Prometheus metrics

| Metric | Type | Labels | Meaning |
|--------|:----:|--------|---------|
| `bonito_query_mean_ms` | Gauge | `fingerprint` | Mean execution time (ms) per top query |
| `bonito_blocking_sessions` | Gauge | — | Number of blocking session pairs |
| `bonito_active_sessions` | Gauge | — | Active (non-idle) sessions |
| `bonito_table_bloat_pct` | Gauge | `table` (`schema.table`) | Dead-tuple bloat percentage |

Gauges are kept low-cardinality (`fingerprint`, `table` only). Top 20 of each
collector are exported.

```text
# HELP bonito_query_mean_ms Mean execution time per top query (ms)
# TYPE bonito_query_mean_ms gauge
bonito_query_mean_ms{fingerprint="-6842865755026457642"} 12.43
bonito_blocking_sessions 0.0
bonito_active_sessions 3.0
bonito_table_bloat_pct{table="public.orders"} 4.2
```

## JSON events (one snapshot)

`bonito-collector --once` prints the same payload it would push. Shape:

```json
{
  "collected_at": "2026-09-04T02:10:00+00:00",
  "top_queries":  [ { "...": "..." } ],
  "locks":        [ { "...": "..." } ],
  "sessions":     [ { "...": "..." } ],
  "tables":       [ { "...": "..." } ]
}
```

See `examples/events.sample.json` for a fully-populated example.

### Top queries (`pg_stat_statements`)

```json
{
  "fingerprint": "-6842865755026457642",
  "calls": 1284,
  "total_ms": 15932.11,
  "mean_ms": 12.43,
  "max_ms": 841.02,
  "rows": 245680,
  "buffer_hit_ratio": 99.2,
  "query": "SELECT * FROM orders WHERE customer_id = $1"
}
```

### Locks / blocking tree (`pg_locks` + `pg_blocking_pids`)

```json
{
  "blocked_pid": 1412,
  "blocked_user": "app",
  "blocked_query": "UPDATE orders SET status='paid' WHERE id=$1",
  "blocking_pid": 1408,
  "blocking_user": "app",
  "blocking_query": "SELECT ... FROM orders WHERE ... FOR UPDATE",
  "wait_event_type": "Lock",
  "wait_event": "transactionid"
}
```

### Sessions / waits (`pg_stat_activity`)

```json
{
  "pid": 1412,
  "user": "app",
  "database": "app",
  "state": "active",
  "wait_event_type": "Lock",
  "wait_event": "transactionid",
  "query_age_s": 42,
  "query": "UPDATE orders SET status='paid' WHERE id=$1"
}
```

### Table stats / bloat (`pg_stat_user_tables`)

```json
{
  "schema": "public",
  "table": "orders",
  "seq_scan": 1200,
  "idx_scan": 45800,
  "live_rows": 245680,
  "dead_rows": 10241,
  "bloat_pct": 4.2,
  "last_autovacuum": "2026-09-04T00:00:00+00:00"
}
```

### Execution plans (`EXPLAIN`, no ANALYZE)

Not part of the one-shot snapshot — `collect_plan()` plans a single
`SELECT`/`WITH` query on demand (300s cadence) and returns:

```json
{
  "query": "SELECT * FROM orders WHERE customer_id = $1",
  "plan": { "Plan": { "Node Type": "Seq Scan", "Relation Name": "orders" } }
}
```