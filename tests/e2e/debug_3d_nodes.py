#!/usr/bin/env python3
"""Debug script: Check why 3D nodes are not visible."""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
    page = ctx.new_page()

    # Capture console messages
    console_messages = []
    def on_console(msg):
        console_messages.append({"type": msg.type, "text": msg.text})
    page.on("console", on_console)

    page.goto("http://localhost:5173", wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(8000)

    # Check 3D graph data
    result = page.evaluate("""() => {
        const app = document.querySelector('#app').__vue_app__;
        if (!app) return {error: 'Vue app not found'};
        const pinia = app.config.globalProperties.$pinia;
        const store = pinia._s.get('graph');
        if (!store) return {error: 'Graph store not found'};

        // Get the 3D graph instance
        const graph3d = document.querySelector('.graph3d-container');
        let graphInstance = null;
        if (graph3d) {
            // Try to find the graph instance through Vue internals
            const vueEl = graph3d.__vueParentComponent;
            graphInstance = vueEl?.refs?.graphInstance;
        }

        return {
            overviewMode: store.overviewMode,
            domainsCount: store.domains.length,
            domainIds: store.domains.map(d => d.id),
            domainLabels: store.domains.map(d => d.labels),
            connectionsCount: store.domainConnections.length,
            connectionTypes: [...new Set(store.domainConnections.map(c => c.type))],
            firstNode: store.domains.length > 0 ? {
                id: store.domains[0].id,
                name: store.domains[0].name,
                labels: store.domains[0].labels,
                color: store.domains[0].color,
            } : null,
        };
    }""")

    print("Store data:")
    for k, v in result.items():
        print(f"  {k}: {v}")

    # Check canvas state
    canvas_info = page.evaluate("""() => {
        const canvas = document.querySelector('.graph3d-container canvas');
        if (!canvas) return {error: 'No canvas found'};
        return {
            width: canvas.width,
            height: canvas.height,
            style: {
                width: canvas.style.width,
                height: canvas.style.height,
                display: canvas.style.display,
            }
        };
    }""")
    print(f"\nCanvas info: {canvas_info}")

    # Check for errors
    print(f"\nConsole messages ({len(console_messages)}):")
    for msg in console_messages:
        print(f"  [{msg['type']}] {msg['text'][:200]}")

    browser.close()
