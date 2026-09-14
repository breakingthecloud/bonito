-- Bonito demo tenant — postgres fixture (docker-entrypoint-initdb.d)
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

CREATE TABLE IF NOT EXISTS orders (
    id          serial PRIMARY KEY,
    customer_id int NOT NULL,
    status      text NOT NULL DEFAULT 'pending',
    amount      numeric(10, 2) NOT NULL DEFAULT 0
);

INSERT INTO orders (customer_id, status, amount)
SELECT (random() * 1000)::int, 'paid', (random() * 500)::numeric(10, 2)
FROM generate_series(1, 10000);

-- read-only collector role
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'bonito_ro') THEN
        CREATE ROLE bonito_ro LOGIN PASSWORD 'bonito';
    END IF;
END $$;

GRANT CONNECT ON DATABASE app TO bonito_ro;
GRANT USAGE ON SCHEMA public TO bonito_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO bonito_ro;
GRANT pg_monitor TO bonito_ro;
GRANT SELECT ON pg_stat_statements TO bonito_ro;