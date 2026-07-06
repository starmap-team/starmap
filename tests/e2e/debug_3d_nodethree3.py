#!/usr/bin/env python3
"""Debug: Override nodeThreeObject to check if it's called."""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
    page = ctx.new_page()

    # Inject a script before page load to intercept nodeThreeObject
    page.add_init_script("""
        window.__nodeThreeObjectCalls = [];
        window.__originalNodeThreeObject = null;
    """)

    page.goto("http://localhost:5173", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(10000)

    # Check if nodeThreeObject was called
    result = page.evaluate("""() => {
        return {
            calls: window.__nodeThreeObjectCalls.length,
            firstFew: window.__nodeThreeObjectCalls.slice(0, 5),
        };
    }""")

    print(f"nodeThreeObject calls: {result}")

    browser.close()
