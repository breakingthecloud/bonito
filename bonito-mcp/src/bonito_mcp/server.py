"""MCPServer with the 8 Bonito tools (BON-004).

Each tool is a thin wrapper over the bonito-api REST layer; business logic
(baselines, plans) lives in the store/API. Tool descriptions are written for
LLM routing ("AI-first UX").
"""
from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from mcp.server.mcpserver import MCPServer

from .client import BonitoClient

REMEDIATION_RULES: dict[str, str] = {
    "slow_query": (
        "Query is slow: check for sequential scans and missing indexes. Suggest: "
        "CREATE INDEX CONCURRENTLY on the filtered/joined columns; raise work_mem "
        "if sorts spill to disk."
    ),
    "lock": (
        "A lock is held. Identify blocking_pid from the blocking tree and terminate "
        "it with pg_terminate_backend if it is a stale/idle-in-transaction session; "
        "set lock_timeout to prevent long waits."
    ),
    "blocking": (
        "A blocking tree exists. Kill the blocking session or fix the transaction "
        "that holds locks too long; investigate idle-in-transaction sessions."
    ),
    "bloat": (
        "Table bloat detected. Run VACUUM (FULL) during maintenance or tune "
        "autovacuum_vacuum_scale_factor / autovacuum_naptime for steady bloat."
    ),
    "wait_io": (
        "Sessions wait on I/O. Check disk latency and throughput; consider moving "
        "hot tables/indexes to faster storage and raising effective_io_concurrency."
    ),
    "wait_lock": (
        "Sessions wait on locks. Use lock_timeout, examine the blocking tree, and "
        "kill the session holding the conflicting lock."
    ),
}


def suggest_remediation(
    issue_type: str, detail: str | None = None
) -> dict[str, Any]:
    """Rule-based remediation advice for a detected DB issue."""
    rule = REMEDIATION_RULES.get(issue_type, REMEDIATION_RULES.get("slow_query"))
    return {
        "issue_type": issue_type,
        "advice": rule,
        "context": detail[:300] if detail else None,
    }


def build_blocking_tree(locks: list[dict[str, Any]]) -> dict[str, Any]:
    """Reconstruct parent→children from flat lock events (PID → blocked PIDs)."""
    tree: dict[str, Any] = {}
    for lock in locks:
        blocker = lock.get("blocking_pid")
        if blocker is None:
            continue
        blocked: list[Any] = []
        if lock.get("blocked_pids"):
            try:
                blocked = json.loads(lock["blocked_pids"])
            except json.JSONDecodeError:
                blocked = [lock["blocked_pids"]]
        node = tree.setdefault(
            str(blocker),
            {"blocking_pid": blocker, "lock_mode": lock.get("lock_mode"), "blocked_pids": []},
        )
        for pid in blocked:
            if pid not in node["blocked_pids"]:
                node["blocked_pids"].append(pid)
    return {"tree": list(tree.values()), "total_blocked": sum(
        len(node["blocked_pids"]) for node in tree.values()
    )}


def make_tools(client: BonitoClient) -> dict[str, Callable[..., Any]]:
    async def get_slow_queries(
        db_instance: str = "default", period: str = "24h", limit: int = 10
    ) -> dict[str, Any]:
        """Top N slowest queries in a period. Returns query_text, calls, avg_ms, max_ms, rows.
        Example: 'which queries are slow on rds-prod right now?' -> get_slow_queries(db_instance='rds-prod', period='1h')."""
        return await client.top_queries(db_instance, period, limit)

    async def get_active_locks(
        db_instance: str = "default", minutes: int = 10
    ) -> dict[str, Any]:
        """Currently active lock events / blocking pairs. Returns blocking_pid, blocked_pids, lock_mode.
        Example: 'are there locks on the orders table?' -> get_active_locks()."""
        return await client.active_locks(db_instance, minutes)

    async def get_blocking_tree(
        db_instance: str = "default", minutes: int = 10
    ) -> dict[str, Any]:
        """Blocking tree: each blocker PID mapped to the PIDs it blocks.
        Use before deciding to kill a session. Example: 'who is blocking whom?'"""
        data = await client.active_locks(db_instance, minutes)
        return build_blocking_tree(data.get("locks", []))

    async def explain_query(
        fingerprint: str, db_instance: str = "default"
    ) -> dict[str, Any]:
        """Execution plan (EXPLAIN JSON) for a query fingerprint: node types, seq scans, index usage, cost.
        Example: 'what is the plan for fingerprint -6842865755026457642?' -> explain_query(fingerprint='-6842865755026457642')."""
        return await client.plan(fingerprint, db_instance)

    async def get_wait_analysis(
        db_instance: str = "default", minutes: int = 10
    ) -> dict[str, Any]:
        """Wait breakdown by wait_event_type (Lock, IO, CPU, Client, etc.) with counts and total age.
        Example: 'what are sessions waiting on?' -> get_wait_analysis()."""
        return await client.waits(db_instance, minutes)

    async def compare_to_baseline(
        fingerprint: str, db_instance: str = "default", days: int = 7
    ) -> dict[str, Any]:
        """Compare a query's current avg_ms against its 7-day baseline. regression_pct > 0 means slower.
        Example: 'is the checkout query slower than usual?' -> compare_to_baseline(fingerprint='...')."""
        return await client.baseline(fingerprint, db_instance, days)

    async def suggest_remediation_tool(
        issue_type: str = "slow_query", detail: str | None = None
    ) -> dict[str, Any]:
        """Actionable remediation advice for a DB issue. issue_type in {slow_query, lock, blocking, bloat, wait_io, wait_lock}.
        Example: 'what should we do about this lock?' -> suggest_remediation(issue_type='lock')."""
        return suggest_remediation(issue_type, detail)

    async def get_db_health_summary(
        db_instance: str = "default", minutes: int = 10
    ) -> dict[str, Any]:
        """Executive health summary: sessions by state, top table bloat.
        Example: 'give me a health summary of the database' -> get_db_health_summary()."""
        return await client.health(db_instance, minutes)

    return {
        "get_slow_queries": get_slow_queries,
        "get_active_locks": get_active_locks,
        "get_blocking_tree": get_blocking_tree,
        "explain_query": explain_query,
        "get_wait_analysis": get_wait_analysis,
        "compare_to_baseline": compare_to_baseline,
        "suggest_remediation": suggest_remediation_tool,
        "get_db_health_summary": get_db_health_summary,
    }


def build_mcp(client: BonitoClient) -> MCPServer:
    server = MCPServer(
        "bonito",
        title="Bonito — Deep DB Observability",
        description=(
            "Read-only deep database observability: slow queries, lock/blocking "
            "trees, wait analysis, execution plans, baselines and remediation "
            "advice. Use these tools to diagnose PostgreSQL performance problems."
        ),
        version="0.1.2",
    )
    for name, fn in make_tools(client).items():
        server.tool(name=name)(fn)
    return server