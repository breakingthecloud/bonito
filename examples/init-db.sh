#!/bin/bash
# Bonito v0.1.0 — runs on first container boot (docker-entrypoint-initdb.d).
# Enables pg_stat_statements and seeds a tiny sample table so the collector
# has something to report. For a real database, apply only the CREATE EXTENSION
# line (and use examples/readonly-role.sql for the collector role).
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

    CREATE TABLE IF NOT EXISTS orders (
        id           serial PRIMARY KEY,
        customer_id  int NOT NULL,
        status       text NOT NULL DEFAULT 'pending',
        amount       numeric(10, 2) NOT NULL DEFAULT 0
    );
    INSERT INTO orders (customer_id, status, amount)
    SELECT (random() * 1000)::int, 'paid', (random() * 500)::numeric(10, 2)
    FROM generate_series(1, 10000);
EOSQL