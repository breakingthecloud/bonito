"""Tests for bonito-mcp — pure helpers + integration against a real bonito-api app."""
import asyncio
from datetime import UTC, datetime

import httpx
import pytest
from bonito_api.app import create_app
from bonito_store.store import BonitoStore
from httpx import ASGITransport

from bonito_mcp.client import BonitoClient, truncate_text
from bonito_mcp.server import (
    build_blocking_tree,
    build_mcp,
    make_tools,
    suggest_remediation,
)

API_KEY = "test-key"
LONG_QUERY = "SELECT * FROM orders WHERE customer_id = %s AND status = %s " * 50


def sample_events() -> dict:
    return {
        "collected_at": datetime.now(UTC).isoformat(),
        "top_queries": [
            {
                "fingerprint": "-6842865755026457642",
                "calls": 1284,
                "total_ms": 15932.11,
                "mean_ms": 12.43,
                "max_ms": 841.02,
                "rows": 245680,
                "buffer_hit_ratio": 99.2,
                "query": LONG_QUERY,
            }
        ],
        "locks": [
            {
                "blocked_pid": 1412,
                "blocked_user": "app",
                "blocked_query": "UPDATE orders SET status='paid' WHERE id=$1",
                "blocking_pid": 1408,
                "blocking_user": "app",
                "blocking_query": "SELECT ... FOR UPDATE",
                "wait_event_type": "Lock",
                "wait_event": "transactionid",
            }
        ],
        "sessions": [
            {
                "pid": 1412,
                "user": "app",
                "database": "app",
                "state": "active",
                "wait_event_type": "Lock",
                "wait_event": "transactionid",
                "query_age_s": 42,
                "query": "UPDATE orders SET status='paid' WHERE id=$1",
            }
        ],
        "tables": [
            {
                "schema": "public",
                "table": "orders",
                "seq_scan": 1200,
                "idx_scan": 45800,
                "live_rows": 245680,
                "dead_rows": 10241,
                "bloat_pct": 4.2,
                "last_autovacuum": "2026-09-05T00:00:00+00:00",
            }
        ],
    }


@pytest.fixture()
def tools(tmp_path, monkeypatch):
    monkeypatch.setenv("BONITO_API_KEY", API_KEY)
    db = str(tmp_path / "mcp.db")
    store = BonitoStore(db)
    store.ingest(sample_events())
    store.ingest(
        {
            "plans": [
                {
                    "fingerprint": "-6842865755026457642",
                    "plan": {"Plan": {"Node Type": "Seq Scan", "Relation Name": "orders"}},
                    "cost": 42.0,
                }
            ]
        }
    )
    app = create_app(db)
    http = httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    client = BonitoClient(base_url="http://test", api_key=API_KEY, client=http)
    return make_tools(client)


# ── pure helpers ──────────────────────────────────────────────────────
def test_truncate_text():
    assert truncate_text("short") == "short"
    long = "x" * 1000
    assert len(truncate_text(long)) == 500
    assert truncate_text(None) is None


def test_build_blocking_tree():
    locks = [
        {"blocking_pid": 1408, "blocked_pids": "[1412, 1413]", "lock_mode": "transactionid"},
        {"blocking_pid": 1408, "blocked_pids": "[1414]", "lock_mode": "transactionid"},
        {"blocking_pid": 1412, "blocked_pids": "[1415]", "lock_mode": "tuple"},
    ]
    tree = build_blocking_tree(locks)
    assert tree["total_blocked"] == 4
    by_pid = {n["blocking_pid"]: n for n in tree["tree"]}
    assert by_pid[1408]["blocked_pids"] == [1412, 1413, 1414]


def test_suggest_remediation_rules():
    for key in ("slow_query", "lock", "blocking", "bloat", "wait_io", "wait_lock"):
        assert "advice" in suggest_remediation(key)
    out = suggest_remediation("lock", "blocking_pid=1408")
    assert "pg_terminate_backend" in out["advice"]
    assert out["context"] == "blocking_pid=1408"


# ── tools against a real bonito-api app ───────────────────────────────
def test_get_slow_queries(tools):
    out = asyncio.run(tools["get_slow_queries"](limit=5))
    q = out["queries"][0]
    assert q["fingerprint"] == "-6842865755026457642"
    assert len(q["query_text"]) == 500  # truncated (token governance)


def test_get_active_locks_and_tree(tools):
    locks = asyncio.run(tools["get_active_locks"]())["locks"]
    assert locks[0]["blocking_pid"] == 1408
    tree = asyncio.run(tools["get_blocking_tree"]())
    assert tree["total_blocked"] == 1
    assert tree["tree"][0]["blocked_pids"] == [1412]


def test_explain_query(tools):
    out = asyncio.run(tools["explain_query"](fingerprint="-6842865755026457642"))
    assert out["plan"]["plan"]["Plan"]["Node Type"] == "Seq Scan"  # parsed JSON


def test_get_wait_analysis(tools):
    waits = asyncio.run(tools["get_wait_analysis"]())["waits"]
    assert waits[0]["wait_event_type"] == "Lock"
    assert waits[0]["n"] == 1


def test_compare_to_baseline(tools):
    out = asyncio.run(tools["compare_to_baseline"](fingerprint="-6842865755026457642"))
    assert out["baseline"]["mean_ms"] == 12.43
    assert out["regression_pct"] == 0.0


def test_health_summary(tools):
    out = asyncio.run(tools["get_db_health_summary"]("app"))
    assert out["sessions_by_state"][0]["state"] == "active"
    assert out["top_bloat"][0]["fingerprint"] == "public.orders"


def test_server_registers_all_tools():
    from bonito_mcp.client import BonitoClient as C

    mcp = build_mcp(C("http://localhost:8100", "k"))
    assert sorted(t.name for t in asyncio.run(mcp.list_tools())) == sorted(
        [
            "get_slow_queries",
            "get_active_locks",
            "get_blocking_tree",
            "explain_query",
            "get_wait_analysis",
            "compare_to_baseline",
            "suggest_remediation",
            "get_db_health_summary",
        ]
    )