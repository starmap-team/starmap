#!/usr/bin/env python3
"""Debug: Check which module is loaded."""
from playwright.sync_api import sync_playwright
import urllib.request

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
    page = ctx.new_page()

    page.goto("http://localhost:5173", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(5000)

    # Check the module map
    result = page.evaluate("""() => {
        return {
            hasViteClient: !!document.querySelector('script[src=\"/@vite/client\"]'),
        };
    }""")

    print(f"Module check: {result}")

    # Try to fetch the Graph3D module directly
    url = "http://localhost:5173/src/components/Graph3D.vue"
    try:
        req = urllib.request.Request(url, headers={'Accept': '*/*'})
        content = urllib.request.urlopen(req).read().decode('utf-8')
        print(f"Module contains 'onMounted START': {'onMounted START' in content}")
        print(f"Module contains 'watch triggered': {'watch triggered' in content}")
    except Exception as e:
        print(f"Error fetching module: {e}")

    browser.close()
