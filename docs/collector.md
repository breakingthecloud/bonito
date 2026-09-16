# Collector (`bonito-collector`)

The read-only agent that watches your PostgreSQL and emits three outputs:
Prometheus gauges, JSON events (to the store) and OTLP spans (to Tempo).

## Run it

```bash
uv pip install bonito-collector
export BONITO_DSN=postgresql://bonito_ro:change-me@localhost:5432/app
bonito-collector            # loop — Prometheus on :9187/metrics
bonito-collector --once     # one shot, prints the JSON snapshot
```

| Env var | Default | Description |
|---------|:-------:|-------------|
| `BONITO_DSN` | — | Read-only PostgreSQL DSN (single instance) |
| `BONITO_INSTANCES` | — | JSON `[{name, engine, dsn}]` — multi-instance (replaces `BONITO_DSN`) |
| `BONITO_TOP_N` | `20` | Top queries / tables per instance |
| `BONITO_STORE_URL` | off | Push JSON events to `<url>/events` |
| `BONITO_PROM_PORT` | `9187` | Prometheus `/metrics` port |
| `BONITO_OTLP_ENDPOINT` | off | OTLP endpoint (Tempo) for spans |

## What it collects

| Collector | Cadence | Source |
|-----------|:-------:|--------|
| queries | 60s | `pg_stat_statements` top N |
| locks | 30s | `pg_locks` + `pg_blocking_pids` (blocking tree) |
| sessions | 30s | `pg_stat_activity` states + waits |
| plans | 300s | `EXPLAIN` (SELECT/WITH only, no ANALYZE) |
| tables | 300s | `pg_stat_user_tables` bloat |

## Outputs

1. **Prometheus gauges** (`:9187/metrics`) — full catalog in
   [Prometheus metrics](observability/metrics.md).
2. **JSON events** → `BONITO_STORE_URL/events` — query/lock/session/table
   snapshots with `db_instance` (see [Store](store.md)).
3. **OTLP spans** → `BONITO_OTLP_ENDPOINT` — `query.<fingerprint>` and
   `lock.blocking.<blocker>-><blocked>` (see [Tracing](observability/tracing.md)).

## Read-only guarantee

- `SET default_transaction_read_only = on` + `SET statement_timeout = '5s'`
  on every connection.
- SQL is a fixed constant over system views; values only via `%s`.
- Plans use plain `EXPLAIN` for `SELECT`/`WITH` — nothing executes on your DB.