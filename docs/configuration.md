# Bonito v0.1.0 — Configuration

The collector is configured entirely through environment variables. There is no
config file to keep the container story simple.

## Environment variables

| Variable | Required | Default | Description |
|----------|:--------:|---------|-------------|
| `BONITO_DSN` | ✅ | — | Read-only PostgreSQL DSN (`postgresql://user:pass@host:5432/db`) |
| `BONITO_TOP_N` | | `20` | Number of top queries / tables to collect |
| `BONITO_STORE_URL` | | *(disabled)* | Base URL of bonito-store (or cloud endpoint); collector POSTs JSON events to `/events` |
| `BONITO_PROM_PORT` | | `9187` | Port for the Prometheus `/metrics` endpoint |

See `examples/bonito.env.example` for a ready-to-copy template.

## Scrape intervals

Intervals are fixed per collector type (BON-001 deliverable 8). They are defined
in `src/bonito_collector/config.py`.

| Type | Interval | Why |
|------|:--------:|-----|
| `metrics` | 15s | Lightweight numeric metrics |
| `queries` | 60s | `pg_stat_statements` top queries |
| `locks` | 30s | Blocking tree |
| `sessions` | 30s | Active sessions / waits |
| `plans` | 300s | `EXPLAIN` — expensive, infrequent |
| `tables` | 300s | Table/index stats + bloat |

The loop runs at the fastest cadence (15s) and each collector collects on its
own schedule.

## Store configuration

The store (`bonito-store`) has its own variables (see `docs/store.md`):

| Variable | Default | Description |
|----------|---------|-------------|
| `BONITO_DB` | `bonito.db` | SQLite file path |
| `BONITO_STORE_PORT` | `8000` | HTTP port |
| `BONITO_RETENTION_DAYS` | `7` | Retention window |

Example: `examples/store.env.example`.

## Security (golden rule)

- The connection is **READ-ONLY**: every session runs
  `SET default_transaction_read_only = on` and
  `SET statement_timeout = '5s'` (`src/bonito_collector/db.py`).
- SQL is **always a fixed constant** over system stat views. Client input never
  reaches SQL; values only travel via `%s` parameters.
- Execution plans use plain `EXPLAIN` (never `EXPLAIN ANALYZE`), and only for
  statements that begin with `SELECT`/`WITH`, so nothing is ever executed on
  the client database.