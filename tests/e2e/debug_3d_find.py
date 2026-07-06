#!/usr/bin/env python3
"""Debug script: Check 3D scene using browser console evaluation."""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
    page = ctx.new_page()

    page.goto("http://localhost:5173", wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(8000)

    # Find the graph instance by searching window objects
    result = page.evaluate("""() => {
        // 3d-force-graph stores the instance in various places
        // Let's search for it
        let found = null;
        for (const key in window) {
            const val = window[key];
            if (val && typeof val === 'object' && val.graphData) {
                found = {key: key, hasGraphData: true};
                break;
            }
        }

        // Also check if there's a __graph or similar on the container
        const container = document.querySelector('.graph3d-container');
        const containerInfo = container ? {
            tagName: container.tagName,
            childCount: container.children.length,
            firstChild: container.children[0]?.tagName,
        } : {error: 'No container'};

        // Check canvas
        const canvas = document.querySelector('.graph3d-container canvas');
        const canvasInfo = canvas ? {
            width: canvas.width,
            height: canvas.height,
            style: {
                width: canvas.style.width,
                height: canvas.style.height,
            }
        } : {error: 'No canvas'};

        return {
            found,
            containerInfo,
            canvasInfo,
        };
    }""")

    print(f"Result: {result}")

    # Now try to find the graph instance through the Vue component
    graph_check = page.evaluate("""() => {
        const app = document.querySelector('#app').__vue_app__;
        if (!app) return {error: 'No Vue app'};

        // Walk the component tree to find Graph3D
        const root = app._component;
        function findComponent(vnode, name) {
            if (!vnode) return null;
            if (vnode.type?.name === name || vnode.type?.displayName === name) {
                return vnode;
            }
            if (vnode.children) {
                for (const child of Array.isArray(vnode.children) ? vnode.children : [vnode.children]) {
                    const found = findComponent(child, name);
                    if (found) return found;
                }
            }
            if (vnode.component) {
                const found = findComponent(vnode.component.subTree, name);
                if (found) return found;
            }
            return null;
        }

        // Try to access the exposed graph instance
        const graph3dContainer = document.querySelector('.graph3d-container');
        if (!graph3dContainer) return {error: 'No graph3d-container'};

        // The Vue component instance is attached to the element
        const vueInstance = graph3dContainer._vue || graph3dContainer.__vueParentComponent;

        return {
            hasVueInstance: !!vueInstance,
            vueInstanceType: vueInstance?.type?.name,
            exposedKeys: vueInstance?.component?.exposed ? Object.keys(vueInstance.component.exposed) : null,
        };
    }""")

    print(f"Graph check: {graph_check}")

    browser.close()
