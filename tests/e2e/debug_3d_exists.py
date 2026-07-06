#!/usr/bin/env python3
"""Debug: Check if Graph3D component is rendered."""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
    page = ctx.new_page()

    page.goto("http://localhost:5173", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(5000)

    # Check if Graph3D component exists
    result = page.evaluate("""() => {
        const graph3d = document.querySelector('.graph3d-wrapper');
        const container = document.querySelector('.graph3d-container');
        const canvas = document.querySelector('.graph3d-container canvas');
        const fallback = document.querySelector('.webgl-fallback');

        return {
            hasGraph3D: !!graph3d,
            hasContainer: !!container,
            hasCanvas: !!canvas,
            hasFallback: !!fallback,
            fallbackVisible: fallback ? window.getComputedStyle(fallback).display !== 'none' : false,
            containerVisible: container ? window.getComputedStyle(container).display !== 'none' : false,
        };
    }""")

    print(f"Graph3D check: {result}")

    browser.close()
