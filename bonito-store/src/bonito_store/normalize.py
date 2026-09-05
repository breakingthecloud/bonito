"""Fingerprint normalization (BON-002 deliverable 3).

Same query text normalizes to the same fingerprint regardless of whitespace
and keyword casing. If the collector already supplies a fingerprint (the
Postgres ``queryid``), it takes precedence; this module is the fallback.
"""
from __future__ import annotations

import hashlib


def minify_sql(query: str) -> str:
    """Collapse whitespace and lowercase the query text."""
    return " ".join(query.split()).lower()


def fingerprint_of(query: str) -> str:
    """sha256 hex of the minified query — the dedupe key."""
    return hashlib.sha256(minify_sql(query).encode()).hexdigest()