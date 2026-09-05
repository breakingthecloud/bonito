"""Dual emission: Prometheus metrics (scrape) + JSON events (HTTP push).

BON-001 deliverable 7.
"""
from __future__ import annotations

from typing import Any

import httpx
from prometheus_client import Gauge

# Prometheus gauges (labels kept low-cardinality)
QUERY_MEAN_MS = Gauge(
    "bonito_query_mean_ms", "Mean execution time per top query (ms)", ["fingerprint"]
)
BLOCKING_COUNT = Gauge(
    "bonito_blocking_sessions", "Number of blocking session pairs"
)
ACTIVE_SESSIONS = Gauge(
    "bonito_active_sessions", "Active (non-idle) sessions"
)
TABLE_BLOAT_PCT = Gauge(
    "bonito_table_bloat_pct", "Dead-tuple bloat percentage per table", ["table"]
)


def export_prometheus(
    top_queries: list[dict[str, Any]],
    locks: list[dict[str, Any]],
    sessions: list[dict[str, Any]],
    tables: list[dict[str, Any]],
) -> None:
    """Update Prometheus gauges from collected data."""
    for q in top_queries[:20]:
        if q.get("mean_ms") is not None:
            QUERY_MEAN_MS.labels(fingerprint=str(q["fingerprint"])).set(float(q["mean_ms"]))
    BLOCKING_COUNT.set(len(locks))
    ACTIVE_SESSIONS.set(len(sessions))
    for t in tables[:20]:
        TABLE_BLOAT_PCT.labels(table=f"{t['schema']}.{t['table']}").set(float(t["bloat_pct"]))


def push_events(store_url: str, events: dict[str, Any], timeout: float = 5.0) -> bool:
    """POST structured JSON events to bonito-store (or cloud). Non-fatal."""
    try:
        r = httpx.post(f"{store_url.rstrip('/')}/events", json=events, timeout=timeout)
        return r.status_code < 300
    except Exception:
        return False
