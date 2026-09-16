# Architecture

Bonito is a **read-only observability pipeline** for PostgreSQL (more engines
planned). It collects the data Prometheus can't — query texts, execution
plans, lock trees, wait events, table bloat — and makes it consumable by
humans (Grafana), AI agents (MCP) and AI incident triage (Remo).

## Data flow

```
┌──────────────────────────────────────────────────────────────────────┐
│                       Postgres (read-only)                            │
│   pg_stat_statements · pg_locks · pg_blocking_pids · pg_stat_activity │
│   pg_stat_user_tables · EXPLAIN (SELECT/WITH only)                    │
└───────────────▲──────────────────────────────────────────────────────┘
                │ BONITO_DSN / BONITO_INSTANCES (multi-instance)
┌───────────────┴──────────────────────────────────────────────────────┐
│                        bonito-collector                              │
│   • Prometheus gauges   :9187/metrics   (bonito_*)                   │
│   • JSON events  ───────▶ POST store/events                          │
│   • OTLP spans   ───────▶ Tempo (query.<fp> + lock.blocking)         │
└───────────────┬──────────────────────────────┬───────────────────────┘
                │                              │
                ▼                              ▼
┌──────────────────────────┐      ┌───────────────────────────────────┐
│      bonito-store        │      │   Prometheus + Alertmanager       │
│   SQLite · baselines 7d  │      │   alert rules → webhook           │
│   anomaly engine         │      │          │                        │
└───────────────┬──────────┘      │          ▼                        │
                │                  │    api.remo.sofe.dev/ingest      │
                ▼                  └───────────────────────────────────┘
┌──────────────────────────┐
│        bonito-api        │
│   /queries/top · /locks  │
│   /baseline · /anomalies │
└───────┬─────────┬────────┘
        │         │
        ▼         ▼
   bonito-mcp   Remo (R-007 enrichment)
   (8 tools)    isDBAlert → fetch context
```

## The pieces

### 1. Collector (`bonito-collector`)

Read-only by design: every connection runs
`SET default_transaction_read_only = on` and `SET statement_timeout = '5s'`.
SQL is always a fixed constant over system views; values travel only via
`%s` parameters. Execution plans use plain `EXPLAIN` for `SELECT`/`WITH`
only — nothing is ever executed on the client database.

Each run produces **three** outputs:

1. **Prometheus gauges** — `:9187/metrics` (see [metrics](observability/metrics.md))
2. **JSON events** — POSTed to `BONITO_STORE_URL/events` (top queries, locks,
   sessions/waits, table stats)
3. **OTLP spans** — to `BONITO_OTLP_ENDPOINT` (Tempo) for trace-level
   drilldown ([tracing](observability/tracing.md))

Scrape cadences (per type): metrics 15s · queries 60s · locks 30s ·
sessions 30s · plans 300s · tables 300s.

### 2. Store (`bonito-store`)

Single SQLite file, what Prometheus can't hold: query texts, plans (JSON),
lock events, session snapshots, table stats — plus:

- **Dedupe** by fingerprint (`pg_stat_statements` queryid, or sha256 of the
  minified query) — identity rows update instead of duplicating.
- **7-day baselines** per fingerprint (`mean_ms`, `p95_ms`).
- **Anomaly engine**: z-score + `regression_pct` + status
  `normal | regression` per query, exposed via `/anomalies` and as Prometheus
  metrics (`bonito_query_anomaly`, `bonito_query_regression_pct`).
- **Retention** (default 7 days) with automatic prune.

### 3. API (`bonito-api`)

FastAPI query layer. **Contract public, deployment private**: the OpenAPI
contract (`/openapi.json`, `bonito-api/openapi.yaml`) is the stable contract;
every data endpoint requires `X-API-Key`. Consumed by the MCP server and by
Remo enrichment (R-007).

### 4. MCP server (`bonito-mcp`)

8 tools over stdio or SSE giving AI agents native access:
`get_slow_queries`, `get_active_locks`, `get_blocking_tree`,
`explain_query`, `get_wait_analysis`, `compare_to_baseline`,
`suggest_remediation`, `get_db_health_summary`.

### 5. Observability stack (optional)

Prometheus + Alertmanager + Grafana + Tempo are deployed with the
[Lightsail demo tenant](https://github.com/breakingthecloud/bonito/blob/main/deploy/cloud/lightsail/README.md). Alert rules
turn `bonito_*` metrics into alerts that hit **Remo** `/ingest`, and Remo
enriches them with live Bonito context (query text, blocking tree, baseline)
before the AI triage.

## Multi-instance (BON-013)

One collector → N databases. `BONITO_INSTANCES` (JSON list of
`{name, engine, dsn}`) replaces `BONITO_DSN`. Every Prometheus gauge and
event carries a `db_instance` label so dashboards and alerts stay per-DB.

## Security model

- Collector: **read-only**, fixed SQL, `EXPLAIN` (no ANALYZE), no client input
  in SQL.
- API/MCP: API-key auth, `query_text` truncated to 500 chars (token
  governance), no secrets in tool output.
- The pipeline never modifies the observed database.