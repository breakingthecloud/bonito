"""SQLite schema for bonito-store (BON-002 deliverable 1).

Timestamps are stored as ISO-8601 UTC text so retention pruning and baselines
are trivially comparable.
"""
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS query_texts (
    fingerprint TEXT PRIMARY KEY,
    query_text  TEXT NOT NULL,
    first_seen  TEXT NOT NULL,
    last_seen   TEXT NOT NULL,
    calls       INTEGER NOT NULL DEFAULT 0,
    avg_ms      REAL,
    max_ms      REAL
);

CREATE TABLE IF NOT EXISTS query_samples (
    fingerprint TEXT NOT NULL,
    ts          TEXT NOT NULL,
    calls       INTEGER,
    mean_ms     REAL,
    rows        INTEGER,
    PRIMARY KEY (fingerprint, ts)
);
CREATE INDEX IF NOT EXISTS idx_samples_ts ON query_samples (ts);

CREATE TABLE IF NOT EXISTS execution_plans (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    fingerprint TEXT NOT NULL,
    ts          TEXT NOT NULL,
    plan_json   TEXT,
    cost        REAL
);
CREATE INDEX IF NOT EXISTS idx_plans_fp_ts ON execution_plans (fingerprint, ts);

CREATE TABLE IF NOT EXISTS lock_events (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ts           TEXT NOT NULL,
    db_instance  TEXT,
    blocking_pid INTEGER,
    blocked_pids TEXT,
    lock_mode    TEXT,
    duration_s   REAL
);
CREATE INDEX IF NOT EXISTS idx_locks_ts ON lock_events (ts);

CREATE TABLE IF NOT EXISTS session_snapshots (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    ts             TEXT NOT NULL,
    pid            INTEGER,
    user           TEXT,
    database       TEXT,
    state          TEXT,
    wait_event_type TEXT,
    wait_event     TEXT,
    query_age_s    INTEGER,
    query          TEXT
);
CREATE INDEX IF NOT EXISTS idx_sessions_ts ON session_snapshots (ts);

CREATE TABLE IF NOT EXISTS table_stats (
    fingerprint     TEXT NOT NULL,
    ts              TEXT NOT NULL,
    seq_scan        INTEGER,
    idx_scan        INTEGER,
    live_rows       INTEGER,
    dead_rows       INTEGER,
    bloat_pct       REAL,
    last_autovacuum TEXT,
    PRIMARY KEY (fingerprint, ts)
);

CREATE TABLE IF NOT EXISTS change_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT NOT NULL DEFAULT (datetime('now')),
    change_type TEXT NOT NULL,
    entity      TEXT,
    detail      TEXT
);
"""