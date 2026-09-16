# Recipe: Alertar a Remo en 10 min

Turn Bonito metrics into AI-triaged alerts. Verified end-to-end in the demo
tenant (Sprint 10).

## 1. Alert rules

Drop the bundled rules into your Prometheus:

```yaml
# prometheus.yml
rule_files:
  - /etc/prometheus/alerting/rules/*.yml

alerting:
  alertmanagers:
    - static_configs:
        - targets: ['obs-alertmanager:9093']
```

Rules (from `deploy/cloud/lightsail/obs/alerting/rules/bonito.rules.yml`):
`BonitoBlocking`, `BonitoIdleInTransaction`, `BonitoQuerySlow`,
`BonitoRegression`, `BonitoCollectorDown`, `BonitoStoreDown`.

!!! tip
    Keep `rule_files` scoped to a `rules/` subdir — never `*.yml` in a dir
    that also holds `alertmanager.yml` (Prometheus will try to parse it as
    rules and fail).

## 2. Alertmanager receiver

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
              values: [whsec_bonito_demo_001]
```

## 3. Remo tenant

```bash
# KV (namespace of remo-api)
wrangler kv key put "tenants/bonito-demo" "$(cat tenants/bonito-demo.yaml)" --remote
wrangler kv key put "secrets/whsec_bonito_demo_001" "bonito-demo" --remote
```

Tenant YAML needs `sla`, `llm` (free model), `sources[prometheus]` and
(optional) `enrichment.bonito_endpoint`.

## 4. Trigger + verify

Trigger real blocking:

```bash
# holder (row lock) + blocked updater
docker exec -d bonito-collector python -c "import psycopg,time; c=psycopg.connect('postgresql://postgres:postgres@dbs-postgres:5432/app'); c.autocommit=False; c.execute('UPDATE orders SET status=%s WHERE id=1',('held',)); time.sleep(600)"
docker exec -d bonito-collector python -c "import psycopg; c=psycopg.connect('postgresql://postgres:postgres@dbs-postgres:5432/app'); c.autocommit=True; c.execute('UPDATE orders SET status=%s WHERE id=1',('stuck',))"
```

Within ~1-2 min:

```bash
# BonitoBlocking fires → Remo creates + triages the incident
curl -s -H "X-Remo-Key: rk_bonito_demo_001" "https://api.remo.sofe.dev/incidents?limit=3" | jq '.incidents[].title'
```

You'll see the incident with an `enriched` step and a diagnosis naming the
**PID to kill**:

```
1. SELECT pid, state, query FROM pg_stat_activity WHERE query LIKE '%UPDATE orders SET status%';
2. SELECT pg_cancel_backend(<pid>);
3. CREATE INDEX IF NOT EXISTS idx_orders_id ON orders(id);
```

## What you get

| Before | After |
|--------|-------|
| A graph that changed shape | A page (Slack/Discord ticket) with the culprit query |
| "connections are high" | "PID 829705 blocks PID 829718; cancel it" |
| Manual triage | AI triage + enrichment in seconds |