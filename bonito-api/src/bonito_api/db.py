"""Read-only access to the bonito-store SQLite file (same schema)."""
from __future__ import annotations

import sqlite3
from typing import Any


class ReadStore:
    """Opens the store DB read-only (uri mode=ro) and returns dict rows."""

    def __init__(self, path: str) -> None:
        self._path = path

    def query(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        conn = sqlite3.connect(f"file:{self._path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]
        finally:
            conn.close()