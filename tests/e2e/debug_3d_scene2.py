#!/usr/bin/env python3
"""Debug: Check 3D scene objects."""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
    page = ctx.new_page()

    page.goto("http://localhost:5177", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(10000)

    # Check the 3D scene
    result = page.evaluate("""() => {
        // Find the graph instance
        let graph = null;
        for (const key in window) {
            const val = window[key];
            if (val && typeof val === 'object' && val.graphData) {
                graph = val;
                break;
            }
        }

        if (!graph) return {error: 'No graph instance found'};

        const data = graph.graphData();
        const nodes = data.nodes;

        // Check node positions
        const positions = nodes.map(n => ({
            id: n.id,
            x: n.x,
            y: n.y,
            z: n.z,
        }));

        // Check camera position
        const cameraPos = graph.cameraPosition();

        return {
            nodeCount: nodes.length,
            positions: positions,
            cameraPosition: cameraPos,
        };
    }""")

    print(f"3D scene: {result}")

    browser.close()
