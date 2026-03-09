"""Save LinkedIn session cookies for the engagement engine.

Run this script once to authenticate and export your LinkedIn session:

    python save_linkedin_cookies.py

A browser window will open. Log in to LinkedIn manually, then press Enter
in this terminal. Cookies will be saved to linkedin_session.json in the
project root.
"""

from __future__ import annotations

import json
from pathlib import Path

OUTPUT = Path("linkedin_session.json")


def main() -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("ERROR: playwright not installed. Run: pip install playwright && playwright install chromium")
        return

    print("Opening LinkedIn login page in a visible browser window...")
    print("1. Log in to LinkedIn in the browser that opens.")
    print("2. Once the feed has loaded, come back here and press Enter.")
    print()

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto("https://www.linkedin.com/login", timeout=30_000)

        input("Press Enter after you have logged in and the LinkedIn feed is visible...")

        cookies = context.cookies()
        browser.close()

    OUTPUT.write_text(json.dumps(cookies, indent=2), encoding="utf-8")
    print(f"\nSaved {len(cookies)} cookies to {OUTPUT.resolve()}")
    print("The engagement engine will now use this session.")


if __name__ == "__main__":
    main()
