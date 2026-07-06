#!/usr/bin/env python3
"""Debug: Check 3D scene rendering."""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
    page = ctx.new_page()

    page.goto("http://localhost:5177", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(15000)

    # Check the WebGL context
    result = page.evaluate("""() => {
        const canvas = document.querySelector('.graph3d-container canvas');
        if (!canvas) return {error: 'No canvas'};

        const gl = canvas.getContext('webgl') || canvas.getContext('webgl2');
        if (!gl) return {error: 'No WebGL context'};

        // Check if the canvas has been drawn to
        const pixels = new Uint8Array(4);
        gl.readPixels(0, 0, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, pixels);

        // Check the center of the canvas
        const centerX = Math.floor(canvas.width / 2);
        const centerY = Math.floor(canvas.height / 2);
        const centerPixels = new Uint8Array(4);
        gl.readPixels(centerX, centerY, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, centerPixels);

        return {
            canvasSize: {width: canvas.width, height: canvas.height},
            topLeftPixel: {r: pixels[0], g: pixels[1], b: pixels[2], a: pixels[3]},
            centerPixel: {r: centerPixels[0], g: centerPixels[1], b: centerPixels[2], a: centerPixels[3]},
        };
    }""")

    print(f"WebGL pixels: {result}")

    browser.close()
