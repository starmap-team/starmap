#!/usr/bin/env python3
"""Debug: Check nodeThreeObject return type."""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
    page = ctx.new_page()

    page.goto("http://localhost:5177", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(10000)

    # Check nodeThreeObject return type
    result = page.evaluate("""() => {
        // Create a test mesh
        const geometry = new window.THREE.SphereGeometry(10, 16, 16);
        const material = new window.THREE.MeshPhongMaterial({color: 0xff0000});
        const mesh = new window.THREE.Mesh(geometry, material);
        
        return {
            meshType: mesh.type,
            meshIsObject3D: mesh instanceof window.THREE.Object3D,
            meshIsMesh: mesh instanceof window.THREE.Mesh,
            meshHasPosition: !!mesh.position,
            meshPosition: {x: mesh.position.x, y: mesh.position.y, z: mesh.position.z},
        };
    }""")

    print(f"Mesh check: {result}")

    browser.close()
