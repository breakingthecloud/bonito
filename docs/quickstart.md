# Bonito v0.1.0 — Quickstart

Get `bonito-collector` talking to a PostgreSQL database in ~5 minutes.

**Prerequisites:** Python 3.11+, Docker (for the local PostgreSQL).

---

## 1. Install

```bash
uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

Verify:

```bash
bonito-collector --version   # bonito-collector 0.1.0
```

---

## 2. Run a local PostgreSQL (with `pg_stat_statements`)

The deep collectors read `pg_stat_statements`, so the extension must be enabled.
The easiest path is the example compose stack:

```bash
docker compose -f examples/docker-compose.yml up -d db
```

This starts `postgres:16` with `shared_preload_libraries = 'pg_stat_statements'`
and the extension enabled on the `app` database.

---

## 3. Create the read-only role

Never run the collector as superuser. Apply the example script:

```bash
docker exec -i bonito-db psql -U postgres -d app \
  < examples/readonly-role.sql
```

This creates `bonito_ro`, grants `pg_monitor` (read access to the stat views)
plus `SELECT` on `pg_stat_statements` and on the `public` schema tables.

---

## 4. Point the collector at it

```bash
cp examples/bonito.env.example .env.bonito
# edit the DSN if your host/user differs
set -a; source .env.bonito; set +a
```

Minimum required variable: `BONITO_DSN` (see `docs/configuration.md`).

---

## 5. Run it

One-shot snapshot (prints counts, emits to Prometheus gauges, and pushes to
`BONITO_STORE_URL` if set):

```bash
bonito-collector --once
# [2026-09-04T...Z] queries=20 locks=0 sessions=3 tables=20
```

Long-running loop (Prometheus on `:9187/metrics`, per-type intervals):

```bash
bonito-collector
# bonito-collector 0.1.0 — Prometheus on :9187/metrics
```

Scrape the metrics:

```bash
curl -s localhost:9187/metrics | grep bonito_
```

---

## What you get

| Collector | System view | What it tells you |
|-----------|-------------|-------------------|
| Top queries | `pg_stat_statements` | Slowest queries: calls, mean/max ms, rows, buffer hit ratio |
| Locks / blocking tree | `pg_locks` + `pg_blocking_pids` | Who is blocked by whom, wait event |
| Sessions / waits | `pg_stat_activity` | Active sessions, state, wait_event, query age |
| Table stats / bloat | `pg_stat_user_tables` | seq vs idx scans, live/dead rows, bloat % |
| Execution plans | `EXPLAIN` (no ANALYZE) | Plan JSON for read-only queries |

See `docs/metrics-and-events.md` for the exact output schema.