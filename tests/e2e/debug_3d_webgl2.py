#!/usr/bin/env python3
"""Debug: Check 3D scene by reading WebGL pixels."""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
    page = ctx.new_page()

    page.goto("http://localhost:5177", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(10000)

    # Read WebGL pixels
    result = page.evaluate("""() => {
        const canvas = document.querySelector('.graph3d-container canvas');
        if (!canvas) return {error: 'No canvas'};

        const gl = canvas.getContext('webgl') || canvas.getContext('webgl2');
        if (!gl) return {error: 'No WebGL context'};

        const width = canvas.width;
        const height = canvas.height;

        // Read pixels from center
        const centerX = Math.floor(width / 2);
        const centerY = Math.floor(height / 2);
        const pixels = new Uint8Array(4 * 100); // 10x10 area
        gl.readPixels(centerX - 5, centerY - 5, 10, 10, gl.RGBA, gl.UNSIGNED_BYTE, pixels);

        // Check if any pixel is not black/background
        let hasContent = false;
        for (let i = 0; i < pixels.length; i += 4) {
            if (pixels[i] > 20 || pixels[i+1] > 20 || pixels[i+2] > 20) {
                hasContent = true;
                break;
            }
        }

        return {
            canvasSize: {width, height},
            hasContent,
            centerPixels: Array.from(pixels.slice(0, 16)),
        };
    }""")

    print(f"WebGL pixels: {result}")

    browser.close()
