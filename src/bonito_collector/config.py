"""Configuration for the Bonito collector.

Read-only by design. Supports single-instance (``BONITO_DSN``) and
multi-instance (``BONITO_INSTANCES`` JSON) modes (BON-013).
"""
from __future__ import annotations

import json
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
class Instance:
    """One monitored database."""

    name: str
    engine: str = "postgresql"
    dsn: str = ""


@dataclass
class CollectorConfig:
    """Collector configuration.

    instances: one or more monitored databases (BON-013 multi-instance).
    top_n: number of top queries to fetch per instance.
    store_url: optional HTTP endpoint to POST JSON events (bonito-store).
    prometheus_port: port to expose /metrics for scraping.
    otlp_endpoint: optional OTLP endpoint for trace spans (bonito-collector).
    intervals: per-type scrape frequency in seconds.
    """

    instances: list[Instance]
    top_n: int = 20
    store_url: str | None = None
    prometheus_port: int = 9187
    otlp_endpoint: str | None = None
    intervals: dict[str, int] = field(default_factory=lambda: dict(DEFAULT_INTERVALS))

    @property
    def dsn(self) -> str:
        """Backward-compatible accessor for the single-instance DSN."""
        return self.instances[0].dsn if self.instances else ""

    @classmethod
    def from_env(cls) -> CollectorConfig:
        top_n = int(os.environ.get("BONITO_TOP_N", "20"))
        store_url = os.environ.get("BONITO_STORE_URL") or None
        prometheus_port = int(os.environ.get("BONITO_PROM_PORT", "9187"))
        otlp_endpoint = os.environ.get("BONITO_OTLP_ENDPOINT") or None

        raw = os.environ.get("BONITO_INSTANCES")
        if raw:
            data = json.loads(raw)
            instances = [
                Instance(name=item["name"], engine=item.get("engine", "postgresql"), dsn=item["dsn"])
                for item in data
            ]
        else:
            dsn = os.environ.get("BONITO_DSN")
            if not dsn:
                raise ValueError(
                    "BONITO_DSN is required (or BONITO_INSTANCES for multi-instance)"
                )
            instances = [Instance(name="default", engine="postgresql", dsn=dsn)]

        return cls(
            instances=instances,
            top_n=top_n,
            store_url=store_url,
            prometheus_port=prometheus_port,
            otlp_endpoint=otlp_endpoint,
        )