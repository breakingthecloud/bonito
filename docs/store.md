# Bonito v0.1.0 — bonito-store

The persistence layer of Bonito. It stores exactly what Prometheus can't:
**query texts, execution plans, lock events, session snapshots and table
stats**, in a single SQLite file — and computes **7-day baselines** per query
fingerprint for anomaly detection.

## Run it

```bash
uv pip install -e bonito-store
bonito-store serve --db bonito.db        # FastAPI on :8000
```

| Env var | Default | Description |
|---------|---------|-------------|
| `BONITO_DB` | `bonito.db` | SQLite file path |
| `BONITO_STORE_PORT` | `8000` | HTTP port |
| `BONITO_RETENTION_DAYS` | `7` | Retention window |

## Endpoints

| Endpoint | Purpose |
|----------|---------|
| `POST /events` | Ingest a collector snapshot (batch capped at 100 per type) |
| `POST /plans` | Ingest execution plan records (stored as JSON) |
| `GET /baselines?fingerprint=...&days=7` | 7-day rolling mean + p95 per query |
| `GET /health` | Liveness |

```bash
curl -X POST localhost:8000/events -H 'Content-Type: application/json' \
     -d @examples/events.sample.json
curl localhost:8000/baselines
```

## Schema (BON-002 deliverable 1)

| Table | Contents |
|-------|----------|
| `query_texts` | Identity per fingerprint: query text, first/last seen, latest calls/avg/max ms |
| `query_samples` | One row per observation `(fingerprint, ts, calls, mean_ms, rows)` — feeds baselines |
| `execution_plans` | `EXPLAIN` output stored as raw JSON + estimated cost |
| `lock_events` | Blocking pairs: blocking pid, blocked pids (JSON), lock mode, duration |
| `session_snapshots` | Per-snapshot active sessions: state, wait_event, query age, query text |
| `table_stats` | Per-snapshot `schema.table` bloat stats |
| `change_history` | Audit log: new fingerprints, retention prunes |

Timestamps are ISO-8601 UTC text so retention and baselines compare trivially.

## Dedupe (deliverable 3)

`query_texts` is keyed by **fingerprint** — the Postgres `queryid` when the
collector supplies it, otherwise the sha256 of the minified query
(`bonito_store.normalize`). The same query updates stats instead of creating a
new row. Samples are `INSERT OR REPLACE` keyed on `(fingerprint, ts)`, so
re-delivered snapshots are idempotent.

## Baselines (deliverable 5)

`GET /baselines` computes, per fingerprint over the last N days:

- `mean_ms` — average mean execution time
- `p95_ms` — 95th percentile (the "slow tail")

```json
{
  "baselines": [
    { "fingerprint": "-6842865755026457642", "samples": 10,
      "mean_ms": 12.43, "p95_ms": 14.1 }
  ]
}
```

## Retention (deliverable 4)

Sample/event tables (`query_samples`, `execution_plans`, `lock_events`,
`session_snapshots`, `table_stats`) are pruned past `BONITO_RETENTION_DAYS`.
Pruning runs automatically on ingest (throttled to once/hour) and manually via:

```bash
bonito-store prune --days 7
```

Identity data (`query_texts`) is kept forever so the API/MCP can always map a
fingerprint to its query text.