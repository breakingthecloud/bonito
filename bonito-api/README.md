# bonito-api

The FastAPI query layer of Bonito (BON-003). Exposes the data stored by
`bonito-store` as structured JSON for AI agents, the MCP server (BON-004) and
Remo (R-007).

**Contract public, deployment private.** `/openapi.json` + `/docs` are the
public contract (no auth) — every consumer implements against them. The data
endpoints are private: every request needs `X-API-Key` (or
`Authorization: Bearer`) matching `BONITO_API_KEY`.

## Run

```bash
uv pip install -e bonito-api
export BONITO_API_KEY=change-me
bonito-api serve --db bonito.db          # FastAPI on :8100
```

```bash
curl -H "X-API-Key: $BONITO_API_KEY" localhost:8100/queries/top?limit=5
curl -H "X-API-Key: $BONITO_API_KEY" localhost:8100/baseline/-6842865755026457642
```

## Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /queries/top?period=&limit=` | Top queries by mean execution time |
| `GET /locks/active` | Recent lock events / blocking pairs |
| `GET /waits` | Wait breakdown by `wait_event_type` |
| `GET /plans/{fingerprint}` | Latest execution plan (JSON) for a query |
| `GET /health/{db_instance}` | Session + bloat summary |
| `GET /baseline/{fingerprint}` | Query vs its 7-day baseline (mean/p95 + regression) |
| `POST /ingest` | Compat webhook — same payload as the store's `/events` |

The committed [`openapi.yaml`](openapi.yaml) is the versioned public contract.

## Config

| Env var | Default | Description |
|---------|---------|-------------|
| `BONITO_API_KEY` | *(required)* | API key for all data endpoints |
| `BONITO_DB` | `bonito.db` | SQLite file written by `bonito-store` |
| `BONITO_API_PORT` | `8100` | HTTP port |