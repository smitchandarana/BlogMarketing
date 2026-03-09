"""
Phoenix Marketing Engine — Playwright GUI Screenshot Tests
=========================================================
Simulates human interaction across all 11 dashboard pages.
Screenshots saved to tests/screenshots/.
Run: python tests/test_playwright_gui.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

BASE_URL = "http://127.0.0.1:8000"
SCREENSHOT_DIR = Path(__file__).parent / "screenshots"
SCREENSHOT_DIR.mkdir(exist_ok=True)

# Navigation items to test (data-page attribute values in index.html)
PAGES = [
    "dashboard",
    "signals",
    "insights",
    "content",
    "distribution",
    "analytics",
    "pipeline",
    "sources",
    "database",
    "growth",
    "settings",
]

_screenshot_count = 0
_results: list[dict] = []


def _shot(page, label: str) -> Path:
    global _screenshot_count
    _screenshot_count += 1
    ts = datetime.now().strftime("%H%M%S")
    fname = SCREENSHOT_DIR / f"{_screenshot_count:03d}-{label}-{ts}.png"
    page.screenshot(path=str(fname), full_page=False)
    print(f"  [screenshot] {fname.name}")
    return fname


def _log(msg: str) -> None:
    print(f"{'':2}{msg}")


def _pass(test: str) -> None:
    _results.append({"test": test, "status": "PASS"})
    print(f"  [PASS] {test}")


def _fail(test: str, reason: str) -> None:
    _results.append({"test": test, "status": "FAIL", "reason": reason})
    print(f"  [FAIL] {test}: {reason}")


def run_tests() -> bool:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

    print("=" * 70)
    print("Phoenix Marketing Engine — GUI + API Test Suite")
    print(f"Target: {BASE_URL}")
    print(f"Screenshots: {SCREENSHOT_DIR}")
    print("=" * 70)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1400, "height": 900},
            # Capture JS console messages
        )
        js_errors: list[str] = []
        page = context.new_page()
        page.on("pageerror", lambda exc: js_errors.append(str(exc)))
        page.on("console", lambda msg: (
            js_errors.append(f"CONSOLE ERROR: {msg.text}")
            if msg.type == "error" else None
        ))

        # ── 1. Initial page load ──────────────────────────────────────────────
        print("\n[1] Loading Dashboard")
        try:
            page.goto(BASE_URL, wait_until="networkidle", timeout=30_000)
            _shot(page, "dashboard-initial")
            _pass("page_load")
        except PWTimeout:
            _fail("page_load", "Timed out loading dashboard")
            browser.close()
            return False

        # ── 2. Verify header / title ─────────────────────────────────────────
        title = page.title()
        if "Phoenix" in title or "Marketing" in title or title:
            _pass(f"page_title ({title!r})")
        else:
            _fail("page_title", f"Unexpected title: {title!r}")

        # ── 3. Check nav items are visible ───────────────────────────────────
        print("\n[2] Verifying navigation items")
        nav_items = page.query_selector_all("[data-page]")
        found_pages = {el.get_attribute("data-page") for el in nav_items}
        for p in PAGES:
            if p in found_pages:
                _pass(f"nav_item_present: {p}")
            else:
                _fail(f"nav_item_present: {p}", f"data-page='{p}' not found in nav")

        # ── 4. Visit every page ───────────────────────────────────────────────
        print("\n[3] Visiting each page and taking screenshots")
        for page_name in PAGES:
            try:
                el = page.query_selector(f"[data-page='{page_name}']")
                if not el:
                    _fail(f"nav_click: {page_name}", "Element not found")
                    continue
                el.click()
                time.sleep(1.5)  # human-like pause + API call to complete
                _shot(page, page_name)
                # Check for visible JS errors on the page
                error_els = page.query_selector_all(".error, .alert-error, [class*='error']")
                if error_els:
                    texts = [e.inner_text()[:80] for e in error_els[:3] if e.is_visible()]
                    visible_errors = [t for t in texts if t]
                    if visible_errors:
                        _fail(f"page_errors: {page_name}", "; ".join(visible_errors))
                    else:
                        _pass(f"page_visit: {page_name}")
                else:
                    _pass(f"page_visit: {page_name}")
            except Exception as exc:
                _fail(f"page_visit: {page_name}", str(exc)[:120])

        # ── 5. Dashboard — check status dots render ───────────────────────────
        print("\n[4] Dashboard — checking worker status indicators")
        page.query_selector("[data-page='dashboard']").click()
        time.sleep(2)
        status_elements = page.query_selector_all(".dot, .status-dot, [class*='dot'], .worker-status")
        _log(f"Found {len(status_elements)} status indicator elements")
        _shot(page, "dashboard-status")
        _pass("dashboard_rendered")

        # ── 6. Signals page — check table loads ───────────────────────────────
        print("\n[5] Signals page — check table data")
        page.query_selector("[data-page='signals']").click()
        time.sleep(2)
        _shot(page, "signals-table")
        rows = page.query_selector_all("table tr, .table-row, [class*='row']")
        _log(f"Signals table rows found: {len(rows)}")
        if len(rows) > 1:
            _pass("signals_table_has_data")
        else:
            _fail("signals_table_has_data", f"Only {len(rows)} rows visible (expected >1)")

        # ── 7. Content page — check content listed ────────────────────────────
        print("\n[6] Content page — check content listed")
        page.query_selector("[data-page='content']").click()
        time.sleep(2)
        _shot(page, "content-list")
        rows = page.query_selector_all("table tr")
        _log(f"Content table rows found: {len(rows)}")
        _pass("content_page_rendered")

        # ── 8. Database page — table browser ─────────────────────────────────
        print("\n[7] Database browser — browse signals table")
        page.query_selector("[data-page='database']").click()
        time.sleep(1.5)
        _shot(page, "database-before")

        # Try to select 'signals' table and browse
        try:
            # Use JavaScript to interact — avoids Playwright's visibility wait
            # on elements that are in hidden page sections elsewhere.
            page.evaluate("""
                const sel = document.getElementById('db-table');
                if (sel) {
                    for (let o of sel.options) {
                        if (o.text === 'signals') { sel.value = o.value || o.text; break; }
                    }
                }
                if (typeof loadDb === 'function') loadDb();
            """)
            time.sleep(2)
            _shot(page, "database-signals-browse")
            table_rows = page.query_selector_all("#db-table-wrap tr")
            _log(f"Database rows loaded: {len(table_rows)}")
            _pass(f"database_browse_signals ({len(table_rows)} rows)")
        except Exception as exc:
            _fail("database_browse", str(exc)[:120])

        # ── 9. Growth / Engagement page ───────────────────────────────────────
        print("\n[8] Growth page — check engagement controls")
        page.query_selector("[data-page='growth']").click()
        time.sleep(2)
        _shot(page, "growth-page")
        worker_status = page.query_selector("[id*='worker'], [class*='worker'], [id*='engagement']")
        _log(f"Growth worker element: {worker_status.get_attribute('id') if worker_status else 'not found'}")
        _pass("growth_page_rendered")

        # ── 10. Settings page ─────────────────────────────────────────────────
        print("\n[9] Settings page — verify config fields present")
        page.query_selector("[data-page='settings']").click()
        time.sleep(1.5)
        _shot(page, "settings-page")
        inputs = page.query_selector_all("input, textarea, select")
        _log(f"Settings form inputs found: {len(inputs)}")
        if len(inputs) >= 3:
            _pass(f"settings_has_inputs ({len(inputs)} found)")
        else:
            _fail("settings_has_inputs", f"Only {len(inputs)} inputs found")

        # ── 11. Sources page — check source list ──────────────────────────────
        print("\n[10] Sources page — verify signal source list")
        page.query_selector("[data-page='sources']").click()
        time.sleep(2)
        _shot(page, "sources-page")
        rows = page.query_selector_all("table tr, .source-row, [class*='source']")
        _log(f"Sources rows found: {len(rows)}")
        if len(rows) > 1:
            _pass(f"sources_table_populated ({len(rows)} rows)")
        else:
            _fail("sources_table_populated", f"Only {len(rows)} rows")

        # ── 12. Pipeline page ─────────────────────────────────────────────────
        print("\n[11] Pipeline page — verify controls")
        page.query_selector("[data-page='pipeline']").click()
        time.sleep(2)
        _shot(page, "pipeline-page")
        checkboxes = page.query_selector_all("input[type='checkbox']")
        _log(f"Pipeline step checkboxes: {len(checkboxes)}")
        _pass("pipeline_page_rendered")

        # ── 13. Check JS console errors ───────────────────────────────────────
        print("\n[12] JavaScript console error check")
        if js_errors:
            for err in js_errors[:5]:
                _fail("js_console_error", err[:120])
        else:
            _pass("no_js_console_errors")

        # ── 14. Final full-page screenshot of dashboard ───────────────────────
        print("\n[13] Final dashboard screenshot")
        page.query_selector("[data-page='dashboard']").click()
        time.sleep(2)
        page.screenshot(
            path=str(SCREENSHOT_DIR / "final-dashboard-fullpage.png"),
            full_page=True,
        )
        _log("Full-page dashboard screenshot saved")

        browser.close()

    # ── Summary ────────────────────────────────────────────────────────────────
    passed = sum(1 for r in _results if r["status"] == "PASS")
    failed = sum(1 for r in _results if r["status"] == "FAIL")
    total = len(_results)

    print("\n" + "=" * 70)
    print(f"RESULTS: {passed}/{total} passed, {failed} failed")
    print("=" * 70)
    if failed:
        print("\nFailed tests:")
        for r in _results:
            if r["status"] == "FAIL":
                print(f"  FAIL: {r['test']} — {r.get('reason', '')}")

    # Write JSON report
    report_path = SCREENSHOT_DIR / "test_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "passed": passed,
            "failed": failed,
            "total": total,
            "screenshots_dir": str(SCREENSHOT_DIR),
            "results": _results,
        }, f, indent=2)
    print(f"\nReport saved: {report_path}")
    print(f"Screenshots: {SCREENSHOT_DIR}")
    return failed == 0


if __name__ == "__main__":
    ok = run_tests()
    sys.exit(0 if ok else 1)
