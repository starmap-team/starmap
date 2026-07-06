#!/usr/bin/env python3
"""Debug script: Check WebGL canvas content by reading pixels."""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
    page = ctx.new_page()

    page.goto("http://localhost:5173", wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(10000)

    # Read WebGL pixels from the center of the canvas
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

        // Also read from top-left, top-right, bottom-left, bottom-right
        const corners = [];
        for (const [x, y] of [[10, 10], [width-10, 10], [10, height-10], [width-10, height-10]]) {
            const p = new Uint8Array(4);
            gl.readPixels(x, y, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, p);
            corners.push({x, y, r: p[0], g: p[1], b: p[2], a: p[3]});
        }

        return {
            canvasSize: {width, height},
            hasContent,
            centerPixels: Array.from(pixels.slice(0, 16)), // First 4 pixels
            corners,
        };
    }""")

    print(f"WebGL pixels: {result}")

    # Now let's check if the issue is with nodeThreeObject returning null
    # by temporarily overriding it in the browser
    override_result = page.evaluate("""() => {
        // We can't easily access the graph instance, but we can check
        // if there are any Three.js objects in the scene by looking at
        // the canvas's __three property (if any)

        const canvas = document.querySelector('.graph3d-container canvas');
        if (!canvas) return {error: 'No canvas'};

        // Check if 3d-force-graph has attached any data
        const container = document.querySelector('.graph3d-container');
        return {
            containerDataKeys: Object.keys(container).filter(k => !k.startsWith('__')),
            canvasDataKeys: Object.keys(canvas).filter(k => !k.startsWith('__')),
        };
    }""")

    print(f"Override result: {override_result}")

    browser.close()
