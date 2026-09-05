# bonito-store

The persistence layer of Bonito (BON-002). Stores exactly what Prometheus
can't: **query texts, execution plans, lock events, session snapshots and
table stats** in a single SQLite file. Receives JSON events from
`bonito-collector` via `POST /events`.

## Quickstart

```bash
uv pip install -e bonito-store
bonito-store serve --db bonito.db   # FastAPI on :8000
```

```bash
curl -X POST localhost:8000/events -H 'Content-Type: application/json' \
     -d @examples/events.sample.json
curl localhost:8000/baselines     # 7-day mean + p95 per fingerprint
bonito-store prune                # apply retention
```

## Config

| Variable | Default | Description |
|----------|---------|-------------|
| `BONITO_DB` | `bonito.db` | SQLite file path |
| `BONITO_STORE_PORT` | `8000` | HTTP port |
| `BONITO_RETENTION_DAYS` | `7` | Retention window (pruned in background) |

## Endpoints

- `POST /events` — ingest a collector snapshot (batch capped at 100 per type)
- `POST /plans` — ingest execution plan records (stored as JSON)
- `GET /baselines?fingerprint=...&days=7` — rolling mean + p95 per query
- `GET /health`

## Design

- **Dedupe**: `query_texts` is keyed by `fingerprint` (sha256 of the minified
  query). Same query updates stats instead of creating a new row.
- **Baselines**: each observation is appended to `query_samples`; baselines are
  computed on the fly over the last N days (mean + p95).
- **Retention**: `lock_events`, `session_snapshots`, `execution_plans`,
  `query_samples` and `table_stats` are pruned past `BONITO_RETENTION_DAYS`.
  Identity tables (`query_texts`) keep the latest stats forever.
- **Plans**: stored as raw JSON (`EXPLAIN` output) — never interpolated into
  prompts without truncation (LLM token governance).