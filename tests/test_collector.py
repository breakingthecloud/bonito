"""Tests for bonito-collector — no live DB needed (unit + safety checks)."""
import pytest

from bonito_collector import collectors
from bonito_collector.config import DEFAULT_INTERVALS, CollectorConfig


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
