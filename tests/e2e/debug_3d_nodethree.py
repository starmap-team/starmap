#!/usr/bin/env python3
"""Debug: Check if nodeThreeObject is being called and what it returns."""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
    page = ctx.new_page()

    # Inject a script to monitor nodeThreeObject
    page.add_init_script("""
        window.__nodeThreeObjectCalls = [];
        window.__originalNodeThreeObject = null;
    """)

    page.goto("http://localhost:5173", wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(10000)

    # Check if nodeThreeObject was called
    result = page.evaluate("""() => {
        return {
            calls: window.__nodeThreeObjectCalls.length,
            firstFew: window.__nodeThreeObjectCalls.slice(0, 5),
        };
    }""")

    print(f"nodeThreeObject calls: {result}")

    # Try to access the graph instance through the exposed methods
    graph_check = page.evaluate("""() => {
        const app = document.querySelector('#app').__vue_app__;
        if (!app) return {error: 'No Vue app'};

        // Find Graph3D component
        const graph3d = document.querySelector('.graph3d-wrapper');
        if (!graph3d) return {error: 'No graph3d-wrapper'};

        // Try to find Vue component instance
        const keys = Object.keys(graph3d);
        const vueKey = keys.find(k => k.startsWith('__vue'));
        if (!vueKey) return {error: 'No Vue instance', keys: keys};

        const component = graph3d[vueKey];
        return {
            hasGraphInstance: !!component.refs?.graphInstance,
            graphInstanceType: component.refs?.graphInstance ? typeof component.refs.graphInstance : 'none',
        };
    }""")

    print(f"Graph check: {graph_check}")

    browser.close()
