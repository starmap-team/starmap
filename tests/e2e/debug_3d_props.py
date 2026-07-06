#!/usr/bin/env python3
"""Debug: Check graph3DNodes actual values."""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
    page = ctx.new_page()

    page.goto("http://localhost:5173", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(10000)

    # Check graph3DNodes
    result = page.evaluate("""() => {
        const app = document.querySelector('#app').__vue_app__;
        if (!app) return {error: 'No Vue app'};

        // Access the Home component's setup state
        const home = app._component.subTree;
        if (!home) return {error: 'No Home component'};

        // Find Graph3D component instance
        const graph3d = document.querySelector('.graph3d-wrapper');
        if (!graph3d) return {error: 'No graph3d-wrapper'};

        // Try to access the component's props
        const keys = Object.keys(graph3d);
        const vueKey = keys.find(k => k.startsWith('__vue'));
        if (!vueKey) return {error: 'No Vue instance', keys: keys};

        const component = graph3d[vueKey];
        const props = component.props || {};

        return {
            nodesCount: props.nodes?.length || 0,
            firstNode: props.nodes?.length > 0 ? {
                id: props.nodes[0].id,
                labels: props.nodes[0].labels,
                hasLabels: !!props.nodes[0].labels,
            } : null,
            overviewMode: props.overviewMode,
        };
    }""")

    print(f"Graph3D props: {result}")

    browser.close()
