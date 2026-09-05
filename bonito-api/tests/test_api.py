"""Tests for bonito-api — auth, endpoints, OpenAPI contract."""
from datetime import UTC, datetime

import pytest
from bonito_store.store import BonitoStore
from fastapi.testclient import TestClient

from bonito_api import __version__
from bonito_api.app import create_app

API_KEY = "test-key"


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
                "query": "SELECT * FROM orders WHERE customer_id = $1",
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
                "last_autovacuum": "2026-09-04T00:00:00+00:00",
            }
        ],
    }


def seed(db_path: str) -> None:
    store = BonitoStore(db_path)
    store.ingest(sample_events())
    store.ingest(
        {
            "plans": [
                {
                    "fingerprint": "-6842865755026457642",
                    "plan": {"Plan": {"Node Type": "Seq Scan"}},
                    "cost": 42.0,
                }
            ]
        }
    )


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("BONITO_API_KEY", API_KEY)
    db = str(tmp_path / "api.db")
    seed(db)
    return TestClient(create_app(db))


def test_auth_required(client):
    assert client.get("/queries/top").status_code == 401


def test_no_key_configured_returns_503(tmp_path):
    db = str(tmp_path / "nodb.db")
    seed(db)
    app = create_app(db)
    # no BONITO_API_KEY in env
    assert TestClient(app).get("/queries/top").status_code == 503


def test_bearer_auth_works(client):
    r = client.get("/queries/top", headers={"Authorization": f"Bearer {API_KEY}"})
    assert r.status_code == 200


def test_queries_top(client):
    r = client.get("/queries/top", headers={"X-API-Key": API_KEY})
    body = r.json()
    assert body["queries"][0]["fingerprint"] == "-6842865755026457642"
    assert body["queries"][0]["avg_ms"] == 12.43


def test_locks_active(client):
    r = client.get("/locks/active", headers={"X-API-Key": API_KEY})
    assert r.json()["locks"][0]["blocking_pid"] == 1408


def test_waits_breakdown(client):
    r = client.get("/waits", headers={"X-API-Key": API_KEY})
    waits = r.json()["waits"]
    assert waits[0]["wait_event_type"] == "Lock"
    assert waits[0]["n"] == 1


def test_plans_by_fingerprint(client):
    r = client.get(
        "/plans/-6842865755026457642", headers={"X-API-Key": API_KEY}
    )
    assert r.status_code == 200
    assert r.json()["plan"]["cost"] == 42.0
    assert client.get("/plans/unknown", headers={"X-API-Key": API_KEY}).status_code == 404


def test_health_summary(client):
    r = client.get("/health/app", headers={"X-API-Key": API_KEY})
    body = r.json()
    assert body["db_instance"] == "app"
    assert body["sessions_by_state"][0]["state"] == "active"
    assert body["top_bloat"][0]["fingerprint"] == "public.orders"


def test_baseline_with_regression(client):
    r = client.get(
        "/baseline/-6842865755026457642", headers={"X-API-Key": API_KEY}
    )
    body = r.json()
    assert body["baseline"]["p95_ms"] == 12.43
    assert body["current_avg_ms"] == 12.43
    assert body["regression_pct"] == 0.0


def test_ingest_compat(client):
    events = sample_events()
    r = client.post("/ingest", json=events, headers={"X-API-Key": API_KEY})
    assert r.status_code == 200
    assert r.json()["new_fingerprints"] == 0  # already known → no new


def test_openapi_contract_is_public_and_versioned(client):
    r = client.get("/openapi.json")
    assert r.status_code == 200
    paths = r.json()["paths"]
    for p in ("/queries/top", "/locks/active", "/waits", "/health/{db_instance}", "/baseline/{fingerprint}", "/ingest"):
        assert p in paths
    assert r.json()["info"]["version"] == __version__