# Alerting → Remo (BON-012)

Bonito metrics live in Prometheus — but metrics don't page anyone. The
**Fase C** flow turns `bonito_*` metrics into alerts that hit **Remo**
(`api.remo.sofe.dev/ingest`) for AI triage, with live Bonito context
(query text, blocking tree, baseline) attached by Remo's R-007 enrichment.

```
bonito_* metrics → Prometheus rules → Alertmanager → Remo /ingest → AI triage + enrichment
```

## Alert rules (`deploy/cloud/lightsail/obs/alerting/rules/bonito.rules.yml`)

| Alert | Expression | Severity | `for` |
|-------|-----------|:--------:|:-----:|
| `BonitoBlocking` | `bonito_blocking_sessions > 0` | critical | 1m |
| `BonitoIdleInTransaction` | `bonito_idle_in_transaction > 0` | warning | 2m |
| `BonitoQuerySlow` | `topk(3, bonito_query_mean_ms) > 100` | warning | 2m |
| `BonitoRegression` | `bonito_query_anomaly == 1` | critical | 1m |
| `BonitoCollectorDown` | `up{job="bonito-collector"} == 0` | critical | 2m |
| `BonitoStoreDown` | `up{job="bonito-store"} == 0` | critical | 2m |

## Alertmanager receiver

`deploy/cloud/lightsail/obs/alerting/alertmanager.yml`:

```yaml
route:
  group_by: ['alertname', 'fingerprint']
  receiver: remo

receivers:
  - name: remo
    webhook_configs:
      - url: https://api.remo.sofe.dev/ingest
        send_resolved: false
        http_config:
          http_headers:
            X-Webhook-Secret:
              values: [whsec_<tenant>_001]
```

The webhook payload is the **native Alertmanager format** (`{receiver,
status, alerts:[{labels, annotations}]}`) — Remo's `parsePrometheusAlerts()`
handles it as-is.

## Remo tenant

1. Create the tenant config in KV: `tenants/bonito-demo` (YAML with
   `sla`, `llm`, `sources`, `enrichment`).
2. Map the webhook secret → tenant:
   `secrets/whsec_bonito_demo_001` → `bonito-demo`.
3. `send_resolved: false` — only **FIRING** alerts hit Remo (no "OK" spam).

## Enrichment (R-007)

When the alert is a DB alert (`isDBAlert`), Remo fetches live context from
`bonito-api` before triaging:

- `/queries/top` → slow queries with text
- `/locks/active` → blocking tree (who blocks whom)
- `/baseline/{fingerprint}` → regression vs 7-day baseline

The diagnosis then includes the exact blocker/PID and remediation:

> **PID 829705** holding transactionid lock, blocking **PID 829718**.
> `SELECT pg_cancel_backend(829705);` · `CREATE INDEX idx_orders_id ON orders(id);`

## Verified end-to-end

Sprint 10 (2026-09-16): a real blocking scenario (`generate-load.sh`) →
`bonito_blocking_sessions=1` → `BonitoBlocking` FIRING → Alertmanager →
Remo → enriched incident with PID-level diagnosis. See
[recipes/alert-to-remo](../recipes/alert-to-remo.md).