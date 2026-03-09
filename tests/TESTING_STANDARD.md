# Phoenix Marketing Engine — Testing Standard

## Philosophy

- **API-first**: All tests run against the live FastAPI server (no mocking)
- **Non-destructive**: Tests never delete production data or push to external services
- **Tolerant of empty DB**: Tests pass on a fresh install with zero rows
- **Clear failure messages**: Every assertion includes context about what failed

## Test Structure

```
tests/
├── conftest.py          # Session fixtures, helpers (assert_ok, assert_has_keys)
├── TESTING_STANDARD.md  # This document
├── test_system.py       # Health, workers, config, sources, DB browser, Web GUI
├── test_pipeline.py     # Signals, Insights, Content, Distribution, Analytics, Pipeline
└── test_engagement.py   # Engagement worker, run, feed, log, stats, viral, influencers
```

## Assertion Helpers

| Helper | Purpose |
|---|---|
| `assert_ok(response, allow_codes=(200,201))` | Asserts status in allowed set, returns JSON |
| `assert_has_keys(body, *keys)` | Asserts keys exist in response dict |

## Status Code Conventions

| Scenario | Expected codes |
|---|---|
| Normal GET | `200` |
| Normal POST/PUT (create) | `200` or `201` |
| Resource not found | `404` |
| Validation error | `422` |
| Missing dependency (playwright) | `500` with `detail` explaining the issue |
| Long-running operation (collect/generate) | `200`, `202`, or `500` |

Tests use `assert r.status_code in (200, 500)` for optional-dependency paths,
ensuring the test passes whether or not playwright is installed.

## Running Tests

```bash
# Full suite
.venv/Scripts/pytest tests/ -v

# Specific file
.venv/Scripts/pytest tests/test_system.py -v

# Specific class
.venv/Scripts/pytest tests/test_engagement.py::TestInfluencers -v

# Fast (skip slow generate/collect calls)
.venv/Scripts/pytest tests/ -v -k "not generate and not collect and not run and not pipeline"

# With summary
.venv/Scripts/pytest tests/ -v --tb=short --no-header -q
```

## Prerequisites

1. Server must be running: `.venv/Scripts/python -m uvicorn api.main:app --port 8000`
2. `.env` must have `GROQ_API_KEY` set (content generation tests need it)
3. DB must be initialised (happens automatically on server start)

## Adding New Tests

1. Place in the appropriate `test_*.py` file by domain
2. Use `class Test<Feature>:` grouping
3. Use `assert_ok()` — never `assert r.status_code == 200` directly
4. For slow tests, add `timeout=` to the request call
5. For destructive tests (create+delete), store the created ID as a class variable
6. For optional features (playwright), allow `500` in the status set

## What Is NOT Tested Here

- Browser/Selenium UI interactions (web GUI visual behaviour)
- LinkedIn live posting (would create real posts)
- Git push to website (would push to production)
- Playwright feed scanning (requires LinkedIn session)

These are integration tests that require human approval and are documented
in the manual test checklist in `PRODUCT_CAPABILITIES.md`.
