#!/usr/bin/env bash
# Bonito demo tenant — synthetic DB activity + blocking scenario.
# Makes the Grafana "Deep DB View" panels (sessions, blocking, waits, idle-in-tx,
# query calls) show real action on the demo PostgreSQL.
#
# Usage (on the Lightsail host):
#   bash ~/stack/scripts/generate-load.sh
#
# What it launches:
#   1. an idle-in-transaction session that holds a row lock (orders.id=1) ~10 min
#   2. an updater blocked on that lock -> blocking pair + wait event (Lock/tuple)
#   3. a background load loop (queries every 3s) so top-query calls keep growing
set -euo pipefail

PG="postgresql://postgres:postgres@dbs-postgres:5432/app"

echo "== idle-in-transaction holder (row lock on orders.id=1, ~10 min) =="
docker exec -d bonito-collector python -c "import psycopg,time; c=psycopg.connect('$PG'); c.autocommit=False; c.execute('UPDATE orders SET status=%s WHERE id=1', ('held',)); c.execute('SELECT 1'); time.sleep(600)" || echo "  (holder already running — skip)"

sleep 1

echo "== blocked updater (waits on the row lock) =="
docker exec -d bonito-collector python -c "import psycopg; c=psycopg.connect('$PG'); c.autocommit=True; c.execute('UPDATE orders SET status=%s WHERE id=1', ('stuck',))" || echo "  (blocked updater already running — skip)"

echo "== load loop (queries every 3s, background) =="
nohup bash -c 'while true; do
  docker exec dbs-postgres psql -U postgres -d app -qc "SELECT count(*) FROM orders WHERE amount > (random()*500);" >/dev/null 2>&1
  docker exec dbs-postgres psql -U postgres -d app -qc "SELECT avg(amount) FROM orders a JOIN orders b ON a.customer_id=b.customer_id WHERE a.status='"'"'paid'"'"';" >/dev/null 2>&1
  sleep 3
done' > /tmp/bonito-load.log 2>&1 &

echo "done. Wait ~40s and check https://grafana-demo.sofe.dev (sessions/blocking/waits) and https://prometheus-demo.sofe.dev"