"""Configuration for the Bonito PostgreSQL collector.

Read-only by design. All scrape frequencies are per collector type.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field


# Scrape intervals in seconds, per collector type (BON-001 deliverable 8)
DEFAULT_INTERVALS: dict[str, int] = {
    "metrics": 15,   # lightweight numeric metrics
    "queries": 60,   # pg_stat_statements top queries
    "locks": 30,     # blocking tree
    "sessions": 30,  # active sessions / waits
    "plans": 300,    # EXPLAIN ANALYZE (expensive → infrequent)
    "tables": 300,   # table/index stats + bloat
}


@dataclass
class CollectorConfig:
    """Collector configuration.

    dsn: read-only PostgreSQL connection string.
    top_n: number of top queries to fetch from pg_stat_statements.
    store_url: optional HTTP endpoint to POST JSON events (bonito-store).
    prometheus_port: port to expose /metrics for scraping.
    intervals: per-type scrape frequency in seconds.
    """

    dsn: str
    top_n: int = 20
    store_url: str | None = None
    prometheus_port: int = 9187
    intervals: dict[str, int] = field(default_factory=lambda: dict(DEFAULT_INTERVALS))

    @classmethod
    def from_env(cls) -> "CollectorConfig":
        dsn = os.environ.get("BONITO_DSN")
        if not dsn:
            raise ValueError(
                "BONITO_DSN is required (read-only PostgreSQL connection string)"
            )
        return cls(
            dsn=dsn,
            top_n=int(os.environ.get("BONITO_TOP_N", "20")),
            store_url=os.environ.get("BONITO_STORE_URL") or None,
            prometheus_port=int(os.environ.get("BONITO_PROM_PORT", "9187")),
        )
