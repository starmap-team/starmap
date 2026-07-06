#!/usr/bin/env python3
"""Debug: Check 3D scene by taking a screenshot."""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
    page = ctx.new_page()

    page.goto("http://localhost:5177", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(15000)

    # Take a screenshot
    page.screenshot(path="tests/e2e/screenshot_3d_debug2.png")
    print("Screenshot saved to tests/e2e/screenshot_3d_debug2.png")

    # Check the screenshot
    from PIL import Image
    img = Image.open('tests/e2e/screenshot_3d_debug2.png')
    pixels = img.load()

    # Check for bright pixels in the graph area
    bright_pixels = []
    for x in range(20, 1000):
        for y in range(250, 850):
            p = pixels[x, y]
            r, g, b = p
            if r > 50 or g > 50 or b > 50:
                if not (abs(r - g) < 20 and abs(g - b) < 20 and r > 200):
                    bright_pixels.append((x, y, p))

    print(f"Found {len(bright_pixels)} bright pixels in graph area")
    if bright_pixels:
        from collections import Counter
        colors = Counter([p[2] for p in bright_pixels])
        print('Top colors:')
        for color, count in colors.most_common(20):
            print(f'  {color}: {count}')

    browser.close()
