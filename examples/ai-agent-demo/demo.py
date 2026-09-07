"""Bonito AI-agent demo — diagnose a synthetic deadlock using the MCP tools.

Runs the exact tools an AI agent would call (get_active_locks →
get_blocking_tree → suggest_remediation → get_slow_queries →
compare_to_baseline) against a real in-process bonito-api + store, and prints
a narrated transcript. No live database or LLM needed.

Usage:
    python examples/ai-agent-demo/demo.py
"""
from __future__ import annotations

import asyncio
import json
import os
import tempfile
from datetime import UTC, datetime

from bonito_api.app import create_app
from bonito_mcp.client import BonitoClient
from bonito_mcp.server import make_tools
from bonito_store.store import BonitoStore
from httpx import ASGITransport, AsyncClient

FINGERPRINT = "-6842865755026457642"


def _seed(store: BonitoStore) -> None:
    now = datetime.now(UTC).isoformat()
    store.ingest(
        {
            "collected_at": now,
            "top_queries": [
                {
                    "fingerprint": FINGERPRINT,
                    "calls": 1284,
                    "total_ms": 15932.11,
                    "mean_ms": 12.43,
                    "max_ms": 841.02,
                    "rows": 245680,
                    "buffer_hit_ratio": 99.2,
                    "query": "SELECT * FROM orders WHERE customer_id = $1",
                },
                {
                    "fingerprint": "xyz987",
                    "calls": 88,
                    "total_ms": 88000,
                    "mean_ms": 1000.0,
                    "max_ms": 4200.0,
                    "rows": 1200000,
                    "buffer_hit_ratio": 40.1,
                    "query": "SELECT * FROM orders JOIN line_items ON ... WHERE status=$1",
                },
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
                },
                {
                    "blocked_pid": 1413,
                    "blocked_user": "app",
                    "blocked_query": "UPDATE orders SET amount=$1 WHERE id=$2",
                    "blocking_pid": 1412,
                    "blocking_user": "app",
                    "blocking_query": "UPDATE orders SET status='paid' WHERE id=$1",
                    "wait_event_type": "Lock",
                    "wait_event": "tuple",
                },
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
                },
                {
                    "pid": 1413,
                    "user": "app",
                    "database": "app",
                    "state": "active",
                    "wait_event_type": "Lock",
                    "wait_event": "tuple",
                    "query_age_s": 15,
                    "query": "UPDATE orders SET amount=$1 WHERE id=$2",
                },
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
                    "last_autovacuum": now,
                }
            ],
        }
    )
    store.ingest(
        {
            "plans": [
                {
                    "fingerprint": FINGERPRINT,
                    "plan": {"Plan": {"Node Type": "Seq Scan", "Relation Name": "orders"}},
                    "cost": 42.0,
                }
            ]
        }
    )


def _say(agent: str, text: str) -> None:
    print(f"\n{agent}")
    print(text)


async def main() -> None:
    db_path = tempfile.mktemp(suffix="-bonito-demo.db")
    store = BonitoStore(db_path)
    _seed(store)

    os.environ["BONITO_API_KEY"] = "demo-key"
    app = create_app(db_path)
    http = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    tools = make_tools(BonitoClient(base_url="http://test", api_key="demo-key", client=http))

    _say("🔄 STEP 1 — agent checks for locks:", "")
    locks = await tools["get_active_locks"]()
    print(json.dumps(locks, indent=2))

    _say("🔄 STEP 2 — agent builds the blocking tree:", "")
    tree = await tools["get_blocking_tree"]()
    print(json.dumps(tree, indent=2))

    _say("🔄 STEP 3 — agent asks for remediation:", "")
    advice = await tools["suggest_remediation"]("lock", "blocking_pid=1408")
    print(json.dumps(advice, indent=2))

    _say("🔄 STEP 4 — agent checks slow queries:", "")
    slow = await tools["get_slow_queries"](limit=3)
    for q in slow["queries"]:
        print(f"  avg_ms={q['avg_ms']:>10} calls={q['calls']:>6} {q['query_text'][:70]}")

    _say("🔄 STEP 5 — agent compares against baseline:", "")
    baseline = await tools["compare_to_baseline"](FINGERPRINT)
    print(json.dumps(baseline, indent=2))

    _say(
        "✅ VERDICT (what a real agent concludes):",
        "PID 1408 holds a transactionid lock blocking 1412 → 1413. "
        "Remediation: pg_terminate_backend(1408). Query -6842... sits on a Seq Scan "
        f"with regression_pct={baseline['regression_pct']} — suggest CREATE INDEX on orders(customer_id).",
    )

    await http.aclose()


if __name__ == "__main__":
    asyncio.run(main())