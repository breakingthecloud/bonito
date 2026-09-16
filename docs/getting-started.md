# Getting started

Get the **full Bonito pipeline** running locally in ~5 minutes:
PostgreSQL → `bonito-collector` → `bonito-store` → `bonito-api` → baselines.

**Prerequisites:** Python 3.11+, Docker (for the local PostgreSQL).

---

## 1. Install

```bash
uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install -e ".[dev]" -e bonito-store -e bonito-api
```

Verify:

```bash
bonito-collector --version   # bonito-collector 0.2.0
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
# bonito-collector 0.2.0 — Prometheus on :9187/metrics
```

!!! tip "Multiple databases"
    Set `BONITO_INSTANCES` (JSON) to monitor N databases with one collector.
    Every metric/event gets a `db_instance` label. See
    [Multi-instancia recipe](recipes/multi-instance.md).

---

## 5. Read it back from the API

```bash
export BONITO_API_KEY=change-me
curl -H "X-API-Key: $BONITO_API_KEY" localhost:8100/queries/top?limit=5
curl -H "X-API-Key: $BONITO_API_KEY" localhost:8100/baseline/-6842865755026457642
curl -H "X-API-Key: $BONITO_API_KEY" localhost:8100/anomalies     # regression list
```

---

## 6. Give an AI agent the tools (MCP)

```bash
uv pip install -e bonito-mcp
export BONITO_API_URL=http://localhost:8100
bonito-mcp                     # stdio — then add to Claude/Bedrock/Strands
```

Claude CLI:

```bash
claude mcp add bonito -- bonito-mcp
```

Now the agent can answer "which queries are slow?", "who is blocking whom?",
"is this query slower than its baseline?", and "what should I do?" — see
[mcp.md](mcp.md) for the full tool list and the deadlock demo flow.

---

## What you get

| Component | What |
|-----------|------|
| `bonito-collector` | Top queries, locks/blocking tree, sessions/waits, table bloat, `EXPLAIN` plans — Prometheus + JSON events + OTLP spans |
| `bonito-store` | Persists events + 7-day baselines + **anomaly engine** (`/anomalies`, `/metrics`) |
| `bonito-api` | Query layer for AI agents / MCP / Remo (contract public, deployment private) |
| `bonito-mcp` | 8 tools any AI agent consumes natively (Claude/Bedrock/Strands) |
| Prometheus | Numeric gauges on `:9187/metrics` + store `/metrics` (regression/anomaly) |

## Next steps

- [Architecture](architecture.md) — full data flow
- [Prometheus metrics](observability/metrics.md) — every `bonito_*` metric
- [Alerting → Remo](observability/alerting.md) — turn metrics into AI-triaged alerts
- [Configuration](configuration.md) — every env var