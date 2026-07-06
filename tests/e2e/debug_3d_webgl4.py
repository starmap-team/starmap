#!/usr/bin/env python3
"""Debug: Check 3D scene by accessing the renderer."""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
    page = ctx.new_page()

    page.goto("http://localhost:5177", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(15000)

    # Check the 3D scene by accessing the renderer
    result = page.evaluate("""() => {
        // Find the canvas
        const canvas = document.querySelector('.graph3d-container canvas');
        if (!canvas) return {error: 'No canvas'};

        // Get the WebGL context
        const gl = canvas.getContext('webgl') || canvas.getContext('webgl2');
        if (!gl) return {error: 'No WebGL context'};

        // Check the viewport
        const viewport = gl.getParameter(gl.VIEWPORT);
        
        // Check the clear color
        const clearColor = gl.getParameter(gl.COLOR_CLEAR_VALUE);

        // Check if there are any draw calls
        const ext = gl.getExtension('WEBGL_debug_renderer_info');
        const renderer = ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : 'unknown';

        return {
            viewport: {x: viewport[0], y: viewport[1], width: viewport[2], height: viewport[3]},
            clearColor: {r: clearColor[0], g: clearColor[1], b: clearColor[2], a: clearColor[3]},
            renderer: renderer,
        };
    }""")

    print(f"WebGL state: {result}")

    browser.close()
