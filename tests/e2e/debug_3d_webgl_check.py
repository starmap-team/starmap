#!/usr/bin/env python3
"""Debug: Check if WebGL is supported."""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
    page = ctx.new_page()

    page.goto("http://localhost:5173", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(10000)

    # Check if WebGL fallback is visible
    result = page.evaluate("""() => {
        const fallback = document.querySelector('.webgl-fallback');
        const container = document.querySelector('.graph3d-container');
        return {
            fallbackVisible: fallback ? window.getComputedStyle(fallback).display !== 'none' : false,
            containerVisible: container ? window.getComputedStyle(container).display !== 'none' : false,
            containerChildren: container ? container.children.length : 0,
        };
    }""")

    print(f"WebGL check: {result}")

    browser.close()
