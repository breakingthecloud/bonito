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
| bonito-collector | Read-only PostgreSQL collector | 🟡 In progress (BON-001) |
| bonito-store | Time-series storage | 🔴 BON-002 |
| bonito-api | FastAPI query layer | 🔴 BON-003 |
| bonito-mcp | MCP server for AI agents | 🔴 BON-004 |

## Setup

```bash
uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

## Docs & Examples (v0.1.0)

- **Docs:** [`docs/quickstart.md`](docs/quickstart.md) · [`docs/configuration.md`](docs/configuration.md) · [`docs/metrics-and-events.md`](docs/metrics-and-events.md)
- **Examples:** [`examples/docker-compose.yml`](examples/docker-compose.yml) (PG + collector stack) · [`examples/readonly-role.sql`](examples/readonly-role.sql) (read-only role) · [`examples/bonito.env.example`](examples/bonito.env.example) (env template) · [`examples/events.sample.json`](examples/events.sample.json) (JSON event payload)

Fastest path — local PostgreSQL + one-shot snapshot:

```bash
docker compose -f examples/docker-compose.yml up -d db
docker exec -i bonito-db psql -U postgres -d app < examples/readonly-role.sql
set -a; source examples/bonito.env.example; set +a
bonito-collector --once
```

## Security (golden rule)

- Connection is **READ-ONLY** (a DB user with only `SELECT` on stat views)
- Never build SQL from client input — only fixed queries over system views
- Never writes to the client database

---

*Built by Carlos Cortez — AWS Community Hero. Part of the SOFE / Remo / Bonito observability ecosystem.*
