# Remo — AI incident triage

[Remo](https://remoso.dev) is an open-source AI SOC triage orchestrator
(Cloudflare Worker, $0/mo). Bonito feeds Remo two ways:

1. **Alerting** — Prometheus alert rules → Alertmanager → Remo `/ingest`
   (see [Alerting → Remo](../observability/alerting.md)).
2. **Enrichment (R-007)** — when a DB alert arrives, Remo pulls live context
   from `bonito-api` so the AI diagnosis is precise (exact PID, query text,
   baseline) instead of generic.

## The loop

```
Bonito metrics → Prometheus rules → Alertmanager
                                          │  webhook (X-Webhook-Secret)
                                          ▼
                                   Remo /ingest
                                          │
                     isDBAlert()?  ──yes──▶  fetch bonito-api
                        │                        /queries/top
                        │                        /locks/active
                        │                        /baseline/{fp}
                        ▼                        ▼
                   LLM triage ◀──────  ENRICHMENT DATA appended to prompt
                                          │
                                          ▼
                              diagnosis with PID + CREATE INDEX
```

## Remo tenant config

The tenant carries the Bonito endpoint + key for enrichment:

```yaml
# tenants/bonito-demo.yaml (in KV)
enrichment:
  enabled: true
  bonito_endpoint: https://bonito-api.sofe.dev
  bonito_api_key: <BONITO_API_KEY>
  bonito_timeout_ms: 3000

sources:
  - name: prometheus
    secret: "whsec_bonito_demo_001"
```

## What Remo needs from Bonito

| Bonito endpoint | Used for |
|-----------------|----------|
| `GET /queries/top?db_instance=` | Slow queries with text (for slow/regression alerts) |
| `GET /locks/active?db_instance=` | Blocking tree → who blocks whom (blocking alerts) |
| `GET /baseline/{fingerprint}` | Regression % vs 7-day baseline |

`isDBAlert()` matches keywords in source/service/title/description/labels
(`postgres`, `mysql`, `deadlock`, `slow_query`, `lock`, `blocking`,
`regression`, ...).

## Failure safety

Enrichment runs with a **3s timeout** and `Promise.allSettled`: if
`bonito-api` is unreachable, triage proceeds without enrichment — the alert
is never lost and never blocked.

## Example diagnosis

> Two blocking session pairs on `app`. Primary blocker: long-running
> `UPDATE orders SET status=$1 WHERE id=$2` (fingerprint 1978432790045853480,
> ~5-10 min) holding locks.
> 1. `SELECT pid, state, query FROM pg_stat_activity WHERE query LIKE '%UPDATE orders SET status%';`
> 2. `SELECT pg_cancel_backend(<pid>);`
> 3. `SELECT pg_terminate_backend(<pid>);`
> 4. `CREATE INDEX IF NOT EXISTS idx_orders_id ON orders(id);`