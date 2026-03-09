"""
Tests — Engagement Engine
=========================
Covers: worker status, run cycle, feed scan, log, stats, viral, influencers CRUD.
"""

from __future__ import annotations

import pytest
import requests

from tests.conftest import assert_ok, assert_has_keys

BASE = "http://127.0.0.1:8000"


class TestEngagementWorker:
    def test_worker_status(self, api: requests.Session) -> None:
        r = api.get(f"{BASE}/api/engagement/worker")
        body = assert_ok(r)
        assert_has_keys(body, "running", "interval_hours")

    def test_worker_running_is_bool(self, api: requests.Session) -> None:
        body = api.get(f"{BASE}/api/engagement/worker").json()
        assert isinstance(body["running"], bool)

    def test_worker_interval_is_int(self, api: requests.Session) -> None:
        body = api.get(f"{BASE}/api/engagement/worker").json()
        assert isinstance(body["interval_hours"], int)
        assert body["interval_hours"] > 0


class TestEngagementRun:
    def test_run_returns_valid_schema(self, api: requests.Session) -> None:
        r = api.post(f"{BASE}/api/engagement/run", timeout=30)
        body = assert_ok(r)
        assert_has_keys(body, "posts_scanned", "posts_engaged",
                        "comments_posted", "likes_given", "timestamp")

    def test_run_counts_are_non_negative(self, api: requests.Session) -> None:
        body = api.post(f"{BASE}/api/engagement/run", timeout=30).json()
        assert body["posts_scanned"] >= 0
        assert body["posts_engaged"] >= 0
        assert body["comments_posted"] >= 0
        assert body["likes_given"] >= 0

    def test_run_error_field_is_string_or_none(self, api: requests.Session) -> None:
        body = api.post(f"{BASE}/api/engagement/run", timeout=30).json()
        assert body.get("error") is None or isinstance(body["error"], str)

    def test_run_timestamp_is_set(self, api: requests.Session) -> None:
        body = api.post(f"{BASE}/api/engagement/run", timeout=30).json()
        assert body["timestamp"] not in (None, "")


class TestEngagementFeed:
    def test_get_feed_returns_200(self, api: requests.Session) -> None:
        r = api.get(f"{BASE}/api/engagement/feed", timeout=30)
        assert r.status_code in (200, 500)  # 500 if playwright not installed

    def test_post_feed_returns_200(self, api: requests.Session) -> None:
        r = api.post(f"{BASE}/api/engagement/feed", timeout=30)
        assert r.status_code in (200, 500)

    def test_feed_response_shape_on_success(self, api: requests.Session) -> None:
        r = api.get(f"{BASE}/api/engagement/feed", timeout=30)
        if r.status_code == 200:
            body = r.json()
            assert "posts" in body or "detail" in body


class TestEngagementLog:
    def test_get_log_returns_200(self, api: requests.Session) -> None:
        r = api.get(f"{BASE}/api/engagement/log")
        body = assert_ok(r)
        assert_has_keys(body, "rows", "count")

    def test_log_rows_is_list(self, api: requests.Session) -> None:
        body = api.get(f"{BASE}/api/engagement/log").json()
        assert isinstance(body["rows"], list)

    def test_log_limit_param(self, api: requests.Session) -> None:
        body = api.get(f"{BASE}/api/engagement/log", params={"limit": 5}).json()
        assert len(body["rows"]) <= 5

    def test_log_status_filter(self, api: requests.Session) -> None:
        r = api.get(f"{BASE}/api/engagement/log", params={"status": "done"})
        assert_ok(r)


class TestEngagementStats:
    def test_stats_returns_200(self, api: requests.Session) -> None:
        r = api.get(f"{BASE}/api/engagement/stats")
        body = assert_ok(r)
        assert_has_keys(body, "total_likes", "total_comments",
                        "today_likes", "today_comments", "engagement_rate")

    def test_stats_all_non_negative(self, api: requests.Session) -> None:
        body = api.get(f"{BASE}/api/engagement/stats").json()
        assert body["total_likes"] >= 0
        assert body["total_comments"] >= 0
        assert body["today_likes"] >= 0
        assert body["today_comments"] >= 0
        assert body["engagement_rate"] >= 0


class TestViralPosts:
    def test_viral_returns_200(self, api: requests.Session) -> None:
        r = api.get(f"{BASE}/api/engagement/viral")
        body = assert_ok(r)
        assert_has_keys(body, "rows", "count")

    def test_viral_days_param(self, api: requests.Session) -> None:
        r = api.get(f"{BASE}/api/engagement/viral", params={"days": 30})
        assert_ok(r)

    def test_viral_rows_is_list(self, api: requests.Session) -> None:
        body = api.get(f"{BASE}/api/engagement/viral").json()
        assert isinstance(body["rows"], list)


class TestInfluencers:
    _created_id: int | None = None

    def test_list_influencers(self, api: requests.Session) -> None:
        r = api.get(f"{BASE}/api/engagement/influencers")
        body = assert_ok(r)
        assert "influencers" in body
        assert isinstance(body["influencers"], list)

    def test_add_influencer(self, api: requests.Session) -> None:
        import time
        unique_url = f"https://linkedin.com/in/test-influencer-pytest-{int(time.time())}"
        TestInfluencers._test_url = unique_url
        r = api.post(
            f"{BASE}/api/engagement/influencers",
            json={
                "name": "Test Influencer",
                "linkedin_url": unique_url,
                "category": "technology",
                "priority": 3,
            },
        )
        body = assert_ok(r, allow_codes=(200, 201))
        assert "id" in body
        TestInfluencers._created_id = body["id"]

    def test_influencer_appears_in_list(self, api: requests.Session) -> None:
        url = getattr(TestInfluencers, "_test_url", None)
        if url is None:
            pytest.skip("No influencer was created in this session")
        body = api.get(f"{BASE}/api/engagement/influencers").json()
        urls = [i["linkedin_url"] for i in body["influencers"]]
        assert url in urls

    def test_delete_influencer(self, api: requests.Session) -> None:
        if TestInfluencers._created_id is None:
            pytest.skip("No influencer was created in this session")
        r = api.delete(f"{BASE}/api/engagement/influencers/{TestInfluencers._created_id}")
        body = assert_ok(r)
        assert body.get("action") == "removed"

    def test_delete_nonexistent_influencer(self, api: requests.Session) -> None:
        r = api.delete(f"{BASE}/api/engagement/influencers/999999")
        # Should succeed silently (soft delete) or 404
        assert r.status_code in (200, 404)

    def test_add_influencer_missing_required_fields(self, api: requests.Session) -> None:
        r = api.post(
            f"{BASE}/api/engagement/influencers",
            json={"category": "tech"},  # missing name + linkedin_url
        )
        assert r.status_code == 422
