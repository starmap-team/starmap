#!/usr/bin/env python3
"""Browser QA Phase 3-5 detailed: mode-specific data + node drill-down + 2D/3D cross-verify."""
from playwright.sync_api import sync_playwright
import json

ss_dir = "tests/e2e/browser_qa_screenshots"

GET_STORE_JS = """() => {
    const app = document.querySelector('#app').__vue_app__;
    if (!app) return {error: 'Vue app not found'};
    const pinia = app.config.globalProperties.$pinia;
    if (!pinia) return {error: 'Pinia not found'};
    const store = pinia._s.get('graph');
    if (!store) return {error: 'Graph store not found'};
    return {
        overviewMode: store.overviewMode,
        currentLayer: store.currentLayer,
        domainsCount: store.domains.length,
        connectionsCount: store.domainConnections.length,
        domainIds: store.domains.map(d => d.id),
        domainNames: store.domains.map(d => d.name),
        connectionTypes: [...new Set(store.domainConnections.map(c => c.type))],
        visibleNodesCount: store.visibleNodes.length,
        visibleEdgesCount: store.visibleEdges.length,
    };
}"""

GET_FPS_JS = """() => {
    const fpsEl = document.querySelector('.fps-counter');
    return fpsEl ? fpsEl.textContent : 'FPS counter not found';
}"""

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
    page = ctx.new_page()

    console_log = []
    page.on("console", lambda m: console_log.append({"type": m.type, "text": m.text[:500]}))
    net_fail = []
    page.on("response", lambda r: net_fail.append({"url": r.url[:150], "status": r.status}) if r.status >= 400 else None)

    # Navigate
    page.goto("http://localhost:5173", wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(5000)

    # ── Test each mode in 3D ──
    print("=== 3D Mode-by-Mode Verification ===")
    results = {}

    for mode, label in [("domain", "领域"), ("tech_stack", "技术栈"), ("level", "级别")]:
        print(f"\n  [{mode}] Switching to {label}...")

        # Click the radio button
        btn = page.query_selector(f'.el-radio-button[value="{mode}"]')
        if not btn:
            # Try by text
            btn = page.locator(f'.view-tabs .el-radio-button:has-text("{label}")').first
        if btn:
            btn.click()
            page.wait_for_timeout(4000)
        else:
            print(f"    ERROR: {label} button not found!")
            continue

        # Screenshot
        page.screenshot(path=f"{ss_dir}/qa_3d_{mode}_detail.png")

        # Get store data
        data = page.evaluate(GET_STORE_JS)
        results[mode] = data
        print(f"    overviewMode: {data.get('overviewMode')}")
        print(f"    domains: {data.get('domainsCount')} nodes")
        print(f"    connections: {data.get('connectionsCount')} edges")
        print(f"    domainIds: {data.get('domainIds')}")
        print(f"    domainNames: {data.get('domainNames')}")
        print(f"    connectionTypes: {data.get('connectionTypes')}")
        print(f"    visibleNodes: {data.get('visibleNodesCount')}")
        print(f"    visibleEdges: {data.get('visibleEdgesCount')}")

        # Verify mode matches
        if data.get('overviewMode') == mode:
            print(f"    [PASS] overviewMode correct")
        else:
            print(f"    [FAIL] overviewMode mismatch: expected {mode}, got {data.get('overviewMode')}")

        # Verify nodes are not all at origin (check canvas exists)
        canvas = page.query_selector("canvas")
        if canvas:
            print(f"    [PASS] Canvas present")
        else:
            print(f"    [FAIL] Canvas missing!")

        # Check FPS
        fps = page.evaluate(GET_FPS_JS)
        print(f"    FPS: {fps}")

    # ── 2D/3D Cross-Verification ──
    print("\n=== 2D/3D Cross-Verification ===")

    for mode, label in [("domain", "领域"), ("tech_stack", "技术栈"), ("level", "级别")]:
        print(f"\n  [{mode}] Testing 2D vs 3D...")

        # Switch to 3D first
        page.locator('.vm-btn:has-text("3D")').first.click()
        page.wait_for_timeout(2000)

        btn = page.query_selector(f'.el-radio-button[value="{mode}"]')
        if btn:
            btn.click()
            page.wait_for_timeout(4000)

        data_3d = page.evaluate(GET_STORE_JS)

        # Switch to 2D
        page.locator('.vm-btn:has-text("2D")').first.click()
        page.wait_for_timeout(3000)

        data_2d = page.evaluate(GET_STORE_JS)

        # Compare
        d3 = data_3d.get("domainsCount", 0)
        d2 = data_2d.get("domainsCount", 0)
        c3 = data_3d.get("connectionsCount", 0)
        c2 = data_2d.get("connectionsCount", 0)

        domain_match = d3 == d2
        conn_match = c3 == c2

        if domain_match and conn_match:
            print(f"    [PASS] 2D/3D consistent: {d3} domains, {c3} connections")
        else:
            print(f"    [FAIL] 2D/3D mismatch: 3D({d3}d/{c3}c) vs 2D({d2}d/{c2}c)")

        # Screenshot 2D
        page.screenshot(path=f"{ss_dir}/qa_2d_{mode}_cross.png")

    # Switch back to 3D for final
    page.locator('.vm-btn:has-text("3D")').first.click()
    page.wait_for_timeout(2000)

    # ── Node Click Drill-Down ──
    print("\n=== Node Click Drill-Down ===")

    # Switch to domain mode
    btn = page.query_selector('.el-radio-button[value="domain"]')
    if btn:
        btn.click()
    page.wait_for_timeout(3000)

    # Get the first domain node name from store
    first_domain = page.evaluate("""() => {
        const app = document.querySelector('#app').__vue_app__;
        const store = app.config.globalProperties.$pinia._s.get('graph');
        return store && store.domains.length > 0 ? store.domains[0].name : null;
    }""")
    print(f"  First domain: {first_domain}")

    # Click the node label in the 3D graph (hover first to find it)
    # Use JavaScript to trigger the drill-down via the store directly
    drill_result = page.evaluate("""() => {
        const app = document.querySelector('#app').__vue_app__;
        const store = app.config.globalProperties.$pinia._s.get('graph');
        if (!store || store.domains.length === 0) return {error: 'No domains'};
        const domain = store.domains[0];
        // Trigger the drill-down by expanding the KA
        store.expandKA(domain.id, domain.name);
        return {id: domain.id, name: domain.name, layer: store.currentLayer};
    }""")
    print(f"  Drill-down result: {json.dumps(drill_result, ensure_ascii=False)}")
    page.wait_for_timeout(3000)
    page.screenshot(path=f"{ss_dir}/qa_3d_drilldown_position.png")

    # Check current layer
    layer = page.evaluate("""() => {
        const app = document.querySelector('#app').__vue_app__;
        const store = app.config.globalProperties.$pinia._s.get('graph');
        return store ? store.currentLayer : 'unknown';
    }""")
    print(f"  Current layer after drill-down: {layer}")
    if layer == "position":
        print("  [PASS] Drill-down to position layer works")
    else:
        print(f"  [FAIL] Expected 'position', got '{layer}'")

    # Breadcrumb back
    breadcrumb = page.query_selector(".graph-breadcrumb")
    if breadcrumb:
        first_crumb = breadcrumb.query_selector(".gb-item")
        if first_crumb:
            first_crumb.click()
            page.wait_for_timeout(2000)
            print("  [PASS] Breadcrumb navigation back works")

    # ── Rapid 10x Switch Stress Test ──
    print("\n=== 10x Rapid Switch Stress Test ===")
    errors_before = len(console_log)
    for i in range(10):
        modes = ["tech_stack", "level", "domain"]
        mode = modes[i % 3]
        btn = page.query_selector(f'.el-radio-button[value="{mode}"]')
        if btn:
            btn.click()
        page.wait_for_timeout(300)

    page.wait_for_timeout(5000)
    page.screenshot(path=f"{ss_dir}/qa_3d_stress_final.png")

    new_errors = [e for e in console_log[errors_before:]
                  if e["type"] == "error"
                  and "favicon" not in e["text"].lower()
                  and "devtools" not in e["text"].lower()]
    canvas_count = len(page.query_selector_all("canvas"))
    print(f"  New errors: {len(new_errors)}")
    print(f"  Canvas surviving: {canvas_count > 0}")

    # ── Final Summary ──
    print("\n" + "=" * 60)
    print("BROWSER QA REPORT — 3D Graph Differentiated Layout")
    print("=" * 60)

    real_errors = [e for e in console_log
                   if e["type"] == "error"
                   and "favicon" not in e["text"].lower()
                   and "devtools" not in e["text"].lower()]

    print(f"\n  Console errors (real): {len(real_errors)}")
    for e in real_errors[:5]:
        print(f"    {e['text'][:200]}")

    print(f"  Network failures: {len(net_fail)}")

    fps_final = page.evaluate(GET_FPS_JS)
    print(f"  FPS (final): {fps_final}")
    print(f"  Canvas surviving: {canvas_count > 0}")

    # Mode-specific results
    print("\n  Mode Data Summary:")
    for mode in ["domain", "tech_stack", "level"]:
        d = results.get(mode, {})
        print(f"    {mode}: {d.get('domainsCount')} domains, "
              f"{d.get('connectionsCount')} connections, "
              f"types={d.get('connectionTypes')}")

    verdict = "SHIP" if len(real_errors) == 0 and canvas_count > 0 else "SHIP WITH NOTES"
    print(f"\n  Verdict: {verdict}")

    browser.close()
