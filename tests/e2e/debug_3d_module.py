#!/usr/bin/env python3
"""Debug: Check module content via fetch."""
from playwright.sync_api import sync_playwright
import urllib.request

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
    page = ctx.new_page()

    page.goto("http://localhost:5173", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(5000)

    # Get all script srcs
    scripts = page.evaluate("""() => {
        return Array.from(document.querySelectorAll('script')).map(s => s.src).filter(Boolean);
    }""")

    print(f"Scripts ({len(scripts)}):")
    for src in scripts[:10]:
        print(f"  {src[:100]}")

    # Find Graph3D module
    graph3d_url = None
    for src in scripts:
        if 'Graph3D' in src:
            graph3d_url = src
            break

    if graph3d_url:
        print(f"\nGraph3D module: {graph3d_url}")
        req = urllib.request.Request(graph3d_url, headers={'Accept': '*/*'})
        content = urllib.request.urlopen(req).read().decode('utf-8')
        print(f"Contains 'onMounted START': {'onMounted START' in content}")
        print(f"Contains 'nodeThreeObject called': {'nodeThreeObject called' in content}")
    else:
        print("\nNo Graph3D module found in scripts")

    browser.close()
