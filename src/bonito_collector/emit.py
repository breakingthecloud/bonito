"""Dual emission: Prometheus metrics (scrape) + JSON events (HTTP push).

BON-001 deliverable 7 · BON-006 metrics enrichment.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

import httpx
from prometheus_client import Counter as PromCounter
from prometheus_client import Gauge

# ── Prometheus metrics (labels kept low-cardinality) ──────────────────
# per top query (fingerprint) — BON-013: db_instance label
QUERY_MEAN_MS = Gauge(
    "bonito_query_mean_ms", "Mean execution time per top query (ms)", ["fingerprint", "db_instance"]
)
QUERY_CALLS = Gauge(
    "bonito_query_calls", "Total calls per top query", ["fingerprint", "db_instance"]
)
QUERY_MAX_MS = Gauge(
    "bonito_query_max_ms", "Max execution time per top query (ms)", ["fingerprint", "db_instance"]
)
QUERY_ROWS = Gauge(
    "bonito_query_rows", "Total rows returned per top query", ["fingerprint", "db_instance"]
)
QUERY_BUFFER_HIT_RATIO = Gauge(
    "bonito_query_buffer_hit_ratio", "Buffer hit ratio (0-100) per top query", ["fingerprint", "db_instance"]
)

# locks / sessions
BLOCKING_COUNT = Gauge("bonito_blocking_sessions", "Number of blocking session pairs", ["db_instance"])
ACTIVE_SESSIONS = Gauge("bonito_active_sessions", "Active (non-idle) sessions", ["db_instance"])
SESSIONS_BY_STATE = Gauge(
    "bonito_sessions_by_state", "Sessions by state", ["state", "db_instance"]
)
WAIT_EVENTS_TOTAL = Gauge(
    "bonito_wait_events_total", "Sessions waiting by event type", ["type", "db_instance"]
)
IDLE_IN_TRANSACTION = Gauge("bonito_idle_in_transaction", "Idle-in-transaction sessions", ["db_instance"])

# per table (schema.table)
TABLE_BLOAT_PCT = Gauge(
    "bonito_table_bloat_pct", "Dead-tuple bloat percentage per table", ["table", "db_instance"]
)
TABLE_LIVE_ROWS = Gauge("bonito_table_live_rows", "Live rows per table", ["table", "db_instance"])
TABLE_DEAD_ROWS = Gauge("bonito_table_dead_rows", "Dead rows per table", ["table", "db_instance"])
TABLE_SEQ_SCAN = Gauge("bonito_table_seq_scan", "Sequential scans per table", ["table", "db_instance"])
TABLE_IDX_SCAN = Gauge("bonito_table_idx_scan", "Index scans per table", ["table", "db_instance"])

# collector health
COLLECTOR_DURATION = Gauge(
    "bonito_collector_scrape_duration_seconds", "Seconds per collector run"
)
COLLECTOR_ERRORS = PromCounter(
    "bonito_collector_errors_total", "Collector loop errors (counter)"
)


def _set(gauge: Gauge, value: Any) -> None:
    if value is not None:
        gauge.set(float(value))


def export_prometheus(
    top_queries: list[dict[str, Any]],
    locks: list[dict[str, Any]],
    sessions: list[dict[str, Any]],
    tables: list[dict[str, Any]],
    db_instance: str = "default",
) -> None:
    """Update Prometheus gauges from collected data (BON-013: db_instance)."""
    for q in top_queries[:20]:
        fp = str(q.get("fingerprint"))
        _set(QUERY_MEAN_MS.labels(fingerprint=fp, db_instance=db_instance), q.get("mean_ms"))
        _set(QUERY_CALLS.labels(fingerprint=fp, db_instance=db_instance), q.get("calls"))
        _set(QUERY_MAX_MS.labels(fingerprint=fp, db_instance=db_instance), q.get("max_ms"))
        _set(QUERY_ROWS.labels(fingerprint=fp, db_instance=db_instance), q.get("rows"))
        _set(
            QUERY_BUFFER_HIT_RATIO.labels(fingerprint=fp, db_instance=db_instance),
            q.get("buffer_hit_ratio"),
        )

    BLOCKING_COUNT.labels(db_instance=db_instance).set(len(locks))
    ACTIVE_SESSIONS.labels(db_instance=db_instance).set(len(sessions))

    states = Counter(s.get("state") for s in sessions if s.get("state"))
    for state, count in states.items():
        SESSIONS_BY_STATE.labels(state=state, db_instance=db_instance).set(count)
    idle = sum(1 for s in sessions if s.get("state") == "idle in transaction")
    IDLE_IN_TRANSACTION.labels(db_instance=db_instance).set(idle)

    waits = Counter(
        s.get("wait_event_type") for s in sessions if s.get("wait_event_type")
    )
    for wtype, count in waits.items():
        WAIT_EVENTS_TOTAL.labels(type=wtype, db_instance=db_instance).set(count)

    for t in tables[:20]:
        table = f"{t.get('schema')}.{t.get('table')}"
        _set(TABLE_BLOAT_PCT.labels(table=table, db_instance=db_instance), t.get("bloat_pct"))
        _set(TABLE_LIVE_ROWS.labels(table=table, db_instance=db_instance), t.get("live_rows"))
        _set(TABLE_DEAD_ROWS.labels(table=table, db_instance=db_instance), t.get("dead_rows"))
        _set(TABLE_SEQ_SCAN.labels(table=table, db_instance=db_instance), t.get("seq_scan"))
        _set(TABLE_IDX_SCAN.labels(table=table, db_instance=db_instance), t.get("idx_scan"))


def record_scrape_duration(seconds: float) -> None:
    COLLECTOR_DURATION.set(seconds)


def record_collector_error() -> None:
    COLLECTOR_ERRORS.inc()


def push_events(store_url: str, events: dict[str, Any], timeout: float = 5.0) -> bool:
    """POST structured JSON events to bonito-store (or cloud). Non-fatal."""
    try:
        r = httpx.post(f"{store_url.rstrip('/')}/events", json=events, timeout=timeout)
        return r.status_code < 300
    except Exception:
        return False
