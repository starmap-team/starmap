#!/usr/bin/env python3
"""Debug: Check if nodeThreeObject objects are in the scene."""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
    page = ctx.new_page()

    page.goto("http://localhost:5177", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(15000)

    # Check the scene
    result = page.evaluate("""() => {
        // Find the canvas
        const canvas = document.querySelector('.graph3d-container canvas');
        if (!canvas) return {error: 'No canvas'};

        // Get the WebGL context
        const gl = canvas.getContext('webgl') || canvas.getContext('webgl2');
        if (!gl) return {error: 'No WebGL context'};

        // Check if there are any draw calls by checking the pixel data
        // Read pixels from multiple locations
        const locations = [
            {x: 100, y: 100},
            {x: 200, y: 200},
            {x: 300, y: 300},
            {x: 400, y: 400},
            {x: 500, y: 500},
        ];

        const results = [];
        for (const loc of locations) {
            const pixels = new Uint8Array(4);
            gl.readPixels(loc.x, loc.y, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, pixels);
            results.push({
                x: loc.x,
                y: loc.y,
                r: pixels[0],
                g: pixels[1],
                b: pixels[2],
                a: pixels[3],
            });
        }

        return {
            locations: results,
        };
    }""")

    print(f"Pixel data: {result}")

    browser.close()
