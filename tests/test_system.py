"""
Tests — System & Infrastructure Endpoints
==========================================
Covers: /health, /api/system/status, /api/system/workers,
        worker start/stop/restart, /api/system/config,
        /api/sources, /api/db/browse
"""

from __future__ import annotations

import pytest
import requests

from tests.conftest import assert_ok, assert_has_keys

BASE = "http://127.0.0.1:8000"
ENGINES = ["signal", "insight", "content", "distribution", "analytics"]


# ── Health ─────────────────────────────────────────────────────────────────────

class TestHealth:
    def test_health_returns_200(self, api: requests.Session) -> None:
        r = api.get(f"{BASE}/health")
        body = assert_ok(r)
        assert_has_keys(body, "status", "version")

    def test_health_status_is_ok(self, api: requests.Session) -> None:
        r = api.get(f"{BASE}/health")
        assert r.json()["status"] == "ok"

    def test_health_version_is_set(self, api: requests.Session) -> None:
        r = api.get(f"{BASE}/health")
        assert r.json()["version"] not in (None, "", "unknown")


# ── System Status ──────────────────────────────────────────────────────────────

class TestSystemStatus:
    def test_status_returns_200(self, api: requests.Session) -> None:
        r = api.get(f"{BASE}/api/system/status")
        assert_ok(r)

    def test_status_has_required_fields(self, api: requests.Session) -> None:
        body = api.get(f"{BASE}/api/system/status").json()
        assert isinstance(body, dict), "Expected a dict"


# ── Workers ────────────────────────────────────────────────────────────────────

class TestWorkers:
    def test_get_all_workers(self, api: requests.Session) -> None:
        r = api.get(f"{BASE}/api/system/workers")
        body = assert_ok(r)
        assert isinstance(body, dict)
        for engine in ENGINES:
            assert engine in body, f"Engine '{engine}' missing from workers response"

    def test_each_worker_has_running_and_interval(self, api: requests.Session) -> None:
        body = api.get(f"{BASE}/api/system/workers").json()
        for engine in ENGINES:
            w = body[engine]
            assert "running" in w, f"{engine}: missing 'running'"
            assert "interval_hours" in w or "interval_minutes" in w, (
                f"{engine}: missing interval key"
            )

    @pytest.mark.parametrize("engine", ENGINES)
    def test_stop_worker(self, api: requests.Session, engine: str) -> None:
        r = api.post(f"{BASE}/api/system/workers/{engine}/stop")
        assert_ok(r)

    @pytest.mark.parametrize("engine", ENGINES)
    def test_start_worker(self, api: requests.Session, engine: str) -> None:
        r = api.post(f"{BASE}/api/system/workers/{engine}/start")
        assert_ok(r)

    @pytest.mark.parametrize("engine,interval_key,interval_val", [
        ("signal",       "interval_hours",   3),
        ("insight",      "interval_hours",   6),
        ("content",      "interval_hours",  12),
        ("distribution", "interval_minutes", 15),
        ("analytics",    "interval_hours",  12),
    ])
    def test_restart_worker_with_new_interval(
        self, api: requests.Session, engine: str, interval_key: str, interval_val: int
    ) -> None:
        r = api.post(
            f"{BASE}/api/system/workers/{engine}/restart",
            json={interval_key: interval_val},
        )
        assert_ok(r)

    def test_invalid_engine_returns_404(self, api: requests.Session) -> None:
        r = api.post(f"{BASE}/api/system/workers/nonexistent/stop")
        assert r.status_code == 404

    def test_interval_persisted_after_restart(self, api: requests.Session) -> None:
        api.post(f"{BASE}/api/system/workers/signal/restart", json={"interval_hours": 4})
        body = api.get(f"{BASE}/api/system/workers").json()
        assert body["signal"]["interval_hours"] == 4


# ── System Config ──────────────────────────────────────────────────────────────

class TestSystemConfig:
    def test_get_config_returns_200(self, api: requests.Session) -> None:
        r = api.get(f"{BASE}/api/system/config")
        assert_ok(r)

    def test_post_config_updates_value(self, api: requests.Session) -> None:
        r = api.post(f"{BASE}/api/system/config", json={"content_max_per_cycle": 5})
        assert_ok(r)

    def test_config_value_persists(self, api: requests.Session) -> None:
        api.post(f"{BASE}/api/system/config", json={"content_max_per_cycle": 7})
        body = api.get(f"{BASE}/api/system/config").json()
        assert body.get("content_max_per_cycle") == 7


# ── Sources ────────────────────────────────────────────────────────────────────

class TestSources:
    def test_get_sources_returns_list(self, api: requests.Session) -> None:
        r = api.get(f"{BASE}/api/sources")
        body = assert_ok(r)
        assert "sources" in body
        assert isinstance(body["sources"], list)

    def test_post_sources_updates(self, api: requests.Session) -> None:
        existing = api.get(f"{BASE}/api/sources").json()["sources"]
        r = api.post(f"{BASE}/api/sources", json={"sources": existing})
        assert_ok(r)


# ── Database Browser ──────────────────────────────────────────────────────────

class TestDatabaseBrowser:
    TABLES = ["signals", "insights", "content", "distribution_queue",
              "engagement_log", "influencer_targets"]

    @pytest.mark.parametrize("table", TABLES)
    def test_browse_table(self, api: requests.Session, table: str) -> None:
        r = api.get(f"{BASE}/api/db/browse", params={"table": table, "limit": 10})
        body = assert_ok(r)
        assert "rows" in body, f"'rows' missing for table {table}"
        assert isinstance(body["rows"], list)

    def test_browse_invalid_table_returns_error(self, api: requests.Session) -> None:
        r = api.get(f"{BASE}/api/db/browse", params={"table": "nonexistent_table"})
        assert r.status_code in (400, 422, 500)

    def test_browse_limit_respected(self, api: requests.Session) -> None:
        r = api.get(f"{BASE}/api/db/browse", params={"table": "signals", "limit": 3})
        body = assert_ok(r)
        assert len(body["rows"]) <= 3


# ── Observability / Metrics ───────────────────────────────────────────────────

class TestObservability:
    def test_metrics_returns_200(self, api: requests.Session) -> None:
        r = api.get(f"{BASE}/api/system/metrics")
        body = assert_ok(r)
        assert "version" in body
        assert "uptime_seconds" in body
        assert isinstance(body["uptime_seconds"], int)

    def test_metrics_has_db_counts(self, api: requests.Session) -> None:
        body = api.get(f"{BASE}/api/system/metrics").json()
        assert "db_signals_count" in body
        assert "db_content_count" in body
        assert "workers_running" in body

    def test_deep_health_returns_200(self, api: requests.Session) -> None:
        r = api.get(f"{BASE}/api/system/health/deep")
        body = assert_ok(r)
        assert body["status"] in ("ok", "degraded")
        assert "database" in body

    def test_deep_health_db_ok(self, api: requests.Session) -> None:
        body = api.get(f"{BASE}/api/system/health/deep").json()
        assert body["database"] == "ok"

    def test_browse_author_metrics(self, api: requests.Session) -> None:
        r = api.get(f"{BASE}/api/db/browse", params={"table": "author_metrics", "limit": 5})
        body = assert_ok(r)
        assert "rows" in body
        assert isinstance(body["rows"], list)


# ── Web GUI (index.html) ──────────────────────────────────────────────────────

class TestWebGui:
    def test_root_serves_html(self, api: requests.Session) -> None:
        r = api.get(f"{BASE}/")
        assert r.status_code == 200
        assert "text/html" in r.headers.get("content-type", "")

    def test_html_contains_phoenix(self, api: requests.Session) -> None:
        r = api.get(f"{BASE}/")
        assert "Phoenix" in r.text or "phoenix" in r.text.lower()
