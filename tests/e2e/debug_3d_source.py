#!/usr/bin/env python3
"""Debug: Check if browser loaded latest code."""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
    page = ctx.new_page()

    page.goto("http://localhost:5173", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(5000)

    # Check if the source code contains the new log
    result = page.evaluate("""() => {
        // Find the Graph3D module
        const scripts = Array.from(document.querySelectorAll('script'));
        const graph3dScript = scripts.find(s => s.src && s.src.includes('Graph3D'));
        return {
            hasGraph3DScript: !!graph3dScript,
            scriptSrc: graph3dScript?.src,
        };
    }""")

    print(f"Script check: {result}")

    # Fetch the script content
    if result.get('scriptSrc'):
        import urllib.request
        req = urllib.request.Request(result['scriptSrc'], headers={'Accept': '*/*'})
        content = urllib.request.urlopen(req).read().decode('utf-8')
        print(f"Script contains 'onMounted START': {'onMounted START' in content}")
        print(f"Script contains 'nodeThreeObject called': {'nodeThreeObject called' in content}")

    browser.close()
