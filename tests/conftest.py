"""
Phoenix Marketing Engine — Test Configuration
============================================
Shared fixtures and helpers for the API test suite.
"""

from __future__ import annotations

import pytest
import requests

BASE_URL = "http://127.0.0.1:8000"


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def api():
    """Return a requests.Session pre-configured for the Phoenix API."""
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    # Smoke-test: server must be reachable before any test runs
    try:
        r = s.get(f"{BASE_URL}/health", timeout=5)
        r.raise_for_status()
    except Exception as exc:
        pytest.exit(
            f"Server not reachable at {BASE_URL} — start it first.\n{exc}",
            returncode=1,
        )
    return s


@pytest.fixture(scope="session")
def base_url():
    return BASE_URL


# ── Assertion helpers ─────────────────────────────────────────────────────────

def assert_ok(response: requests.Response, *, allow_codes: tuple[int, ...] = (200, 201)) -> dict:
    """Assert the response is in the allowed codes and return JSON body."""
    assert response.status_code in allow_codes, (
        f"{response.request.method} {response.url} → {response.status_code}\n"
        f"Body: {response.text[:500]}"
    )
    return response.json()


def assert_has_keys(body: dict, *keys: str) -> None:
    """Assert all keys are present in the response dict."""
    missing = [k for k in keys if k not in body]
    assert not missing, f"Missing keys {missing} in: {list(body.keys())}"
