#!/usr/bin/env python3
"""Debug: Check THREE instance identity."""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
    page = ctx.new_page()

    page.goto("http://localhost:5177", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(10000)

    # Check THREE instance identity
    result = page.evaluate("""() => {
        // Check if window.THREE is the same as the one used by three-forcegraph
        // We can check this by comparing the Mesh constructor
        const mesh1 = new window.THREE.Mesh();
        const mesh2 = new window.THREE.Mesh();
        
        return {
            windowTHREE: !!window.THREE,
            windowTHREEVersion: window.THREE ? window.THREE.REVISION : 'none',
            mesh1Type: mesh1.type,
            mesh2Type: mesh2.type,
            sameConstructor: mesh1.constructor === mesh2.constructor,
        };
    }""")

    print(f"THREE identity: {result}")

    browser.close()
