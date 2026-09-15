"""Bonito collector CLI — runs the scrape loop with per-type intervals.

BON-013: multi-instance runner — one collector, N monitored databases,
each tagged with its ``db_instance`` name in metrics/events/spans.
"""
from __future__ import annotations

import argparse
import time
from datetime import UTC, datetime

from prometheus_client import start_http_server

from . import __version__
from .collectors import (
    collect_locks,
    collect_sessions,
    collect_table_stats,
    collect_top_queries,
)
from .config import CollectorConfig
from .db import ReadOnlyPG
from .emit import (
    export_prometheus,
    push_events,
    record_collector_error,
    record_scrape_duration,
)
from .traces import emit_lock_span, emit_query_span, init_otlp


def _now() -> str:
    return datetime.now(UTC).isoformat()


def run_instance(cfg: CollectorConfig, name: str, dsn: str) -> dict:
    """Collect one full snapshot for a single instance and emit it."""
    pg = ReadOnlyPG(dsn)
    top = collect_top_queries(pg, cfg.top_n)
    locks = collect_locks(pg)
    sessions = collect_sessions(pg)
    tables = collect_table_stats(pg, cfg.top_n)

    export_prometheus(top, locks, sessions, tables, db_instance=name)

    for q in top[:10]:
        emit_query_span(
            fingerprint=q.get("fingerprint", ""),
            query_text=q.get("query", ""),
            mean_ms=q.get("mean_ms"),
            max_ms=q.get("max_ms"),
            calls=q.get("calls"),
            rows=q.get("rows"),
            buffer_hit_ratio=q.get("buffer_hit_ratio"),
            db_instance=name,
        )
    for lock in locks:
        emit_lock_span(
            blocked_pid=lock.get("blocked_pid"),
            blocking_pid=lock.get("blocking_pid"),
            wait_event_type=lock.get("wait_event_type"),
            wait_event=lock.get("wait_event"),
            db_instance=name,
        )

    events = {
        "collected_at": _now(),
        "db_instance": name,
        "top_queries": top,
        "locks": locks,
        "sessions": sessions,
        "tables": tables,
    }
    if cfg.store_url:
        push_events(cfg.store_url, events)
    return events


def run_once(cfg: CollectorConfig) -> list[dict]:
    """Collect one snapshot for every configured instance."""
    return [run_instance(cfg, inst.name, inst.dsn) for inst in cfg.instances]


def main() -> int:
    ap = argparse.ArgumentParser(prog="bonito-collector", description="Deep PostgreSQL observability collector")
    ap.add_argument("--once", action="store_true", help="collect once and exit (no loop)")
    ap.add_argument("--version", action="version", version=f"bonito-collector {__version__}")
    args = ap.parse_args()

    cfg = CollectorConfig.from_env()
    init_otlp(cfg.otlp_endpoint)

    if args.once:
        for ev in run_once(cfg):
            print(f"[{ev['collected_at']}] {ev['db_instance']}: "
                  f"queries={len(ev['top_queries'])} "
                  f"locks={len(ev['locks'])} "
                  f"sessions={len(ev['sessions'])} "
                  f"tables={len(ev['tables'])}")
        return 0

    start_http_server(cfg.prometheus_port)
    print(f"bonito-collector {__version__} — Prometheus on :{cfg.prometheus_port}/metrics "
          f"({len(cfg.instances)} instance(s))")
    interval = min(cfg.intervals.values())  # loop at the fastest cadence
    while True:
        started = time.monotonic()
        try:
            run_once(cfg)
        except Exception as e:  # never crash the loop
            record_collector_error()
            print(f"[{_now()}] collect error: {e}")
        record_scrape_duration(time.monotonic() - started)
        time.sleep(interval)


if __name__ == "__main__":
    raise SystemExit(main())