#!/usr/bin/env python3
"""Debug: Check createGlowTexture."""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
    page = ctx.new_page()

    page.goto("http://localhost:5177", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(10000)

    # Check createGlowTexture
    result = page.evaluate("""() => {
        // Create a test texture
        const THREE = window.THREE;
        if (!THREE) return {error: 'No THREE'};

        const size = 128;
        const canvas = document.createElement('canvas');
        canvas.width = size;
        canvas.height = size;
        const ctx = canvas.getContext('2d');

        const gradient = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
        gradient.addColorStop(0, 'rgba(255, 0, 0, 0.6)');
        gradient.addColorStop(0.3, 'rgba(255, 0, 0, 0.25)');
        gradient.addColorStop(0.7, 'rgba(255, 0, 0, 0.08)');
        gradient.addColorStop(1, 'rgba(255, 0, 0, 0)');
        ctx.fillStyle = gradient;
        ctx.fillRect(0, 0, size, size);

        const texture = new THREE.CanvasTexture(canvas);
        texture.needsUpdate = true;

        return {
            textureType: texture.type,
            textureWidth: texture.image.width,
            textureHeight: texture.image.height,
            textureNeedsUpdate: texture.needsUpdate,
        };
    }""")

    print(f"Texture check: {result}")

    browser.close()
