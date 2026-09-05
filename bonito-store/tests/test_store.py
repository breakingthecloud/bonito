"""Tests for bonito-store — dedupe, baselines, pruning, batch + API."""
from fastapi.testclient import TestClient

from bonito_store.api import create_app
from bonito_store.normalize import fingerprint_of, minify_sql
from bonito_store.store import BonitoStore


def sample_events() -> dict:
    return {
        "collected_at": "2026-09-04T02:10:00+00:00",
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


def test_minify_and_fingerprint():
    assert (
        minify_sql("  SELECT  *\nFROM   users WHERE id = 1 ")
        == "select * from users where id = 1"
    )
    assert fingerprint_of("SELECT 1") == fingerprint_of("select 1")


def test_ingest_dedupe_by_fingerprint(tmp_path):
    store = BonitoStore(tmp_path / "t.db")
    s1 = store.ingest(sample_events())
    s2 = store.ingest(sample_events())
    assert s1["new_fingerprints"] == 1
    assert s2["new_fingerprints"] == 0
    assert s1["top_queries"] == 1 and s1["locks"] == 1
    assert s1["sessions"] == 1 and s1["tables"] == 1
    with store._conn() as conn:
        rows = conn.execute(
            "SELECT calls, avg_ms FROM query_texts WHERE fingerprint = ?",
            ("-6842865755026457642",),
        ).fetchall()
        assert len(rows) == 1  # dedupe: one row, stats updated
        assert rows[0]["calls"] == 1284


def test_fallback_fingerprint_from_query(tmp_path):
    store = BonitoStore(tmp_path / "t.db")
    events = sample_events()
    del events["top_queries"][0]["fingerprint"]
    events["top_queries"][0]["query"] = "  SELECT 1 "
    summary = store.ingest(events)
    assert summary["new_fingerprints"] == 1
    assert fingerprint_of("SELECT 1") in [
        b["fingerprint"] for b in store.baselines()
    ]


def test_baseline_mean_and_p95(tmp_path):
    store = BonitoStore(tmp_path / "t.db")
    for i in range(10):
        events = sample_events()
        events["collected_at"] = f"2026-09-04T02:{i:02d}:00+00:00"
        store.ingest(events)
    bl = store.baselines()
    assert len(bl) == 1
    assert bl[0]["samples"] == 10
    assert bl[0]["mean_ms"] == 12.43
    assert bl[0]["p95_ms"] == 12.43  # all samples equal


def test_prune_removes_old_samples(tmp_path):
    store = BonitoStore(tmp_path / "t.db", retention_days=1)
    with store._conn() as conn:
        conn.execute(
            "INSERT INTO query_samples (fingerprint, ts, calls, mean_ms, rows) "
            "VALUES ('old', '2000-01-01T00:00:00+00:00', 1, 5.0, 1)"
        )
    removed = store.prune()
    assert removed["query_samples"] >= 1
    with store._conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM query_samples WHERE fingerprint = 'old'"
        ).fetchone()
        assert row is None


def test_batch_capped_at_100(tmp_path):
    store = BonitoStore(tmp_path / "t.db")
    events = sample_events()
    events["top_queries"] = [sample_events()["top_queries"][0]] * 150
    summary = store.ingest(events)
    assert summary["top_queries"] == 100  # capped by BATCH_LIMIT


def test_api_events_and_baselines(tmp_path):
    app = create_app(str(tmp_path / "api.db"))
    client = TestClient(app)
    r = client.post("/events", json=sample_events())
    assert r.status_code == 200
    assert r.json()["new_fingerprints"] == 1
    bl = client.get("/baselines").json()["baselines"]
    assert bl[0]["fingerprint"] == "-6842865755026457642"
    assert client.get("/health").json() == {"status": "ok"}


def test_api_plans_endpoint(tmp_path):
    app = create_app(str(tmp_path / "plans.db"))
    client = TestClient(app)
    r = client.post(
        "/plans",
        json={
            "plans": [
                {
                    "fingerprint": "abc",
                    "plan": {"Plan": {"Node Type": "Seq Scan"}},
                    "cost": 42.0,
                }
            ]
        },
    )
    assert r.status_code == 200
    assert r.json()["plans"] == 1
    with app.state.store._conn() as conn:
        row = conn.execute(
            "SELECT plan_json, cost FROM execution_plans WHERE fingerprint = 'abc'"
        ).fetchone()
        assert row["cost"] == 42.0
        assert "Seq Scan" in row["plan_json"]