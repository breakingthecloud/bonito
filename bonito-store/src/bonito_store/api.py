"""FastAPI app — POST /events receiver + baseline/anomaly reads (BON-002, BON-014)."""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, Gauge, generate_latest
from pydantic import BaseModel, Field

from .store import BATCH_LIMIT, BonitoStore

_REGRESSION = Gauge("bonito_query_regression_pct", "Regression % vs 7-day baseline", ["fingerprint"])
_ANOMALY = Gauge("bonito_query_anomaly", "Anomaly flag (1=regression) per fingerprint", ["fingerprint"])


class EventsIn(BaseModel):
    """One collector snapshot. Optional fields match the collector payload."""

    collected_at: str | None = None
    db_instance: str | None = None
    top_queries: list[dict[str, Any]] = Field(default_factory=list)
    locks: list[dict[str, Any]] = Field(default_factory=list)
    sessions: list[dict[str, Any]] = Field(default_factory=list)
    tables: list[dict[str, Any]] = Field(default_factory=list)
    plans: list[dict[str, Any]] = Field(default_factory=list)


class PlansIn(BaseModel):
    plans: list[dict[str, Any]] = Field(default_factory=list)


def create_app(db_path: str, retention_days: int = 7) -> FastAPI:
    store = BonitoStore(db_path, retention_days)

    app = FastAPI(title="bonito-store", version="0.2.0")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/events")
    def ingest(events: EventsIn) -> dict[str, Any]:
        summary = store.ingest(events.model_dump(exclude_none=True))
        return {"status": "ok", **summary}

    @app.post("/plans")
    def plans(payload: PlansIn) -> dict[str, Any]:
        summary = store.ingest({"plans": payload.plans})
        return {"status": "ok", **summary}

    @app.get("/baselines")
    def baselines(fingerprint: str | None = None, days: int | None = None) -> dict[str, Any]:
        return {"baselines": store.baselines(fingerprint, days or retention_days)}

    @app.get("/baseline/{fingerprint}")
    def baseline(fingerprint: str, days: int | None = None) -> dict[str, Any]:
        baseline_rows = store.baselines(fingerprint, days or retention_days)
        verdict = store.anomaly(fingerprint, days or retention_days)
        return {
            "fingerprint": fingerprint,
            "baseline": baseline_rows[0] if baseline_rows else None,
            "anomaly": verdict,
        }

    @app.get("/anomalies")
    def anomalies(days: int | None = None) -> dict[str, Any]:
        return {"anomalies": store.anomalies(days or retention_days)}

    @app.get("/metrics")
    def metrics() -> Response:
        for a in store.anomalies(retention_days):
            _REGRESSION.labels(fingerprint=a["fingerprint"]).set(a["regression_pct"])
            _ANOMALY.labels(fingerprint=a["fingerprint"]).set(1 if a["status"] == "regression" else 0)
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    app.state.store = store
    app.state.batch_limit = BATCH_LIMIT
    return app