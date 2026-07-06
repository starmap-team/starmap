#!/usr/bin/env python3
"""Debug: Check THREE instance compatibility."""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
    page = ctx.new_page()

    page.goto("http://localhost:5177", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(10000)

    # Check THREE instances
    result = page.evaluate("""() => {
        return {
            windowTHREE: !!window.THREE,
            windowTHREEVersion: window.THREE ? window.THREE.REVISION : 'none',
            window__THREE: !!window.__THREE,
            window__THREEVersion: window.__THREE ? window.__THREE.REVISION : 'none',
        };
    }""")

    print(f"THREE instances: {result}")

    browser.close()
