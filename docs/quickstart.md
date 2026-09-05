# Bonito v0.1.0 — Quickstart

Get the **full Bonito pipeline** running locally in ~5 minutes:
PostgreSQL → `bonito-collector` → `bonito-store` → `bonito-api` → baselines.

**Prerequisites:** Python 3.11+, Docker (for the local PostgreSQL).

---

## 1. Install

All three packages (collector + store + api):

```bash
uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install -e ".[dev]" -e bonito-store -e bonito-api
```

Verify:

```bash
bonito-collector --version   # bonito-collector 0.1.1
bonito-store --help          # serve | prune
bonito-api --help            # serve | spec
```

---

## 2. Run the stack (PostgreSQL + store + api)

```bash
docker compose -f examples/docker-compose.yml up -d db store api
```

This starts:

- `bonito-db` — `postgres:16` with `pg_stat_statements` enabled + sample data
- `bonito-store` — FastAPI on `:8000`, SQLite at `/data/bonito.db`
- `bonito-api` — query layer on `:8100` (API key `change-me`, reads the store's DB)

`up -d` (no service args) also starts the collector so it pushes straight into
the store.

---

## 3. Create the read-only role

```bash
docker exec -i bonito-db psql -U postgres -d app \
  < examples/readonly-role.sql
```

Creates `bonito_ro` with `pg_monitor` + `SELECT` on `pg_stat_statements`.

---

## 4. Run the collector (pointing at the store)

```bash
cp examples/bonito.env.example .env.bonito
set -a; source .env.bonito; set +a
```

`BONITO_DSN` is required; `BONITO_STORE_URL` makes the collector push every
snapshot to the store. One-shot:

```bash
bonito-collector --once
# [2026-09-04T...Z] queries=20 locks=0 sessions=3 tables=20
```

Long-running loop (Prometheus on `:9187/metrics` + push to store):

```bash
bonito-collector
# bonito-collector 0.1.0 — Prometheus on :9187/metrics
```

---

## 5. Read it back from the API

```bash
export BONITO_API_KEY=change-me
curl -H "X-API-Key: $BONITO_API_KEY" localhost:8100/queries/top?limit=5
curl -H "X-API-Key: $BONITO_API_KEY" localhost:8100/baseline/-6842865755026457642
```

Or push the bundled sample snapshot into the store and read it:

```bash
./examples/store-push.sh
```

```json
{ "baselines": [
    { "fingerprint": "-6842865755026457642", "samples": 1,
      "mean_ms": 12.43, "p95_ms": 12.43 }
] }
```

---

## What you get

| Component | What |
|-----------|------|
| `bonito-collector` | Top queries, locks/blocking tree, sessions/waits, table bloat, `EXPLAIN` plans |
| `bonito-store` | Persists those events + 7-day baselines per fingerprint |
| `bonito-api` | Query layer for AI agents / MCP / Remo (contract public, deployment private) |
| Prometheus | Numeric gauges on `:9187/metrics` |

Docs: [`docs/configuration.md`](configuration.md) ·
[`docs/metrics-and-events.md`](metrics-and-events.md) ·
[`docs/store.md`](store.md) · [`docs/api.md`](api.md)