"""Persistence layer for bonito-store (SQLite).

BON-002 deliverables 2-6: ingest (POST /events), dedupe by fingerprint,
retention pruning and 7-day baselines.
"""
from __future__ import annotations

import json
import sqlite3
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .normalize import fingerprint_of
from .schema import SCHEMA_SQL

BATCH_LIMIT = 100
PRUNE_EVERY_S = 3600  # throttle automatic retention pruning


def _now() -> str:
    return datetime.now(UTC).isoformat()


def iso_days_ago(days: int) -> str:
    return (datetime.now(UTC) - timedelta(days=days)).isoformat()


class BonitoStore:
    """SQLite-backed event store. All writes go through fixed SQL."""

    def __init__(self, db_path: str | Path, retention_days: int = 7) -> None:
        self._path = str(db_path)
        self.retention_days = retention_days
        self._last_prune = 0.0
        if self._path != ":memory:":
            Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as conn:
            conn.executescript(SCHEMA_SQL)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        return conn

    # ── ingest (deliverable 2) ─────────────────────────────────────────
    def ingest(self, events: dict[str, Any]) -> dict[str, int]:
        """Persist one collector snapshot. Batch capped at BATCH_LIMIT/type."""
        now = events.get("collected_at") or _now()
        summary = {
            "top_queries": 0,
            "locks": 0,
            "sessions": 0,
            "tables": 0,
            "plans": 0,
            "new_fingerprints": 0,
        }
        with self._conn() as conn:
            for q in events.get("top_queries", [])[:BATCH_LIMIT]:
                self._upsert_query(conn, q, now, summary)
            for lock in events.get("locks", [])[:BATCH_LIMIT]:
                self._insert_lock(conn, lock, now)
                summary["locks"] += 1
            for sess in events.get("sessions", [])[:BATCH_LIMIT]:
                self._insert_session(conn, sess, now)
                summary["sessions"] += 1
            for t in events.get("tables", [])[:BATCH_LIMIT]:
                self._insert_table(conn, t, now)
                summary["tables"] += 1
            for p in events.get("plans", [])[:BATCH_LIMIT]:
                self._insert_plan(conn, p, now)
                summary["plans"] += 1
        self._maybe_prune()
        return summary

    def _upsert_query(
        self,
        conn: sqlite3.Connection,
        q: dict[str, Any],
        now: str,
        summary: dict[str, int],
    ) -> None:
        fingerprint = q.get("fingerprint") or fingerprint_of(q.get("query", ""))
        query_text = (q.get("query") or "")[:4000]
        calls = q.get("calls", 0)
        if conn.execute(
            "SELECT 1 FROM query_texts WHERE fingerprint = ?", (fingerprint,)
        ).fetchone() is None:
            conn.execute(
                "INSERT INTO query_texts "
                "(fingerprint, query_text, first_seen, last_seen, calls, avg_ms, max_ms) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (fingerprint, query_text, now, now, calls, q.get("mean_ms"), q.get("max_ms")),
            )
            conn.execute(
                "INSERT INTO change_history (change_type, entity, detail) "
                "VALUES ('fingerprint_new', ?, ?)",
                (fingerprint, query_text[:200]),
            )
            summary["new_fingerprints"] += 1
        else:
            conn.execute(
                "UPDATE query_texts SET last_seen = ?, calls = ?, avg_ms = ?, max_ms = ? "
                "WHERE fingerprint = ?",
                (now, calls, q.get("mean_ms"), q.get("max_ms"), fingerprint),
            )
        conn.execute(
            "INSERT OR REPLACE INTO query_samples (fingerprint, ts, calls, mean_ms, rows) "
            "VALUES (?, ?, ?, ?, ?)",
            (fingerprint, now, calls, q.get("mean_ms"), q.get("rows")),
        )
        summary["top_queries"] += 1

    def _insert_lock(self, conn: sqlite3.Connection, lock: dict[str, Any], now: str) -> None:
        conn.execute(
            "INSERT INTO lock_events "
            "(ts, db_instance, blocking_pid, blocked_pids, lock_mode, duration_s) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                now,
                lock.get("database"),
                lock.get("blocking_pid"),
                json.dumps([lock["blocked_pid"]]) if lock.get("blocked_pid") else None,
                lock.get("lock_mode") or lock.get("wait_event"),
                lock.get("duration_s"),
            ),
        )

    def _insert_session(
        self, conn: sqlite3.Connection, sess: dict[str, Any], now: str
    ) -> None:
        conn.execute(
            "INSERT INTO session_snapshots "
            "(ts, pid, user, database, state, wait_event_type, wait_event, query_age_s, query) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                now,
                sess.get("pid"),
                sess.get("user"),
                sess.get("database"),
                sess.get("state"),
                sess.get("wait_event_type"),
                sess.get("wait_event"),
                sess.get("query_age_s"),
                (sess.get("query") or "")[:2000],
            ),
        )

    def _insert_table(self, conn: sqlite3.Connection, t: dict[str, Any], now: str) -> None:
        conn.execute(
            "INSERT OR REPLACE INTO table_stats "
            "(fingerprint, ts, seq_scan, idx_scan, live_rows, dead_rows, bloat_pct, last_autovacuum) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                f"{t.get('schema')}.{t.get('table')}",
                now,
                t.get("seq_scan"),
                t.get("idx_scan"),
                t.get("live_rows"),
                t.get("dead_rows"),
                t.get("bloat_pct"),
                t.get("last_autovacuum"),
            ),
        )

    def _insert_plan(self, conn: sqlite3.Connection, p: dict[str, Any], now: str) -> None:
        plan = p.get("plan")
        conn.execute(
            "INSERT INTO execution_plans (fingerprint, ts, plan_json, cost) "
            "VALUES (?, ?, ?, ?)",
            (
                p.get("fingerprint") or fingerprint_of(p.get("query", "")),
                now,
                json.dumps(plan) if plan is not None else None,
                p.get("cost"),
            ),
        )

    # ── baselines (deliverable 5) ──────────────────────────────────────
    def baselines(
        self, fingerprint: str | None = None, days: int | None = None
    ) -> list[dict[str, Any]]:
        """7-day rolling mean + p95 per fingerprint, computed from samples."""
        days = days or self.retention_days
        where = "WHERE ts >= ?"
        params: list[Any] = [iso_days_ago(days)]
        if fingerprint:
            where += " AND fingerprint = ?"
            params.append(fingerprint)
        with self._conn() as conn:
            rows = conn.execute(
                f"SELECT fingerprint, mean_ms FROM query_samples {where} ORDER BY fingerprint",
                params,
            ).fetchall()
        grouped: dict[str, list[float]] = {}
        for r in rows:
            if r["mean_ms"] is not None:
                grouped.setdefault(r["fingerprint"], []).append(float(r["mean_ms"]))
        out: list[dict[str, Any]] = []
        for fp, vals in grouped.items():
            vals.sort()
            p95 = vals[int(0.95 * (len(vals) - 1))]
            out.append(
                {
                    "fingerprint": fp,
                    "samples": len(vals),
                    "mean_ms": round(sum(vals) / len(vals), 2),
                    "p95_ms": round(p95, 2),
                }
            )
        return out

    # ── retention pruning (deliverable 4) ──────────────────────────────
    def prune(self, days: int | None = None) -> dict[str, int]:
        days = days or self.retention_days
        cutoff = iso_days_ago(days)
        removed: dict[str, int] = {}
        with self._conn() as conn:
            for table in (
                "query_samples",
                "execution_plans",
                "lock_events",
                "session_snapshots",
                "table_stats",
            ):
                cur = conn.execute(f"DELETE FROM {table} WHERE ts < ?", (cutoff,))
                removed[table] = cur.rowcount
            conn.execute(
                "INSERT INTO change_history (change_type, entity, detail) "
                "VALUES ('retention_prune', 'all', ?)",
                (f"pruned older than {cutoff}",),
            )
        self._last_prune = time.time()
        return removed

    def _maybe_prune(self) -> None:
        if time.time() - self._last_prune > PRUNE_EVERY_S:
            self.prune()