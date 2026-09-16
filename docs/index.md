# 🐟 Bonito OSS

**Deep database observability — a free DBmarlin.**

Prometheus exporters give you **Level 1** metrics (connections, txn/s,
replication lag) — the numbers, not the *why*. Bonito gives you **Level 3**:
query texts, execution plans, lock/blocking trees, wait events, table bloat
and 7-day baselines — exposed to **AI agents via MCP** and to **Remo** for
AI incident triage.

```
🐟 Bonito (deep DB observability)  ──feeds──▶  🚣 Remo (AI incident triage)
   "query X has a seq scan on 10M rows"          "here's the fix: CREATE INDEX..."
```

## Why Bonito

| Level | Tools | What you get |
|:-----:|-------|--------------|
| 1 — Numbers | Prometheus exporters | `connections`, `txn/s`, `replication lag` |
| 2 — Who | pg_stat_activity / dashboards | sessions, waits, current activity |
| 3 — **Why** | **Bonito** | **query text, EXPLAIN plans, blocking tree, baselines, anomaly** |

## Components

| Component | What | PyPI |
|-----------|------|------|
| `bonito-collector` | Read-only collector — top queries, locks, sessions/waits, bloat, plans | `bonito-collector` |
| `bonito-store` | SQLite event store + 7-day baselines + anomaly engine | `bonito-store` |
| `bonito-api` | FastAPI query layer (contract public, deployment private) | `bonito-api` |
| `bonito-mcp` | MCP server — 8 tools for AI agents | `bonito-mcp-server` |

## Start here

- [Getting started](getting-started.md) — full pipeline in ~5 minutes
- [Architecture](architecture.md) — how the pieces fit
- [Prometheus metrics](observability/metrics.md) — the full metric catalog
- [Alerting → Remo](observability/alerting.md) — alerts with AI triage
- [MCP server](mcp.md) — connect Claude / Bedrock / Strands

## Live demo tenant

The `bonito-demo` Lightsail tenant runs the whole stack in production:

- Grafana — `grafana-demo.sofe.dev` (Dashboard "Deep DB View")
- Prometheus — `prometheus-demo.sofe.dev`
- Bonito API — `bonito-api.sofe.dev`
- Remo API — `api.remo.sofe.dev` (alerts + enrichment)

## License

Apache 2.0 — part of the SOFE / Remo / Bonito observability ecosystem.