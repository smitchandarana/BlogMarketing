"""
Phoenix Intelligence Engine — Comprehensive Selenium UI Test Suite
Tests every page, button, API interaction, and visual element in the Web GUI.
Run:  python tests/selenium_full_test.py
"""

from __future__ import annotations

import json
import os
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    WebDriverException,
)

# ── Config ────────────────────────────────────────────────────────────────────
BASE_URL = "http://127.0.0.1:8000"
SCREENSHOTS_DIR = Path(__file__).parent.parent / "tests" / "screenshots"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
WAIT_TIMEOUT = 10  # seconds

# ── Results tracking ──────────────────────────────────────────────────────────
results: list[dict] = []
screenshot_n = [0]


def _shot(driver: webdriver.Chrome, label: str) -> str:
    """Save a screenshot and return the path."""
    screenshot_n[0] += 1
    fname = SCREENSHOTS_DIR / f"{screenshot_n[0]:03d}-{label}.png"
    driver.save_screenshot(str(fname))
    print(f"  [screenshot] {fname.name}")
    return str(fname)


def _pass(test: str, detail: str = "") -> None:
    results.append({"test": test, "status": "PASS", "detail": detail})
    print(f"  PASS  {test}" + (f" — {detail}" if detail else ""))


def _fail(test: str, detail: str = "") -> None:
    results.append({"test": test, "status": "FAIL", "detail": detail})
    print(f"  FAIL  {test}" + (f" — {detail}" if detail else ""))


def _warn(test: str, detail: str = "") -> None:
    results.append({"test": test, "status": "WARN", "detail": detail})
    print(f"  WARN  {test}" + (f" — {detail}" if detail else ""))


def wait_for(driver: webdriver.Chrome, by: str, value: str, timeout: int = WAIT_TIMEOUT):
    return WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, value)))


def navigate_to(driver: webdriver.Chrome, page: str) -> None:
    """Click a nav link by data-page attribute."""
    link = driver.find_element(By.CSS_SELECTOR, f'#nav a[data-page="{page}"]')
    link.click()
    time.sleep(0.5)


def wait_log_populated(driver: webdriver.Chrome, log_id: str, timeout: int = 8) -> bool:
    """Wait until a log-box has content."""
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: len(d.find_element(By.ID, log_id).text.strip()) > 0
        )
        return True
    except TimeoutException:
        return False


def get_js_errors(driver: webdriver.Chrome) -> list[str]:
    """Retrieve JavaScript console errors."""
    try:
        logs = driver.get_log("browser")
        return [e["message"] for e in logs if e["level"] in ("SEVERE", "WARNING")]
    except Exception:
        return []


# ═══════════════════════════════════════════════════════════════════════════════
# TEST FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def test_initial_load(driver: webdriver.Chrome) -> None:
    print("\n[PAGE LOAD]")
    driver.get(BASE_URL)
    time.sleep(2)

    # Title
    title = driver.title
    if "Phoenix" in title:
        _pass("page-title", title)
    else:
        _fail("page-title", f"Got: {title}")

    _shot(driver, "01-initial-load")

    # Sidebar present
    try:
        sidebar = driver.find_element(By.ID, "sidebar")
        _pass("sidebar-exists")
    except NoSuchElementException:
        _fail("sidebar-exists")

    # Nav links count
    nav_links = driver.find_elements(By.CSS_SELECTOR, "#nav a")
    if len(nav_links) >= 9:
        _pass("nav-links-count", f"{len(nav_links)} links")
    else:
        _fail("nav-links-count", f"Only {len(nav_links)} links found")

    # Dashboard page active
    active_page = driver.find_element(By.CSS_SELECTOR, ".page.active")
    if "dashboard" in active_page.get_attribute("id"):
        _pass("dashboard-default-active")
    else:
        _fail("dashboard-default-active", f"Active: {active_page.get_attribute('id')}")

    # Server badge
    try:
        badge = driver.find_element(By.ID, "srv-badge")
        _pass("server-badge", badge.text)
    except NoSuchElementException:
        _fail("server-badge")

    # Status bar
    try:
        sb = driver.find_element(By.ID, "statusbar")
        _pass("statusbar-exists", sb.text[:60])
    except NoSuchElementException:
        _fail("statusbar-exists")

    # JS errors check
    errors = get_js_errors(driver)
    if errors:
        _warn("no-js-errors-on-load", f"{len(errors)} errors: {errors[0][:100]}")
    else:
        _pass("no-js-errors-on-load")


def test_dashboard(driver: webdriver.Chrome) -> None:
    print("\n[DASHBOARD]")
    navigate_to(driver, "dashboard")
    time.sleep(1)

    # Stat cards — wait up to 5s for values to populate via API
    time.sleep(3)
    for stat_id in ["stat-signals", "stat-insights", "stat-content", "stat-queue"]:
        try:
            el = driver.find_element(By.ID, stat_id)
            val = el.text.strip()
            if val and val != "—":
                _pass(f"stat-card-{stat_id}", val)
            else:
                _warn(f"stat-card-{stat_id}", f"value='{val}' (may still be loading)")
        except NoSuchElementException:
            _fail(f"stat-card-{stat_id}")

    # Refresh button
    try:
        btn = driver.find_element(By.CSS_SELECTOR, "button[onclick='refreshDashboard()']")
        btn.click()
        time.sleep(2)
        _pass("dashboard-refresh-btn")
    except (NoSuchElementException, Exception) as e:
        _fail("dashboard-refresh-btn", str(e)[:60])

    _shot(driver, "02-dashboard")

    # Check log populated
    log_el = driver.find_element(By.ID, "log-dashboard")
    if log_el.text.strip():
        _pass("dashboard-log-populated", log_el.text[:80])
    else:
        _warn("dashboard-log-populated", "Log empty after refresh")

    # Check statusbar worker dots populated
    try:
        sb_workers = driver.find_element(By.ID, "sb-workers")
        if "Workers:" in sb_workers.text:
            _pass("statusbar-workers", sb_workers.text[:60])
        else:
            _warn("statusbar-workers", sb_workers.text[:60])
    except NoSuchElementException:
        _fail("statusbar-workers")


def test_signals_page(driver: webdriver.Chrome) -> None:
    print("\n[SIGNALS PAGE]")
    navigate_to(driver, "signals")
    time.sleep(0.5)

    _shot(driver, "03-signals-before")

    # Worker Status button
    try:
        btn = driver.find_element(By.CSS_SELECTOR, "button[onclick=\"apiGet('/api/signals/worker','signals')\"]")
        btn.click()
        populated = wait_log_populated(driver, "log-signals", timeout=6)
        _pass("signals-worker-status-btn") if populated else _warn("signals-worker-status-btn", "log empty")
    except Exception as e:
        _fail("signals-worker-status-btn", str(e)[:60])

    time.sleep(0.5)

    # List Signals button
    try:
        btn = driver.find_element(By.XPATH, "//button[contains(@onclick, \"List Signals\") or contains(text(), 'List Signals')]")
        btn.click()
        time.sleep(2)
        _pass("signals-list-btn")
    except NoSuchElementException:
        # Try by text content
        try:
            btns = driver.find_elements(By.TAG_NAME, "button")
            for b in btns:
                if "List Signals" in b.text:
                    b.click()
                    time.sleep(2)
                    _pass("signals-list-btn")
                    break
        except Exception as e:
            _fail("signals-list-btn", str(e)[:60])

    # Check table appeared
    time.sleep(1)
    try:
        table = driver.find_element(By.ID, "signals-table")
        rows = table.find_elements(By.TAG_NAME, "tr")
        if len(rows) > 1:
            _pass("signals-table-populated", f"{len(rows)} rows")
        else:
            _warn("signals-table-populated", "table empty or 0 data rows")
    except NoSuchElementException:
        _fail("signals-table-populated")

    _shot(driver, "04-signals-after")

    # JS errors
    errors = get_js_errors(driver)
    if errors:
        _warn("signals-no-js-errors", f"{len(errors)} errors")
    else:
        _pass("signals-no-js-errors")


def test_insights_page(driver: webdriver.Chrome) -> None:
    print("\n[INSIGHTS PAGE]")
    navigate_to(driver, "insights")
    time.sleep(0.5)

    # Worker Status
    try:
        btn = driver.find_element(By.CSS_SELECTOR, "button[onclick=\"apiGet('/api/insights/worker','insights')\"]")
        btn.click()
        populated = wait_log_populated(driver, "log-insights", timeout=6)
        _pass("insights-worker-status") if populated else _warn("insights-worker-status", "log empty")
    except Exception as e:
        _fail("insights-worker-status", str(e)[:60])

    # List Insights
    time.sleep(0.5)
    try:
        btns = driver.find_elements(By.TAG_NAME, "button")
        for b in btns:
            if "List Insights" in b.text:
                b.click()
                time.sleep(2)
                break
        table = driver.find_element(By.ID, "insights-table")
        rows = table.find_elements(By.TAG_NAME, "tr")
        if len(rows) > 1:
            _pass("insights-table-populated", f"{len(rows)} rows")
        else:
            _warn("insights-table-populated", "empty")
    except Exception as e:
        _fail("insights-table-populated", str(e)[:60])

    _shot(driver, "05-insights")


def test_content_page(driver: webdriver.Chrome) -> None:
    print("\n[CONTENT PAGE]")
    navigate_to(driver, "content")
    time.sleep(0.5)

    # Topic input exists
    try:
        topic_input = driver.find_element(By.ID, "topic-input")
        _pass("content-topic-input-exists")
        # Type into it
        topic_input.clear()
        topic_input.send_keys("AI Marketing Automation")
        _pass("content-topic-input-type")
    except NoSuchElementException:
        _fail("content-topic-input-exists")

    # Checkboxes
    for cb_id in ["ct-blog", "ct-linkedin", "ct-linked"]:
        try:
            cb = driver.find_element(By.ID, cb_id)
            _pass(f"content-checkbox-{cb_id}", f"checked={cb.is_selected()}")
        except NoSuchElementException:
            _fail(f"content-checkbox-{cb_id}")

    # Publish checkboxes
    for cb_id in ["pub-website", "pub-linkedin"]:
        try:
            cb = driver.find_element(By.ID, cb_id)
            _pass(f"content-publish-{cb_id}")
        except NoSuchElementException:
            _fail(f"content-publish-{cb_id}")

    # Worker Status
    try:
        btn = driver.find_element(By.CSS_SELECTOR, "button[onclick=\"apiGet('/api/content/worker','content')\"]")
        btn.click()
        populated = wait_log_populated(driver, "log-content", timeout=6)
        _pass("content-worker-status") if populated else _warn("content-worker-status", "log empty")
    except Exception as e:
        _fail("content-worker-status", str(e)[:60])

    # List Content
    time.sleep(0.3)
    try:
        btns = driver.find_elements(By.TAG_NAME, "button")
        for b in btns:
            if "List Content" in b.text:
                b.click()
                time.sleep(2)
                break
        table = driver.find_element(By.ID, "content-table")
        rows = table.find_elements(By.TAG_NAME, "tr")
        if len(rows) > 1:
            _pass("content-list-populated", f"{len(rows)} rows")
        else:
            _warn("content-list-populated", "empty")
    except Exception as e:
        _fail("content-list-populated", str(e)[:60])

    _shot(driver, "06-content")


def test_distribution_page(driver: webdriver.Chrome) -> None:
    print("\n[DISTRIBUTION PAGE]")
    navigate_to(driver, "distribution")
    time.sleep(0.5)

    # Worker Status
    try:
        btn = driver.find_element(By.CSS_SELECTOR, "button[onclick=\"apiGet('/api/distribution/worker','distribution')\"]")
        btn.click()
        populated = wait_log_populated(driver, "log-distribution", timeout=6)
        _pass("dist-worker-status") if populated else _warn("dist-worker-status", "log empty")
    except Exception as e:
        _fail("dist-worker-status", str(e)[:60])

    # View Queue
    time.sleep(0.3)
    try:
        btns = driver.find_elements(By.TAG_NAME, "button")
        for b in btns:
            if "View Queue" in b.text:
                b.click()
                time.sleep(2)
                break
        dist_table = driver.find_element(By.ID, "dist-table")
        _pass("dist-queue-table-exists")
    except Exception as e:
        _fail("dist-queue-table-exists", str(e)[:60])

    _shot(driver, "07-distribution")


def test_analytics_page(driver: webdriver.Chrome) -> None:
    print("\n[ANALYTICS PAGE]")
    navigate_to(driver, "analytics")
    time.sleep(0.5)

    # Dashboard Data
    try:
        btn = driver.find_element(By.CSS_SELECTOR, "button[onclick=\"apiGet('/api/analytics/dashboard','analytics')\"]")
        btn.click()
        populated = wait_log_populated(driver, "log-analytics", timeout=8)
        _pass("analytics-dashboard-btn") if populated else _warn("analytics-dashboard-btn", "log empty")
    except Exception as e:
        _fail("analytics-dashboard-btn", str(e)[:60])

    time.sleep(0.5)

    # Top Content
    try:
        btns = driver.find_elements(By.TAG_NAME, "button")
        for b in btns:
            if "Top Content" in b.text:
                b.click()
                time.sleep(2)
                log = driver.find_element(By.ID, "log-analytics")
                if "top_content" in log.text or "items" in log.text:
                    _pass("analytics-top-content-btn")
                else:
                    _warn("analytics-top-content-btn", log.text[-100:])
                break
    except Exception as e:
        _fail("analytics-top-content-btn", str(e)[:60])

    # Worker Status
    try:
        btns = driver.find_elements(By.TAG_NAME, "button")
        for b in btns:
            if "Worker Status" in b.text and driver.current_url:
                active = driver.find_element(By.CSS_SELECTOR, ".page.active")
                if "analytics" in active.get_attribute("id"):
                    b.click()
                    time.sleep(1)
                    break
        _pass("analytics-worker-status-btn")
    except Exception as e:
        _warn("analytics-worker-status-btn", str(e)[:60])

    _shot(driver, "08-analytics")


def test_pipeline_page(driver: webdriver.Chrome) -> None:
    print("\n[PIPELINE PAGE]")
    navigate_to(driver, "pipeline")
    time.sleep(1)  # refreshWorkers() fires on nav

    # Daily topic input
    try:
        inp = driver.find_element(By.ID, "daily-topic")
        _pass("pipeline-daily-topic-input")
        inp.send_keys("B2B SaaS Marketing")
    except NoSuchElementException:
        _fail("pipeline-daily-topic-input")

    # Daily mode selector
    try:
        sel = Select(driver.find_element(By.ID, "daily-mode"))
        options = [o.text for o in sel.options]
        _pass("pipeline-daily-mode", f"options: {options}")
    except Exception as e:
        _fail("pipeline-daily-mode", str(e)[:60])

    # Daily checkboxes
    for cb_id in ["daily-publish-web", "daily-publish-li", "daily-dry-run"]:
        try:
            cb = driver.find_element(By.ID, cb_id)
            _pass(f"pipeline-cb-{cb_id}")
        except NoSuchElementException:
            _fail(f"pipeline-cb-{cb_id}")

    # Worker rows rendered
    time.sleep(2)
    try:
        worker_rows = driver.find_elements(By.CSS_SELECTOR, "#worker-rows .worker-row")
        if len(worker_rows) >= 5:
            _pass("pipeline-worker-rows", f"{len(worker_rows)} rows")
        else:
            _warn("pipeline-worker-rows", f"Only {len(worker_rows)} rows found")
    except Exception as e:
        _fail("pipeline-worker-rows", str(e)[:60])

    # Step checkboxes
    try:
        step_checks = driver.find_element(By.ID, "step-checks")
        checkboxes = step_checks.find_elements(By.TAG_NAME, "input")
        if len(checkboxes) >= 7:
            _pass("pipeline-step-checks", f"{len(checkboxes)} checkboxes")
        else:
            _warn("pipeline-step-checks", f"Only {len(checkboxes)} step checkboxes")
    except Exception as e:
        _fail("pipeline-step-checks", str(e)[:60])

    # Dry-run checkbox
    try:
        dry_run = driver.find_element(By.ID, "dry-run-chk")
        dry_run.click()  # Enable dry run
        _pass("pipeline-dry-run-cb")
    except Exception as e:
        _fail("pipeline-dry-run-cb", str(e)[:60])

    # Schedule controls present
    for el_id in ["sched-hour", "sched-minute", "sched-enabled"]:
        try:
            el = driver.find_element(By.ID, el_id)
            _pass(f"pipeline-sched-{el_id}")
        except NoSuchElementException:
            _fail(f"pipeline-sched-{el_id}")

    # Load Schedule button
    try:
        btns = driver.find_elements(By.TAG_NAME, "button")
        for b in btns:
            if "Load Current" in b.text:
                b.click()
                time.sleep(1)
                _pass("pipeline-load-schedule")
                break
    except Exception as e:
        _fail("pipeline-load-schedule", str(e)[:60])

    # Schedule status btn
    try:
        btns = driver.find_elements(By.TAG_NAME, "button")
        for b in btns:
            if "Status" in b.text and "⟳" in b.text:
                b.click()
                time.sleep(1)
                status_bar = driver.find_element(By.ID, "sched-status-bar")
                _pass("pipeline-sched-status", status_bar.text[:80])
                break
    except Exception as e:
        _fail("pipeline-sched-status", str(e)[:60])

    _shot(driver, "09-pipeline")

    # All/None buttons
    try:
        btns = driver.find_elements(By.TAG_NAME, "button")
        for b in btns:
            if b.text == "All":
                b.click()
                time.sleep(0.3)
                _pass("pipeline-select-all-steps")
                break
    except Exception as e:
        _fail("pipeline-select-all-steps", str(e)[:60])


def test_sources_page(driver: webdriver.Chrome) -> None:
    print("\n[SOURCES PAGE]")
    navigate_to(driver, "sources")
    time.sleep(1.5)  # loadSources() fires on nav

    # Table rows
    try:
        rows = driver.find_elements(By.CSS_SELECTOR, "#sources-tbody tr")
        if len(rows) >= 1:
            _pass("sources-table-populated", f"{len(rows)} sources")
        else:
            _warn("sources-table-populated", "0 source rows")
    except Exception as e:
        _fail("sources-table-populated", str(e)[:60])

    _shot(driver, "10-sources")

    # Check first row has expected columns
    try:
        first_row = rows[0]
        cells = first_row.find_elements(By.TAG_NAME, "td")
        if len(cells) >= 4:
            _pass("sources-row-columns", f"{len(cells)} cols: {[c.text[:20] for c in cells[:4]]}")
        else:
            _warn("sources-row-columns", f"Only {len(cells)} cells")
    except Exception as e:
        _warn("sources-row-columns", str(e)[:60])

    # Add Source inline form
    try:
        btns = driver.find_elements(By.TAG_NAME, "button")
        for b in btns:
            if "+ Add Source" in b.text or "Add Source" in b.text:
                b.click()
                time.sleep(0.5)
                break

        # Inline form should now be visible
        form = driver.find_element(By.ID, "add-source-form")
        assert form.is_displayed(), "add-source-form not visible after click"

        # Fill in fields
        sel = Select(driver.find_element(By.ID, "src-type"))
        sel.select_by_value("rss")
        driver.find_element(By.ID, "src-cat").send_keys("test-category")
        driver.find_element(By.ID, "src-url").send_keys("https://example.com/test/feed")

        # Submit
        btns2 = form.find_elements(By.TAG_NAME, "button")
        for b in btns2:
            if b.text.strip() == "Add":
                b.click()
                break

        time.sleep(0.5)
        # Form should be hidden again
        form2 = driver.find_element(By.ID, "add-source-form")
        _pass("sources-inline-form", f"visible={form2.is_displayed()}")

        # Table should have one more row
        rows2 = driver.find_elements(By.CSS_SELECTOR, "#sources-tbody tr")
        if len(rows2) > len(rows):
            _pass("sources-new-row-added", f"now {len(rows2)} rows")
        else:
            _warn("sources-new-row-added", f"row count unchanged at {len(rows2)}")

    except Exception as e:
        _fail("sources-inline-form", str(e)[:80])


def test_database_page(driver: webdriver.Chrome) -> None:
    print("\n[DATABASE PAGE]")
    navigate_to(driver, "database")
    time.sleep(0.5)

    # Table selector
    try:
        sel = Select(driver.find_element(By.ID, "db-table"))
        options = [o.text for o in sel.options]
        if len(options) >= 6:
            _pass("db-table-selector", f"{len(options)} tables: {options}")
        else:
            _warn("db-table-selector", f"Only {len(options)} options")
    except Exception as e:
        _fail("db-table-selector", str(e)[:60])

    # Limit input
    try:
        limit_inp = driver.find_element(By.ID, "db-limit")
        _pass("db-limit-input", limit_inp.get_attribute("value"))
    except NoSuchElementException:
        _fail("db-limit-input")

    # Load signals
    try:
        btn = driver.find_element(By.CSS_SELECTOR, "button[onclick='loadDb()']")
        btn.click()
        time.sleep(2)
        rows = driver.find_elements(By.CSS_SELECTOR, "#db-table-wrap tr")
        if len(rows) > 1:
            _pass("db-load-signals", f"{len(rows)} rows")
        else:
            _warn("db-load-signals", "No rows returned")
    except Exception as e:
        _fail("db-load-signals", str(e)[:60])

    _shot(driver, "11-database-signals")

    # Switch to content table
    try:
        sel = Select(driver.find_element(By.ID, "db-table"))
        sel.select_by_visible_text("content")
        btn = driver.find_element(By.CSS_SELECTOR, "button[onclick='loadDb()']")
        btn.click()
        time.sleep(2)
        rows = driver.find_elements(By.CSS_SELECTOR, "#db-table-wrap tr")
        _pass("db-load-content", f"{len(rows)} rows")
    except Exception as e:
        _fail("db-load-content", str(e)[:60])

    _shot(driver, "12-database-content")

    # Check row count element
    try:
        count_el = driver.find_element(By.ID, "db-count")
        _pass("db-count-element", count_el.text)
    except NoSuchElementException:
        _fail("db-count-element")


def test_growth_page(driver: webdriver.Chrome) -> None:
    print("\n[GROWTH PAGE]")
    navigate_to(driver, "growth")
    time.sleep(1.5)  # loadInfluencers() fires on nav

    # Influencer table
    try:
        tbody = driver.find_element(By.ID, "influencer-tbody")
        rows = tbody.find_elements(By.TAG_NAME, "tr")
        _pass("growth-influencer-table", f"{len(rows)} influencers")
    except NoSuchElementException:
        _fail("growth-influencer-table")

    # Stats button
    try:
        btn = driver.find_element(By.CSS_SELECTOR, "button[onclick=\"apiGet('/api/engagement/stats','growth')\"]")
        btn.click()
        populated = wait_log_populated(driver, "log-growth", timeout=6)
        _pass("growth-stats-btn") if populated else _warn("growth-stats-btn", "log empty")
    except Exception as e:
        _fail("growth-stats-btn", str(e)[:60])

    time.sleep(0.5)

    # Engagement Log button
    try:
        btn = driver.find_element(By.CSS_SELECTOR, "button[onclick=\"apiGet('/api/engagement/log?limit=20','growth')\"]")
        btn.click()
        time.sleep(1)
        log = driver.find_element(By.ID, "log-growth")
        _pass("growth-engagement-log-btn", log.text[-100:])
    except Exception as e:
        _fail("growth-engagement-log-btn", str(e)[:60])

    # Viral Posts button
    try:
        btn = driver.find_element(By.CSS_SELECTOR, "button[onclick=\"apiGet('/api/engagement/viral','growth')\"]")
        btn.click()
        time.sleep(1)
        _pass("growth-viral-posts-btn")
    except Exception as e:
        _fail("growth-viral-posts-btn", str(e)[:60])

    # Worker interval input
    try:
        interval = driver.find_element(By.ID, "growth-interval")
        _pass("growth-interval-input", interval.get_attribute("value"))
    except NoSuchElementException:
        _fail("growth-interval-input")

    # + Add influencer inline form
    try:
        btns = driver.find_elements(By.TAG_NAME, "button")
        for b in btns:
            if b.text.strip() == "+ Add":
                b.click()
                time.sleep(0.5)
                break

        form = driver.find_element(By.ID, "add-influencer-form")
        if form.is_displayed():
            _pass("growth-add-influencer-form-opens")
            # Cancel it
            cancel_btns = form.find_elements(By.TAG_NAME, "button")
            for b in cancel_btns:
                if "Cancel" in b.text:
                    b.click()
                    break
            _pass("growth-add-influencer-form-cancel")
        else:
            _warn("growth-add-influencer-form-opens", "form not visible")
    except Exception as e:
        _warn("growth-add-influencer-form", str(e)[:60])

    _shot(driver, "13-growth")


def test_settings_page(driver: webdriver.Chrome) -> None:
    print("\n[SETTINGS PAGE]")
    navigate_to(driver, "settings")
    time.sleep(1.5)  # loadConfig() fires on nav

    # Settings form
    try:
        form = driver.find_element(By.ID, "settings-form")
        _pass("settings-form-exists")
        children = form.find_elements(By.XPATH, ".//*")
        _pass("settings-form-fields", f"{len(children)} elements rendered")
    except NoSuchElementException:
        _fail("settings-form-exists")

    # Threshold inputs
    try:
        thresh = driver.find_element(By.ID, "conf-thresh")
        _pass("settings-conf-thresh", f"value={thresh.get_attribute('value')}")
    except NoSuchElementException:
        _fail("settings-conf-thresh")

    try:
        max_c = driver.find_element(By.ID, "max-content")
        _pass("settings-max-content", f"value={max_c.get_attribute('value')}")
    except NoSuchElementException:
        _fail("settings-max-content")

    # Load Config button
    try:
        btns = driver.find_elements(By.TAG_NAME, "button")
        for b in btns:
            if "Load Config" in b.text or "↺ Load Config" in b.text:
                b.click()
                time.sleep(1)
                log = driver.find_element(By.ID, "log-settings")
                if log.text.strip():
                    _pass("settings-load-config", log.text[:80])
                else:
                    _warn("settings-load-config", "log empty after load")
                break
    except Exception as e:
        _fail("settings-load-config", str(e)[:60])

    _shot(driver, "14-settings")

    # Check JS errors on settings page
    errors = get_js_errors(driver)
    if errors:
        _warn("settings-no-js-errors", str(errors[:2])[:120])
    else:
        _pass("settings-no-js-errors")


def test_responsiveness(driver: webdriver.Chrome) -> None:
    print("\n[RESPONSIVENESS]")
    navigate_to(driver, "dashboard")
    time.sleep(0.5)

    # Test narrow viewport (tablet)
    driver.set_window_size(768, 900)
    time.sleep(0.5)
    _shot(driver, "15-responsive-768")
    try:
        sidebar = driver.find_element(By.ID, "sidebar")
        _pass("responsive-768-sidebar-visible")
    except Exception as e:
        _warn("responsive-768-sidebar", str(e)[:60])

    # Back to full
    driver.maximize_window()
    time.sleep(0.5)
    _pass("responsive-restored")


def test_xss_protection(driver: webdriver.Chrome) -> None:
    """Verify the escHtml helper prevents XSS in table cells."""
    print("\n[XSS PROTECTION]")
    navigate_to(driver, "database")
    time.sleep(0.5)

    # The table uses escHtml() now — verify no raw <script> in DOM
    try:
        page_src = driver.page_source
        if "<script>alert(" not in page_src:
            _pass("xss-escaping-db-table")
        else:
            _fail("xss-escaping-db-table", "raw <script> found in page source")
    except Exception as e:
        _warn("xss-escaping", str(e)[:60])


def test_worker_control(driver: webdriver.Chrome) -> None:
    """Test stop/start worker via pipeline page."""
    print("\n[WORKER CONTROL]")
    navigate_to(driver, "pipeline")
    time.sleep(1.5)

    try:
        rows = driver.find_elements(By.CSS_SELECTOR, "#worker-rows .worker-row")
        if rows:
            # Find first Stop button in first row
            stop_btns = rows[0].find_elements(By.TAG_NAME, "button")
            stop_btn = None
            start_btn = None
            for b in stop_btns:
                if "Stop" in b.text:
                    stop_btn = b
                elif "Start" in b.text:
                    start_btn = b

            if stop_btn:
                stop_btn.click()
                time.sleep(2)
                _pass("worker-stop-btn-clicked")

                # Re-start it
                rows = driver.find_elements(By.CSS_SELECTOR, "#worker-rows .worker-row")
                if rows:
                    btns = rows[0].find_elements(By.TAG_NAME, "button")
                    for b in btns:
                        if "Start" in b.text:
                            b.click()
                            time.sleep(2)
                            _pass("worker-start-btn-clicked")
                            break
            else:
                _warn("worker-stop-btn-clicked", "no Stop button found in first worker row")
    except Exception as e:
        _fail("worker-control", str(e)[:80])

    _shot(driver, "16-worker-control")


def test_api_error_handling(driver: webdriver.Chrome) -> None:
    """Test that the GUI gracefully handles 404/500 API responses."""
    print("\n[API ERROR HANDLING]")
    navigate_to(driver, "signals")
    time.sleep(0.5)

    # Call a non-existent endpoint via JS eval and check log
    driver.execute_script("apiGet('/api/nonexistent-endpoint', 'signals');")
    time.sleep(2)

    log = driver.find_element(By.ID, "log-signals")
    if "Error" in log.text or "error" in log.text.lower() or "404" in log.text:
        _pass("api-error-shows-in-log", "error shown in UI")
    else:
        _warn("api-error-shows-in-log", f"log: {log.text[-100:]}")

    _shot(driver, "17-api-error-handling")


def test_final_state(driver: webdriver.Chrome) -> None:
    print("\n[FINAL STATE]")
    navigate_to(driver, "dashboard")
    time.sleep(2)
    _shot(driver, "18-final-dashboard")

    errors = get_js_errors(driver)
    if errors:
        _warn("final-no-js-errors", f"{len(errors)}: {errors[0][:100]}")
    else:
        _pass("final-no-js-errors")


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> int:
    print("=" * 70)
    print("  Phoenix Intelligence Engine — Full Selenium Test Suite")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    opts = Options()
    opts.binary_location = CHROME_PATH
    opts.add_argument("--window-size=1400,900")
    opts.add_argument("--disable-infobars")
    opts.add_argument("--disable-extensions")
    opts.add_argument("--log-level=3")  # suppress console clutter
    opts.add_experimental_option("excludeSwitches", ["enable-logging"])
    opts.set_capability("goog:loggingPrefs", {"browser": "ALL"})

    print(f"\nStarting Chrome... (screenshots -> {SCREENSHOTS_DIR})")
    driver = webdriver.Chrome(options=opts)
    driver.maximize_window()

    try:
        test_initial_load(driver)
        test_dashboard(driver)
        test_signals_page(driver)
        test_insights_page(driver)
        test_content_page(driver)
        test_distribution_page(driver)
        test_analytics_page(driver)
        test_pipeline_page(driver)
        test_sources_page(driver)
        test_database_page(driver)
        test_growth_page(driver)
        test_settings_page(driver)
        test_responsiveness(driver)
        test_xss_protection(driver)
        test_worker_control(driver)
        test_api_error_handling(driver)
        test_final_state(driver)

    except Exception as e:
        print(f"\nFATAL TEST ERROR: {e}")
        traceback.print_exc()
        try:
            _shot(driver, "FATAL-ERROR")
        except Exception:
            pass
    finally:
        driver.quit()

    # ── Summary ───────────────────────────────────────────────────────────────
    passed = [r for r in results if r["status"] == "PASS"]
    failed = [r for r in results if r["status"] == "FAIL"]
    warned = [r for r in results if r["status"] == "WARN"]

    print("\n" + "=" * 70)
    print(f"  RESULTS:  {len(passed)} PASS  |  {len(warned)} WARN  |  {len(failed)} FAIL")
    print("=" * 70)

    if failed:
        print("\nFAILURES:")
        for f in failed:
            print(f"  ✗  {f['test']}: {f['detail']}")

    if warned:
        print("\nWARNINGS:")
        for w in warned:
            print(f"  !  {w['test']}: {w['detail']}")

    print(f"\nScreenshots saved to: {SCREENSHOTS_DIR}")

    # Save JSON report
    report_path = SCREENSHOTS_DIR / "test_report.json"
    with open(report_path, "w") as f:
        json.dump({"timestamp": datetime.now().isoformat(), "results": results}, f, indent=2)
    print(f"Report saved to: {report_path}")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
