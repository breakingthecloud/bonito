"""Bonito collector CLI — runs the scrape loop with per-type intervals."""
from __future__ import annotations

import argparse
import time
from datetime import datetime, timezone

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
from .emit import export_prometheus, push_events


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_once(cfg: CollectorConfig, pg: ReadOnlyPG) -> dict:
    """Collect one full snapshot and emit it. Returns the event payload."""
    top = collect_top_queries(pg, cfg.top_n)
    locks = collect_locks(pg)
    sessions = collect_sessions(pg)
    tables = collect_table_stats(pg, cfg.top_n)

    export_prometheus(top, locks, sessions, tables)

    events = {
        "collected_at": _now(),
        "top_queries": top,
        "locks": locks,
        "sessions": sessions,
        "tables": tables,
    }
    if cfg.store_url:
        push_events(cfg.store_url, events)
    return events


def main() -> int:
    ap = argparse.ArgumentParser(prog="bonito-collector", description="Deep PostgreSQL observability collector")
    ap.add_argument("--once", action="store_true", help="collect once and exit (no loop)")
    ap.add_argument("--version", action="version", version=f"bonito-collector {__version__}")
    args = ap.parse_args()

    cfg = CollectorConfig.from_env()
    pg = ReadOnlyPG(cfg.dsn)

    if args.once:
        events = run_once(cfg, pg)
        print(f"[{events['collected_at']}] "
              f"queries={len(events['top_queries'])} "
              f"locks={len(events['locks'])} "
              f"sessions={len(events['sessions'])} "
              f"tables={len(events['tables'])}")
        return 0

    start_http_server(cfg.prometheus_port)
    print(f"bonito-collector {__version__} — Prometheus on :{cfg.prometheus_port}/metrics")
    interval = min(cfg.intervals.values())  # loop at the fastest cadence
    while True:
        try:
            run_once(cfg, pg)
        except Exception as e:  # never crash the loop
            print(f"[{_now()}] collect error: {e}")
        time.sleep(interval)


if __name__ == "__main__":
    raise SystemExit(main())
