-- Bonito v0.1.0 — read-only role for the collector.
-- Run as superuser (e.g. `docker exec -i bonito-db psql -U postgres -d app < this file`).
-- This is the ONLY role the collector should ever use.

CREATE ROLE bonito_ro LOGIN PASSWORD 'change-me';

-- Connect to the app database
GRANT CONNECT ON DATABASE app TO bonito_ro;

-- Read access to the application schema
GRANT USAGE ON SCHEMA public TO bonito_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO bonito_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO bonito_ro;

-- pg_monitor: SELECT on all system stat/activity views (pg_stat_activity,
-- pg_locks, pg_stat_user_tables, pg_stat_user_indexes, ...)
GRANT pg_monitor TO bonito_ro;

-- pg_stat_statements is NOT public-readable — grant it explicitly
GRANT SELECT ON pg_stat_statements TO bonito_ro;

-- Verify (as bonito_ro):
--   SET default_transaction_read_only = on;
--   SELECT count(*) FROM pg_stat_statements;
--   SELECT * FROM pg_stat_activity;