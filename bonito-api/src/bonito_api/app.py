"""bonito-api — FastAPI query layer (BON-003).

Contract public (``/openapi.json``, ``/docs``), deployment private (all data
endpoints require ``BONITO_API_KEY`` via ``X-API-Key`` or ``Bearer``).
"""
from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from typing import Any

from bonito_store.api import EventsIn
from bonito_store.store import BonitoStore
from fastapi import Depends, FastAPI, Header, HTTPException

from .db import ReadStore

DESCRIPTION = (
    "Bonito query layer. The OpenAPI contract is public; every data endpoint "
    "requires X-API-Key (BONITO_API_KEY). See bonito-api/openapi.yaml."
)


def _require_key(
    x_api_key: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
) -> bool:
    expected = os.environ.get("BONITO_API_KEY")
    if not expected:
        raise HTTPException(status_code=503, detail="BONITO_API_KEY not configured")
    provided = x_api_key
    if provided is None and authorization:
        provided = authorization.removeprefix("Bearer ").strip()
    if provided != expected:
        raise HTTPException(status_code=401, detail="invalid API key")
    return True


def _minutes_ago(minutes: int) -> str:
    return (datetime.now(UTC) - timedelta(minutes=minutes)).isoformat()


def create_app(db_path: str | None = None) -> FastAPI:
    db_path = db_path or os.environ.get("BONITO_DB", "bonito.db")
    store = ReadStore(db_path)
    write = BonitoStore(db_path)

    app = FastAPI(
        title="bonito-api",
        version="0.1.2",
        description=DESCRIPTION,
    )

    @app.get(
        "/queries/top",
        dependencies=[Depends(_require_key)],
        summary="Top queries by mean execution time",
    )
    def queries_top(
        db_instance: str = "default", period: str = "24h", limit: int = 20
    ) -> dict[str, Any]:
        rows = store.query(
            "SELECT fingerprint, query_text, calls, avg_ms, max_ms, "
            "first_seen, last_seen FROM query_texts "
            "ORDER BY avg_ms DESC NULLS LAST LIMIT ?",
            (min(limit, 100),),
        )
        return {"db_instance": db_instance, "period": period, "queries": rows}

    @app.get(
        "/locks/active",
        dependencies=[Depends(_require_key)],
        summary="Recent lock events / blocking pairs",
    )
    def locks_active(
        db_instance: str = "default", minutes: int = 10
    ) -> dict[str, Any]:
        rows = store.query(
            "SELECT ts, db_instance, blocking_pid, blocked_pids, lock_mode "
            "FROM lock_events WHERE ts >= ? ORDER BY ts DESC LIMIT 100",
            (_minutes_ago(minutes),),
        )
        return {"db_instance": db_instance, "window_minutes": minutes, "locks": rows}

    @app.get(
        "/waits",
        dependencies=[Depends(_require_key)],
        summary="Wait breakdown by wait_event_type",
    )
    def waits(db_instance: str = "default", minutes: int = 10) -> dict[str, Any]:
        rows = store.query(
            "SELECT wait_event_type, COUNT(*) AS n, SUM(query_age_s) AS total_age_s "
            "FROM session_snapshots WHERE ts >= ? AND wait_event_type IS NOT NULL "
            "GROUP BY wait_event_type ORDER BY n DESC",
            (_minutes_ago(minutes),),
        )
        return {"db_instance": db_instance, "window_minutes": minutes, "waits": rows}

    @app.get(
        "/plans/{fingerprint}",
        dependencies=[Depends(_require_key)],
        summary="Latest execution plan for a query",
    )
    def plans(fingerprint: str, db_instance: str = "default") -> dict[str, Any]:
        row = store.query(
            "SELECT fingerprint, ts, plan_json, cost FROM execution_plans "
            "WHERE fingerprint = ? ORDER BY ts DESC LIMIT 1",
            (fingerprint,),
        )
        if not row:
            raise HTTPException(status_code=404, detail="no plan for fingerprint")
        return {"db_instance": db_instance, "plan": row[0]}

    @app.get(
        "/health/{db_instance}",
        dependencies=[Depends(_require_key)],
        summary="Session + bloat summary for a database instance",
    )
    def health(db_instance: str, minutes: int = 10) -> dict[str, Any]:
        states = store.query(
            "SELECT state, COUNT(*) AS n FROM session_snapshots "
            "WHERE ts >= ? GROUP BY state",
            (_minutes_ago(minutes),),
        )
        top_bloat = store.query(
            "SELECT fingerprint, live_rows, dead_rows, bloat_pct FROM table_stats "
            "WHERE ts >= ? ORDER BY bloat_pct DESC LIMIT 5",
            (_minutes_ago(minutes),),
        )
        return {
            "db_instance": db_instance,
            "window_minutes": minutes,
            "sessions_by_state": states,
            "top_bloat": top_bloat,
        }

    @app.get(
        "/baseline/{fingerprint}",
        dependencies=[Depends(_require_key)],
        summary="Query vs its 7-day baseline (mean/p95 + regression)",
    )
    def baseline(fingerprint: str, db_instance: str = "default", days: int = 7) -> dict[str, Any]:
        bl = write.baselines(fingerprint, days)
        current = store.query(
            "SELECT avg_ms FROM query_texts WHERE fingerprint = ?", (fingerprint,)
        )
        row = bl[0] if bl else None
        cur_ms = current[0]["avg_ms"] if current else None
        regression = None
        if row and cur_ms is not None and row["mean_ms"]:
            regression = round(100.0 * (cur_ms - row["mean_ms"]) / row["mean_ms"], 1)
        return {
            "db_instance": db_instance,
            "fingerprint": fingerprint,
            "baseline": row,
            "current_avg_ms": cur_ms,
            "regression_pct": regression,
        }

    @app.post(
        "/ingest",
        dependencies=[Depends(_require_key)],
        summary="Compat webhook — same payload as store POST /events",
    )
    def ingest(events: EventsIn) -> dict[str, Any]:
        summary = write.ingest(events.model_dump(exclude_none=True))
        return {"status": "ok", **summary}

    return app