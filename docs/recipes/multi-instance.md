# Recipe: Multi-instancia con 1 collector

Monitor **N PostgreSQL instances** with a single collector process (BON-013).
Every metric, event and span carries a `db_instance` label.

## 1. Configure instances

Replace `BONITO_DSN` with `BONITO_INSTANCES` (JSON):

```bash
export BONITO_INSTANCES='[
  {"name": "app",  "engine": "postgresql", "dsn": "postgresql://bonito_ro:...@db1:5432/app"},
  {"name": "app2", "engine": "postgresql", "dsn": "postgresql://bonito_ro:...@db2:5432/app2"}
]'
bonito-collector
```

`BONITO_DSN` still works for the single-instance case (instance name
`default`).

## 2. What changes

| Output | Effect |
|--------|--------|
| Prometheus gauges | label `db_instance="app"` / `"app2"` |
| JSON events | `db_instance` field on every event |
| OTLP spans | `db.instance` attribute |
| API | `db_instance` query param (default `default`) |

## 3. Query per instance

```bash
curl -H "X-API-Key: $BONITO_API_KEY" "localhost:8100/queries/top?db_instance=app&limit=5"
curl -H "X-API-Key: $BONITO_API_KEY" "localhost:8100/locks/active?db_instance=app2"
```

## 4. Dashboards & alerts

Grafana panels group by `db_instance` ("Active sessions by instance"), and
alert rules carry `db_instance` in labels so Remo enrichment queries the
right instance:

```text
bonito_blocking_sessions{db_instance="app"} 1.0   # alert labels include db_instance=app
```

## Verified

The demo tenant runs two instances (`app`, `app2`) — 10 metric series each in
Prometheus, both visible in the "Deep DB View" dashboard.