# 🐟 Bonito OSS

> Deep database observability — a free DBmarlin. Captures slow queries, locks, wait events, and table stats from PostgreSQL (MySQL/Oracle/SQL Server planned), and exposes them to **AI agents via MCP**.

**Status:** v0.1.0 (Phase 0 — PostgreSQL MVP complete) · Apache 2.0

---

## Why

Prometheus exporters give you **Level 1** metrics (connections, txn/s, replication lag) — the numbers, not the *why*. Commercial tools like DBmarlin ($45/db/mo) give **Level 3**: query text, execution plans, lock/blocking trees, wait events. No open-source tool covers this well — and none exposes it to AI agents over **MCP**.

Bonito connects **read-only** to your database, reads the system views the engine already exposes for free (`pg_stat_statements`, `pg_stat_activity`, `pg_locks`, `pg_stat_user_tables`), and emits deep observability data.

## Architecture

```
 ┌──────────────┐  system views   ┌───────────────┐  POST /events  ┌───────────────┐
 │  PostgreSQL  │──────────────▶  │ bonito-collector│──────────────▶ │ bonito-store  │
 │  (read-only) │  Prometheus      │ (PyPI)  :9187  │  JSON (≤100)   │ SQLite+baseline│
 └──────────────┘  :9187/metrics   └───────────────┘                 └──────┬────────┘
                                                                           │ reads
                                                              ┌────────────▼────────┐
                                                              │ bonito-api (FastAPI) │  X-API-Key
                                                              │ :8100 · openapi.yaml │  private deploy
                                                              └────────────┬────────┘  public contract
                                                                           │ REST
                                                              ┌────────────▼────────┐
                                                              │ bonito-mcp (MCP)     │  stdio / SSE :8840
                                                              │ 8 tools for agents   │
                                                              └────────────┬────────┘
                                                                           ▼
                                                   Claude · Bedrock · Strands · Remo (R-007)
```

## Quick start (5 min)

```bash
docker compose -f deploy/docker-compose.yml up -d
# PostgreSQL fixture + collector + store + api + mcp

curl -H "X-API-Key: change-me" localhost:8100/queries/top?limit=5
curl -H "X-API-Key: change-me" localhost:8100/baseline/-6842865755026457642

claude mcp add bonito -- bonito-mcp        # connect an AI agent
```

Full step-by-step: [`docs/quickstart.md`](docs/quickstart.md).

## Components

| Component | What | PyPI |
|-----------|------|------|
| `bonito-collector` | Read-only PostgreSQL collector | `bonito-collector` |
| `bonito-store` | SQLite event store + 7-day baselines | `bonito-store` |
| `bonito-api` | FastAPI query layer (private deploy, public contract) | `bonito-api` |
| `bonito-mcp` | MCP server — 8 tools for AI agents | `bonito-mcp-server` |

## API reference

| Endpoint | Description |
|----------|-------------|
| `GET /queries/top?db_instance=&period=&limit=` | Top queries by mean execution time |
| `GET /locks/active?db_instance=&minutes=` | Recent lock events / blocking pairs |
| `GET /waits?db_instance=&minutes=` | Wait breakdown by `wait_event_type` |
| `GET /plans/{fingerprint}` | Latest execution plan (JSON) |
| `GET /health/{db_instance}` | Sessions by state + top table bloat |
| `GET /baseline/{fingerprint}?days=` | 7-day baseline + `regression_pct` |
| `POST /ingest` | Compat webhook (same payload as store `/events`) |

Full reference: [`docs/api.md`](docs/api.md) · MCP tools: [`docs/mcp.md`](docs/mcp.md).

## Docs & Examples (v0.1.0)

- **Docs:** [`docs/quickstart.md`](docs/quickstart.md) (full pipeline) · [`docs/configuration.md`](docs/configuration.md) · [`docs/metrics-and-events.md`](docs/metrics-and-events.md) · [`docs/store.md`](docs/store.md) · [`docs/api.md`](docs/api.md) · [`docs/mcp.md`](docs/mcp.md) · mkdocs via `mkdocs serve`
- **Deploy:** [`deploy/docker-compose.yml`](deploy/docker-compose.yml) (full stack) · [`deploy/.env.example`](deploy/.env.example) · [`deploy/init-fixture.sql`](deploy/init-fixture.sql)
- **Examples:** [`examples/ai-agent-demo/`](examples/ai-agent-demo/) (agent diagnoses a deadlock) · [`examples/docker-compose.yml`](examples/docker-compose.yml) · [`examples/readonly-role.sql`](examples/readonly-role.sql) · `examples/*.env.example` · [`examples/events.sample.json`](examples/events.sample.json) · [`examples/store-push.sh`](examples/store-push.sh)

## Security (golden rule)

- Connection is **READ-ONLY** (a DB user with only `SELECT` on stat views)
- Never build SQL from client input — only fixed queries over system views
- Never writes to the client database
- API is **private by default** (`BONITO_API_KEY` required); only the OpenAPI contract is public

## License

Apache 2.0 · [`LICENSE`](LICENSE) · [`CONTRIBUTING.md`](CONTRIBUTING.md)

---

*Built by Carlos Cortez — AWS Community Hero. Part of the SOFE / Remo / Bonito observability ecosystem.*
