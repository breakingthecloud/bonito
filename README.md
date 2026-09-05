# 🐟 Bonito OSS

> Deep database observability — a free DBmarlin. Captures slow queries, locks, wait events, and table stats from PostgreSQL (MySQL/Oracle/SQL Server planned), and exposes them for AI agents, MCP servers, and SOC/support teams.

**Status:** v0.1.0 (Phase 0 — PostgreSQL MVP) · Apache 2.0

---

## Why

Prometheus exporters give you **Level 1** metrics (connections, txn/s, replication lag) — the numbers, not the *why*. Commercial tools like DBmarlin ($45/db/mo) give **Level 3**: query text, execution plans, lock/blocking trees, wait events. No open-source tool covers this well.

Bonito connects **read-only** to your database, reads the system views the engine already exposes for free (`pg_stat_statements`, `pg_stat_activity`, `pg_locks`, `pg_stat_user_tables`), and emits deep observability data.

## Ecosystem

```
🐟 Bonito (deep DB observability)  ──feeds──▶  🚣 Remo (AI incident triage)
   "query X has a seq scan on 10M rows"          "here's the fix: CREATE INDEX..."
```

## Components (Phase 0)

| Component | What | Status |
|-----------|------|:------:|
| bonito-collector | Read-only PostgreSQL collector | ✅ Done (BON-001) |
| bonito-store | SQLite event store + `POST /events` | ✅ Done (BON-002) |
| bonito-api | FastAPI query layer (private deploy, public contract) | ✅ Done (BON-003) |
| bonito-mcp | MCP server — 8 tools for AI agents | 🟡 Done, pending merge (BON-004) |

## Setup

```bash
uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

## Docs & Examples (v0.1.0)

- **Docs:** [`docs/quickstart.md`](docs/quickstart.md) (full pipeline) · [`docs/configuration.md`](docs/configuration.md) · [`docs/metrics-and-events.md`](docs/metrics-and-events.md) · [`docs/store.md`](docs/store.md) · [`docs/api.md`](docs/api.md) · [`docs/mcp.md`](docs/mcp.md)
- **Examples:** [`examples/docker-compose.yml`](examples/docker-compose.yml) (PG + store + api + mcp + collector stack) · [`examples/readonly-role.sql`](examples/readonly-role.sql) (read-only role) · [`examples/bonito.env.example`](examples/bonito.env.example) (collector env) · [`examples/store.env.example`](examples/store.env.example) (store env) · [`examples/api.env.example`](examples/api.env.example) (api env) · [`examples/mcp.env.example`](examples/mcp.env.example) (mcp env) · [`examples/events.sample.json`](examples/events.sample.json) (JSON event payload) · [`examples/store-push.sh`](examples/store-push.sh) (push sample → baselines)

Fastest path — full pipeline in one command:

```bash
uv pip install -e ".[dev]" -e bonito-store -e bonito-api
docker compose -f examples/docker-compose.yml up -d
docker exec -i bonito-db psql -U postgres -d app < examples/readonly-role.sql
set -a; source examples/bonito.env.example; set +a
bonito-collector --once
curl localhost:8000/baselines
export BONITO_API_KEY=change-me
curl -H "X-API-Key: $BONITO_API_KEY" localhost:8100/queries/top
```

## Security (golden rule)

- Connection is **READ-ONLY** (a DB user with only `SELECT` on stat views)
- Never build SQL from client input — only fixed queries over system views
- Never writes to the client database

---

*Built by Carlos Cortez — AWS Community Hero. Part of the SOFE / Remo / Bonito observability ecosystem.*
