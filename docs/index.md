# 🐟 Bonito OSS

Deep database observability — a free DBmarlin.

Prometheus exporters give you **Level 1** metrics (connections, txn/s,
replication lag) — the numbers, not the *why*. Bonito gives you **Level 3**:
query texts, execution plans, lock/blocking trees, wait events and baselines,
exposed to **AI agents via MCP**.

```
🐟 Bonito (deep DB observability)  ──feeds──▶  🚣 Remo (AI incident triage)
   "query X has a seq scan on 10M rows"          "here's the fix: CREATE INDEX..."
```

## Components

| Component | What | PyPI |
|-----------|------|------|
| `bonito-collector` | Read-only PostgreSQL collector | `bonito-collector` |
| `bonito-store` | SQLite event store + baselines | `bonito-store` |
| `bonito-api` | FastAPI query layer (private deploy, public contract) | `bonito-api` |
| `bonito-mcp` | MCP server — 8 tools for AI agents | `bonito-mcp-server` |

## Start here

- [Quickstart](quickstart.md) — full pipeline in ~5 minutes
- [Configuration](configuration.md) — env vars for every component
- [MCP server](mcp.md) — connect Claude/Bedrock/Strands

## License

Apache 2.0 — built by Carlos Cortez, part of the SOFE / Remo / Bonito
observability ecosystem.