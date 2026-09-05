# Bonito v0.1.0 — bonito-api

The FastAPI **query layer** of Bonito (BON-003). Reads the `bonito-store`
SQLite file and exposes it as structured JSON for AI agents, the MCP server
(BON-004) and Remo (R-007).

**Key principle — contract public, deployment private:**

- **Public:** the OpenAPI contract (`/openapi.json`, `/docs`, and the committed
  [`bonito-api/openapi.yaml`](../bonito-api/openapi.yaml)). Consumers implement
  against *this*, never against a live instance.
- **Private:** the running server. Every data endpoint requires an API key.

## Run it

```bash
uv pip install -e bonito-api
export BONITO_API_KEY=change-me
bonito-api serve --db bonito.db        # FastAPI on :8100
```

| Env var | Default | Description |
|---------|---------|-------------|
| `BONITO_API_KEY` | *(required)* | API key for all data endpoints (`X-API-Key` or `Authorization: Bearer`) |
| `BONITO_DB` | `bonito.db` | SQLite file written by `bonito-store` |
| `BONITO_API_PORT` | `8100` | HTTP port |

If `BONITO_API_KEY` is not set, data endpoints return `503` — the server
refuses to serve unauthenticated.

## Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /queries/top?db_instance=&period=&limit=` | Top queries by mean execution time |
| `GET /locks/active?db_instance=&minutes=` | Recent lock events / blocking pairs |
| `GET /waits?db_instance=&minutes=` | Wait breakdown by `wait_event_type` |
| `GET /plans/{fingerprint}` | Latest execution plan (JSON) for a query |
| `GET /health/{db_instance}` | Session states + top table bloat |
| `GET /baseline/{fingerprint}?days=` | 7-day baseline (mean/p95) + regression % vs current |
| `POST /ingest` | Compat webhook — same payload as store `POST /events` |

`db_instance` is accepted everywhere to keep the contract multi-instance ready.

```bash
curl -H "X-API-Key: $BONITO_API_KEY" localhost:8100/queries/top?limit=5
curl -H "X-API-Key: $BONITO_API_KEY" localhost:8100/baseline/-6842865755026457642
```

## Example response (`GET /baseline/{fingerprint}`)

```json
{
  "db_instance": "default",
  "fingerprint": "-6842865755026457642",
  "baseline": { "fingerprint": "-6842865755026457642", "samples": 10,
                "mean_ms": 12.43, "p95_ms": 14.1 },
  "current_avg_ms": 42.5,
  "regression_pct": 241.9
}
```

`regression_pct > 0` means the query got slower than its 7-day baseline — the
signal Remo/MCP use to recommend `CREATE INDEX` etc.