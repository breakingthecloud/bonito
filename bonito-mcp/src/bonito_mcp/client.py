"""Thin HTTP client over the bonito-api REST layer (BON-004)."""
from __future__ import annotations

import json
import os
from typing import Any

import httpx

MAX_QUERY_TEXT = 500


def truncate_text(text: str | None, limit: int = MAX_QUERY_TEXT) -> str | None:
    if text is None:
        return None
    return text if len(text) <= limit else text[: limit - 3] + "..."


class BonitoClient:
    """Talks to bonito-api (async). Token governance: query_text is truncated."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._client = client

    @classmethod
    def from_env(cls) -> BonitoClient:
        return cls(
            base_url=os.environ.get("BONITO_API_URL", "http://localhost:8100"),
            api_key=os.environ.get("BONITO_API_KEY", ""),
        )

    def _headers(self) -> dict[str, str]:
        return {"X-API-Key": self._api_key} if self._api_key else {}

    async def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        if self._client is None:
            self._client = httpx.AsyncClient(base_url=self._base_url)
        r = await self._client.get(path, params=params, headers=self._headers())
        r.raise_for_status()
        return r.json()

    async def top_queries(
        self, db_instance: str = "default", period: str = "24h", limit: int = 10
    ) -> dict[str, Any]:
        data = await self._get(
            "/queries/top",
            {"db_instance": db_instance, "period": period, "limit": limit},
        )
        for q in data.get("queries", []):
            q["query_text"] = truncate_text(q.get("query_text"))
        return data

    async def active_locks(
        self, db_instance: str = "default", minutes: int = 10
    ) -> dict[str, Any]:
        return await self._get(
            "/locks/active", {"db_instance": db_instance, "minutes": minutes}
        )

    async def waits(
        self, db_instance: str = "default", minutes: int = 10
    ) -> dict[str, Any]:
        return await self._get("/waits", {"db_instance": db_instance, "minutes": minutes})

    async def plan(self, fingerprint: str, db_instance: str = "default") -> dict[str, Any]:
        data = await self._get(f"/plans/{fingerprint}", {"db_instance": db_instance})
        plan = data.get("plan")
        if plan and plan.get("plan_json"):
            try:
                plan["plan"] = json.loads(plan["plan_json"])
            except json.JSONDecodeError:
                pass
        return data

    async def health(self, db_instance: str, minutes: int = 10) -> dict[str, Any]:
        return await self._get(f"/health/{db_instance}", {"minutes": minutes})

    async def baseline(
        self, fingerprint: str, db_instance: str = "default", days: int = 7
    ) -> dict[str, Any]:
        return await self._get(
            f"/baseline/{fingerprint}",
            {"db_instance": db_instance, "days": days},
        )