# Recipe: Detectar una regresión de query

Bonito builds a **7-day baseline** per query fingerprint and flags regressions
automatically — no thresholds to tune.

## How it works

The store computes `mean_ms` and `p95_ms` per fingerprint over the retention
window. On demand it compares the **current** average against the baseline
and returns:

```json
{
  "db_instance": "default",
  "fingerprint": "-6842865755026457642",
  "baseline": { "samples": 10, "mean_ms": 12.43, "p95_ms": 14.1 },
  "current_avg_ms": 42.5,
  "regression_pct": 241.9
}
```

`regression_pct > 0` → the query got slower than its baseline.

## Via the API

```bash
curl -H "X-API-Key: $BONITO_API_KEY" "localhost:8100/baseline/-6842865755026457642"
curl -H "X-API-Key: $BONITO_API_KEY" "localhost:8100/anomalies"    # all regressions
```

## Via Prometheus

The store exposes anomaly metrics on `:8000/metrics`:

- `bonito_query_regression_pct{fingerprint="..."}`
- `bonito_query_anomaly{fingerprint="..."}` → `1` when in regression

The `BonitoRegression` alert rule (`bonito_query_anomaly == 1`) turns that
into an alert → Remo (see [alert-to-remo](alert-to-remo.md)).

## Via MCP

```text
User: "is query -6842865755026457642 slower than its baseline?"
Agent: compare_to_baseline(fingerprint="-6842865755026457642")
       → verdict: "REGRESSION — 241.9% slower than 7-day baseline. Suggest CREATE INDEX."
```

## Demo

In the live tenant, `sim-regression-001` was injected with a 10ms baseline and
120ms current → `regression_pct: 1100%`, `bonito_query_anomaly: 1`, and the
`BonitoRegression` alert fired to Remo.