# Lightsail demo tenant — compose projects

Multi-project Docker stack for the Bonito OSS demo tenant on a Lightsail 4GB
instance (Ubuntu 24.04). Each project is independent (`docker compose -p <proj>`).

## Layout (on the VM, `~/stack`)

| Project | Services | What |
|---------|----------|------|
| `obs`   | prometheus + grafana + node-exporter | Observability |
| `dbs`   | postgres:16 · mongo:7 · mysql:8 · mariadb:11 · redis:7 · valkey:8 | DBs Bonito observes |
| `bonito`| collector + store + api + mcp | Bonito stack (built locally from repo Dockerfiles) |
| `mlflow`| mlflow tracking server | Qhaway metrics (qhaway-004 exporter) |

All services share one external network `bonito-net`.

## Bring it up

```bash
# 1. shared network + env
docker network create bonito-net
cp ~/stack/.env.example ~/stack/.env     # edit passwords

# 2. obs + dbs first
docker compose --env-file ~/stack/.env -p obs -f ~/stack/obs/docker-compose.yml up -d
docker compose --env-file ~/stack/.env -p dbs -f ~/stack/dbs/docker-compose.yml up -d

# 3. bonito images (from the repo)
cd ~/stack/bonito-repo
docker build -t bonito/collector:0.1.1 .
docker build -t bonito/store:0.1.1 bonito-store/
docker build -t bonito/api:0.1.2 bonito-api/
docker build -t bonito/mcp:0.1.2 bonito-mcp/

# 4. bonito + mlflow
docker compose --env-file ~/stack/.env -p bonito -f ~/stack/bonito/docker-compose.yml up -d
docker compose --env-file ~/stack/.env -p mlflow -f ~/stack/mlflow/docker-compose.yml up -d
```

## Expose (Cloudflare Tunnel)

`cloudflared` runs as a systemd service (`tunnel/docker-compose.yml` or
`cloudflared --config`) and maps `grafana.demo.sofe.dev` → `obs-grafana:3000`,
`api.bonito.sofe.dev` → `bonito-api:8100`, `mlflow.demo.sofe.dev` → `mlflow:5002`.

## Editing / adding services

Each project is a standalone compose file — edit it, `docker compose -p <proj> up -d`
again. New DBs = add a service to `dbs/docker-compose.yml`. New exporters = add a
scrape target to `obs/prometheus.yml` and restart `obs`.