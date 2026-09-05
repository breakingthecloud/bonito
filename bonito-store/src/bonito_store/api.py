"""FastAPI app — POST /events receiver + baseline reads (BON-002 deliverables 2, 5)."""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

from .store import BATCH_LIMIT, BonitoStore


class EventsIn(BaseModel):
    """One collector snapshot. Optional fields match the collector payload."""

    collected_at: str | None = None
    top_queries: list[dict[str, Any]] = Field(default_factory=list)
    locks: list[dict[str, Any]] = Field(default_factory=list)
    sessions: list[dict[str, Any]] = Field(default_factory=list)
    tables: list[dict[str, Any]] = Field(default_factory=list)
    plans: list[dict[str, Any]] = Field(default_factory=list)


class PlansIn(BaseModel):
    plans: list[dict[str, Any]] = Field(default_factory=list)


def create_app(db_path: str, retention_days: int = 7) -> FastAPI:
    store = BonitoStore(db_path, retention_days)

    app = FastAPI(title="bonito-store", version="0.1.0")

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

    app.state.store = store
    app.state.batch_limit = BATCH_LIMIT
    return app