#!/usr/bin/env python3
"""Debug: Check 3D scene objects via browser console."""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
    page = ctx.new_page()

    page.goto("http://localhost:5177", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(15000)

    # Check the 3D scene
    result = page.evaluate("""() => {
        // Find the scene container
        const container = document.querySelector('.graph3d-container');
        if (!container) return {error: 'No graph3d-container'};

        // The scene is rendered in a canvas, but we can check the DOM
        // for any indicators of the scene state
        const sceneContainer = container.querySelector('.scene-container');
        if (!sceneContainer) return {error: 'No scene-container'};

        // Check if there are any child elements that might indicate nodes
        const children = sceneContainer.children;
        const childInfo = Array.from(children).map(child => ({
            tag: child.tagName,
            class: child.className,
            childCount: child.children.length,
        }));

        return {
            sceneContainerFound: true,
            children: childInfo,
        };
    }""")

    print(f"Scene objects: {result}")

    browser.close()
