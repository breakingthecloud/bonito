# Bonito v0.1.0 — Quickstart

Get the **full Bonito pipeline** running locally in ~5 minutes:
PostgreSQL → `bonito-collector` → `bonito-store` → baselines.

**Prerequisites:** Python 3.11+, Docker (for the local PostgreSQL).

---

## 1. Install

Both packages (collector + store):

```bash
uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install -e ".[dev]" -e bonito-store
```

Verify:

```bash
bonito-collector --version   # bonito-collector 0.1.0
bonito-store --help          # serve | prune
```

---

## 2. Run the stack (PostgreSQL + store)

```bash
docker compose -f examples/docker-compose.yml up -d db store
```

This starts:

- `bonito-db` — `postgres:16` with `pg_stat_statements` enabled + sample data
- `bonito-store` — FastAPI on `:8000`, SQLite at `/data/bonito.db`

The compose also wires a `collector` service — `up -d` (no service args)
starts all three so the collector pushes straight into the store.

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

## 5. Read it back from the store

```bash
curl localhost:8000/baselines          # 7-day mean + p95 per query
curl localhost:8000/health             # {"status":"ok"}
```

Or push the bundled sample snapshot directly:

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
| Prometheus | Numeric gauges on `:9187/metrics` |

Docs: [`docs/configuration.md`](configuration.md) ·
[`docs/metrics-and-events.md`](metrics-and-events.md) ·
[`docs/store.md`](store.md)