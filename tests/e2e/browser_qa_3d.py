#!/usr/bin/env python3
"""Browser QA Phase 3-5: Data consistency + performance + regression test."""
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
    };
}"""

GET_FPS_JS = """() => {
    const fpsEl = document.querySelector('.fps-counter');
    return fpsEl ? fpsEl.textContent : 'FPS counter not found';
}"""

GET_LAYER_JS = """() => {
    const app = document.querySelector('#app').__vue_app__;
    const store = app.config.globalProperties.$pinia._s.get('graph');
    return store ? store.currentLayer : 'unknown';
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

    # ── Phase 3: 2D/3D Data Consistency ──
    print("=== Phase 3: 2D/3D Data Consistency ===")

    graph_data_3d = page.evaluate(GET_STORE_JS)
    print(f"  3D mode data: domains={graph_data_3d.get('domainsCount')}, "
          f"connections={graph_data_3d.get('connectionsCount')}, "
          f"mode={graph_data_3d.get('overviewMode')}, "
          f"types={graph_data_3d.get('connectionTypes')}")

    # Switch to 2D
    print("  Switching to 2D...")
    page.locator('.vm-btn:has-text("2D")').first.click()
    page.wait_for_timeout(3000)
    page.screenshot(path=f"{ss_dir}/qa_2d_domain.png")

    graph_data_2d = page.evaluate(GET_STORE_JS)
    print(f"  2D mode data: domains={graph_data_2d.get('domainsCount')}, "
          f"connections={graph_data_2d.get('connectionsCount')}, "
          f"mode={graph_data_2d.get('overviewMode')}")

    # Verify consistency
    d3d = graph_data_3d.get("domainsCount", 0)
    d2d = graph_data_2d.get("domainsCount", 0)
    if d3d == d2d:
        print(f"  [PASS] Domain count consistent: {d3d}")
    else:
        print(f"  [FAIL] Domain count mismatch: 3D={d3d}, 2D={d2d}")

    c3d = graph_data_3d.get("connectionsCount", 0)
    c2d = graph_data_2d.get("connectionsCount", 0)
    if c3d == c2d:
        print(f"  [PASS] Connection count consistent: {c3d}")
    else:
        print(f"  [FAIL] Connection count mismatch: 3D={c3d}, 2D={c2d}")

    # Switch back to 3D
    print("  Switching back to 3D...")
    page.locator('.vm-btn:has-text("3D")').first.click()
    page.wait_for_timeout(3000)

    # ── Phase 4: Performance ──
    print()
    print("=== Phase 4: Performance ===")

    fps_text = page.evaluate(GET_FPS_JS)
    print(f"  FPS counter: \"{fps_text}\"")

    # Rapid 10x switching
    print("  10x rapid switching stress test...")
    errors_before = len(console_log)
    for i in range(10):
        modes = ["tech_stack", "level", "domain"]
        mode = modes[i % 3]
        btn = page.query_selector(f'.el-radio-button[value="{mode}"]')
        if btn:
            btn.click()
        page.wait_for_timeout(300)

    page.wait_for_timeout(5000)
    page.screenshot(path=f"{ss_dir}/qa_3d_stress_10x.png")

    new_errors = [e for e in console_log[errors_before:] if e["type"] == "error" and "favicon" not in e["text"].lower()]
    print(f"  New errors after 10x switch: {len(new_errors)}")
    for e in new_errors[:3]:
        print(f"    {e['text'][:200]}")

    canvas_count = len(page.query_selector_all("canvas"))
    print(f"  Canvas surviving: {canvas_count > 0} (count: {canvas_count})")

    # ── Phase 5: Regression ──
    print()
    print("=== Phase 5: Regression ===")

    # Switch to domain mode
    domain_btn = page.query_selector('.el-radio-button[value="domain"]')
    if domain_btn:
        domain_btn.click()
    page.wait_for_timeout(3000)

    # Node click drill-down
    print("  Attempting node click drill-down...")
    canvas = page.query_selector("canvas")
    if canvas:
        box = canvas.bounding_box()
        if box:
            page.click("canvas", position={"x": box["width"] // 2, "y": box["height"] // 2})
            page.wait_for_timeout(2000)
            page.screenshot(path=f"{ss_dir}/qa_3d_node_click.png")

            layer = page.evaluate(GET_LAYER_JS)
            print(f"  Current layer after click: {layer}")

    # Breadcrumb return
    breadcrumb = page.query_selector(".graph-breadcrumb")
    if breadcrumb:
        first_crumb = breadcrumb.query_selector(".gb-item")
        if first_crumb:
            first_crumb.click()
            page.wait_for_timeout(2000)
            print("  Breadcrumb navigation: OK")

    # Test tech_stack mode
    print()
    print("  Testing tech_stack mode...")
    ts_btn = page.query_selector('.el-radio-button[value="tech_stack"]')
    if ts_btn:
        ts_btn.click()
        page.wait_for_timeout(4000)
        page.screenshot(path=f"{ss_dir}/qa_3d_tech_stack_verify.png")

        ts_data = page.evaluate(GET_STORE_JS)
        print(f"  tech_stack: domains={ts_data.get('domainsCount')}, "
              f"ids={ts_data.get('domainIds')}, "
              f"types={ts_data.get('connectionTypes')}")

    # Test level mode
    print()
    print("  Testing level mode...")
    lv_btn = page.query_selector('.el-radio-button[value="level"]')
    if lv_btn:
        lv_btn.click()
        page.wait_for_timeout(4000)
        page.screenshot(path=f"{ss_dir}/qa_3d_level_verify.png")

        lv_data = page.evaluate(GET_STORE_JS)
        print(f"  level: domains={lv_data.get('domainsCount')}, "
              f"ids={lv_data.get('domainIds')}, "
              f"names={lv_data.get('domainNames')}, "
              f"types={lv_data.get('connectionTypes')}")

    # ── Final Summary ──
    print()
    print("=== Final Summary ===")
    real_errors = [e for e in console_log if e["type"] == "error"
                   and "favicon" not in e["text"].lower()
                   and "devtools" not in e["text"].lower()]
    print(f"  Total console errors (real): {len(real_errors)}")
    for e in real_errors[:5]:
        print(f"    {e['text'][:200]}")
    print(f"  Total network failures: {len(net_fail)}")
    for n in net_fail[:5]:
        print(f"    {n['status']} {n['url']}")
    print(f"  FPS: {fps_text}")
    print(f"  Canvas surviving: {canvas_count > 0}")

    browser.close()
