"""Tests for bonito-collector — no live DB needed (unit + safety checks)."""
import json
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from bonito_collector import collectors
from bonito_collector.config import DEFAULT_INTERVALS, CollectorConfig
from bonito_collector.db import _jsonable


def test_config_from_env_requires_dsn(monkeypatch):
    monkeypatch.delenv("BONITO_DSN", raising=False)
    with pytest.raises(ValueError):
        CollectorConfig.from_env()


def test_config_defaults(monkeypatch):
    monkeypatch.setenv("BONITO_DSN", "postgresql://ro@localhost/db")
    cfg = CollectorConfig.from_env()
    assert cfg.top_n == 20
    assert cfg.prometheus_port == 9187
    assert cfg.intervals == DEFAULT_INTERVALS


def test_intervals_have_all_types():
    for k in ("metrics", "queries", "locks", "sessions", "plans", "tables"):
        assert k in DEFAULT_INTERVALS


def test_sql_constants_are_parameterized_only():
    # No f-string interpolation of client data — only %s placeholders
    assert "%s" in collectors.SQL_TOP_QUERIES
    assert "%s" in collectors.SQL_TABLE_STATS
    # blocking/sessions have no params (fixed)
    assert "%s" not in collectors.SQL_BLOCKING
    assert "%s" not in collectors.SQL_SESSIONS


class _FakePG:
    """Minimal fake for collect_plan safety test (no real DB)."""
    def query(self, sql, params=()):
        return [{"QUERY PLAN": [{"Plan": {}}]}]


def test_collect_plan_rejects_non_read_queries():
    pg = _FakePG()
    assert collectors.collect_plan(pg, "UPDATE users SET x=1") is None
    assert collectors.collect_plan(pg, "DELETE FROM users") is None


def test_collect_plan_accepts_select():
    pg = _FakePG()
    res = collectors.collect_plan(pg, "SELECT 1")
    assert res is not None
    assert "plan" in res


def test_jsonable_coerces_db_types():
    # psycopg returns Decimal/datetime — must be JSON-serializable for push_events
    assert _jsonable(Decimal("12.43")) == 12.43
    assert _jsonable(datetime(2026, 1, 1, 12, 0, tzinfo=UTC)) == "2026-01-01T12:00:00+00:00"
    assert _jsonable("plain") == "plain"


def test_top_queries_payload_is_json_serializable():
    row = {
        "fingerprint": "-6842865755026457642",
        "calls": 1284,
        "mean_ms": Decimal("12.43"),
        "max_ms": Decimal("841.02"),
        "rows": 245680,
    }
    payload = {k: _jsonable(v) for k, v in row.items()}
    json.dumps(payload)  # must not raise (fix for Decimal/JSON push failure)


def test_export_prometheus_enriched_gauges():
    from prometheus_client import REGISTRY

    from bonito_collector import emit

    queries = [
        {
            "fingerprint": "fp1",
            "mean_ms": 12.43,
            "calls": 1284,
            "max_ms": 841.02,
            "rows": 245680,
            "buffer_hit_ratio": 99.2,
        }
    ]
    locks = [{"blocking_pid": 1, "blocked_pids": "[2]"}]
    sessions = [
        {"state": "active", "wait_event_type": "Lock"},
        {"state": "idle in transaction", "wait_event_type": None},
    ]
    tables = [
        {
            "schema": "public",
            "table": "orders",
            "live_rows": 100,
            "dead_rows": 10,
            "bloat_pct": 5.0,
            "seq_scan": 12,
            "idx_scan": 34,
        }
    ]
    emit.export_prometheus(queries, locks, sessions, tables)

    # per-query
    assert REGISTRY.get_sample_value("bonito_query_calls", {"fingerprint": "fp1"}) == 1284
    assert REGISTRY.get_sample_value("bonito_query_max_ms", {"fingerprint": "fp1"}) == 841.02
    assert REGISTRY.get_sample_value("bonito_query_rows", {"fingerprint": "fp1"}) == 245680
    assert REGISTRY.get_sample_value(
        "bonito_query_buffer_hit_ratio", {"fingerprint": "fp1"}
    ) == 99.2
    # sessions / waits
    assert REGISTRY.get_sample_value("bonito_idle_in_transaction") == 1
    assert REGISTRY.get_sample_value(
        "bonito_sessions_by_state", {"state": "active"}
    ) == 1
    assert REGISTRY.get_sample_value("bonito_wait_events_total", {"type": "Lock"}) == 1
    # per-table
    assert REGISTRY.get_sample_value(
        "bonito_table_live_rows", {"table": "public.orders"}
    ) == 100
    assert REGISTRY.get_sample_value(
        "bonito_table_seq_scan", {"table": "public.orders"}
    ) == 12
    assert REGISTRY.get_sample_value(
        "bonito_table_idx_scan", {"table": "public.orders"}
    ) == 34

    emit.record_scrape_duration(0.5)
    emit.record_collector_error()
    assert REGISTRY.get_sample_value("bonito_collector_scrape_duration_seconds") == 0.5
    assert REGISTRY.get_sample_value("bonito_collector_errors_total") == 1


def test_otlp_disabled_by_default():
    from bonito_collector import traces

    assert traces.init_otlp(None) is False
    # no-op when not configured — must never raise
    traces.emit_query_span("fp", "SELECT 1", 1.0, 2.0, 3, 4, 99.0)
    traces.emit_lock_span(2, 1, "Lock", "tuple")


def test_config_reads_otlp_endpoint(monkeypatch):
    monkeypatch.setenv("BONITO_DSN", "postgresql://ro@localhost/db")
    monkeypatch.setenv("BONITO_OTLP_ENDPOINT", "http://tempo:4317")
    cfg = CollectorConfig.from_env()
    assert cfg.otlp_endpoint == "http://tempo:4317"
