"""Read-only PostgreSQL connection base.

Golden rule: the collector NEVER writes to the client database and NEVER
builds SQL from client input — only fixed queries over system stat views.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

import psycopg
from psycopg.rows import dict_row


class ReadOnlyPG:
    """Thin wrapper enforcing read-only, parameterized-only access."""

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    @contextmanager
    def connect(self) -> Iterator[psycopg.Connection]:
        # read-only session; autocommit so we never hold write locks
        conn = psycopg.connect(self._dsn, autocommit=True, row_factory=dict_row)
        try:
            conn.execute("SET default_transaction_read_only = on")
            conn.execute("SET statement_timeout = '5s'")
            yield conn
        finally:
            conn.close()

    def query(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        """Run a FIXED query. `sql` must be a constant string in this codebase,
        never interpolated with client data. Values go through `params`."""
        with self.connect() as conn:
            cur = conn.execute(sql, params)
            return cur.fetchall()

    def has_extension(self, name: str) -> bool:
        rows = self.query(
            "SELECT 1 FROM pg_extension WHERE extname = %s", (name,)
        )
        return bool(rows)
