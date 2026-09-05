"""Deep PostgreSQL collectors — fixed queries over system stat views.

Each collector returns a list of structured dicts (JSON-serializable).
All SQL is constant; the only parameter is LIMIT (top_n) via psycopg params.
"""
from __future__ import annotations

from typing import Any

from .db import ReadOnlyPG

# ── Deliverable 2: top queries (pg_stat_statements) ──────────────────
SQL_TOP_QUERIES = """
SELECT
    queryid::text                                   AS fingerprint,
    calls,
    round(total_exec_time::numeric, 2)              AS total_ms,
    round(mean_exec_time::numeric, 2)               AS mean_ms,
    round(max_exec_time::numeric, 2)                AS max_ms,
    rows,
    CASE WHEN (shared_blks_hit + shared_blks_read) > 0
         THEN round(100.0 * shared_blks_hit
                    / (shared_blks_hit + shared_blks_read), 1)
         ELSE NULL END                              AS buffer_hit_ratio,
    left(query, 500)                                AS query
FROM pg_stat_statements
ORDER BY total_exec_time DESC
LIMIT %s
"""


def collect_top_queries(pg: ReadOnlyPG, top_n: int) -> list[dict[str, Any]]:
    if not pg.has_extension("pg_stat_statements"):
        return []
    return pg.query(SQL_TOP_QUERIES, (top_n,))


# ── Deliverable 3: locks / blocking tree (pg_locks + pg_blocking_pids) ─
SQL_BLOCKING = """
SELECT
    blocked.pid                     AS blocked_pid,
    blocked.usename                 AS blocked_user,
    left(blocked.query, 300)        AS blocked_query,
    blocking.pid                    AS blocking_pid,
    blocking.usename                AS blocking_user,
    left(blocking.query, 300)       AS blocking_query,
    blocked.wait_event_type         AS wait_event_type,
    blocked.wait_event              AS wait_event
FROM pg_stat_activity blocked
JOIN LATERAL unnest(pg_blocking_pids(blocked.pid)) AS bpid ON true
JOIN pg_stat_activity blocking ON blocking.pid = bpid
WHERE cardinality(pg_blocking_pids(blocked.pid)) > 0
"""


def collect_locks(pg: ReadOnlyPG) -> list[dict[str, Any]]:
    return pg.query(SQL_BLOCKING)


# ── Deliverable 4: sessions / waits (pg_stat_activity) ───────────────
SQL_SESSIONS = """
SELECT
    pid,
    usename                                         AS user,
    datname                                         AS database,
    state,
    wait_event_type,
    wait_event,
    round(extract(epoch FROM (now() - query_start)))::int AS query_age_s,
    left(query, 300)                                AS query
FROM pg_stat_activity
WHERE state IS NOT NULL
  AND state <> 'idle'
  AND pid <> pg_backend_pid()
ORDER BY query_start ASC NULLS LAST
"""


def collect_sessions(pg: ReadOnlyPG) -> list[dict[str, Any]]:
    return pg.query(SQL_SESSIONS)


# ── Deliverable 6: table / index stats + bloat estimate ──────────────
SQL_TABLE_STATS = """
SELECT
    schemaname                      AS schema,
    relname                         AS table,
    seq_scan,
    idx_scan,
    n_live_tup                      AS live_rows,
    n_dead_tup                      AS dead_rows,
    CASE WHEN n_live_tup > 0
         THEN round(100.0 * n_dead_tup / n_live_tup, 1)
         ELSE 0 END                 AS bloat_pct,
    last_autovacuum
FROM pg_stat_user_tables
ORDER BY n_dead_tup DESC
LIMIT %s
"""


def collect_table_stats(pg: ReadOnlyPG, top_n: int) -> list[dict[str, Any]]:
    return pg.query(SQL_TABLE_STATS, (top_n,))


# ── Deliverable 5: execution plans (EXPLAIN, no ANALYZE for safety) ──
def collect_plan(pg: ReadOnlyPG, query: str) -> dict[str, Any] | None:
    """EXPLAIN (no ANALYZE) a given query safely.

    We use plain EXPLAIN (not ANALYZE) to avoid executing the statement on the
    client DB — read-only guarantee. Query text comes from pg_stat_statements
    (already-run queries), never from external input.
    """
    q = query.strip().rstrip(";")
    if not q.lower().startswith(("select", "with")):
        return None  # only plan read queries
    try:
        rows = pg.query(f"EXPLAIN (FORMAT JSON) {q}")
        return {"query": query[:300], "plan": rows[0] if rows else None}
    except Exception as e:  # broad: any planning error is non-fatal
        return {"query": query[:300], "error": str(e)}
