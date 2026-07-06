#!/usr/bin/env python3
"""Browser QA Final: Comprehensive 3D graph test with proper waits."""
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
        loading: store.loading,
        domainsCount: store.domains.length,
        connectionsCount: store.domainConnections.length,
        domainIds: store.domains.map(d => d.id),
        domainNames: store.domains.map(d => d.name),
        connectionTypes: [...new Set(store.domainConnections.map(c => c.type))],
    };
}"""

GET_FPS_JS = """() => {
    const fpsEl = document.querySelector('.fps-counter');
    return fpsEl ? fpsEl.textContent : 'N/A';
}"""

passes = []
fails = []

def check(name, condition, detail=""):
    if condition:
        passes.append(name)
        print(f"  [PASS] {name} {detail}")
    else:
        fails.append(name)
        print(f"  [FAIL] {name} {detail}")

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
    page.wait_for_timeout(6000)  # Extra time for 3D graph init

    # ── Phase 1: Smoke ──
    print("=== Phase 1: Smoke ===")
    data = page.evaluate(GET_STORE_JS)
    check("Page loads", data.get("domainsCount", 0) > 0, f"({data.get('domainsCount')} domains)")
    check("3D canvas present", len(page.query_selector_all("canvas")) > 0)
    check("Default mode is domain", data.get("overviewMode") == "domain")
    fps = page.evaluate(GET_FPS_JS)
    check("FPS >= 30", int(fps.replace(" FPS", "").strip() or "0") >= 30, f"({fps})")

    # ── Phase 2: Mode Switching ──
    print("\n=== Phase 2: Mode Switching ===")

    expected_data = {
        "domain": {"min_domains": 10, "conn_type": "SHARES_POSITION"},
        "tech_stack": {"min_domains": 4, "conn_type": "SHARES_SKILLS"},
        "level": {"min_domains": 3, "conn_type": "EVOLVES_TO"},
    }

    # Map mode to Chinese label text (as it appears in the radio button)
    mode_labels = {"domain": "领域", "tech_stack": "技术栈", "level": "级别"}

    for mode, label in [("domain", "领域"), ("tech_stack", "技术栈"), ("level", "级别")]:
        print(f"\n  [{mode}] {label}...")

        # Click radio button by text (Element Plus renders value on inner <input>, not <label>)
        btn = page.locator('.view-tabs').get_by_text(label, exact=True)
        if btn.count() > 0:
            btn.click()
        else:
            check(f"{mode} button found", False)
            continue

        # Wait for loading to finish + layout to settle
        page.wait_for_timeout(5000)

        # Screenshot
        page.screenshot(path=f"{ss_dir}/qa_final_3d_{mode}.png")

        # Get data
        data = page.evaluate(GET_STORE_JS)
        exp = expected_data[mode]

        check(f"{mode}: overviewMode correct", data.get("overviewMode") == mode)
        check(f"{mode}: domains >= {exp['min_domains']}",
              data.get("domainsCount", 0) >= exp["min_domains"],
              f"(got {data.get('domainsCount')})")
        check(f"{mode}: connection type is {exp['conn_type']}",
              exp["conn_type"] in (data.get("connectionTypes") or []),
              f"(got {data.get('connectionTypes')})")
        check(f"{mode}: canvas present", len(page.query_selector_all("canvas")) > 0)

    # ── Phase 3: 2D/3D Cross-Verify ──
    print("\n=== Phase 3: 2D/3D Cross-Verify ===")

    for mode, label in [("domain", "领域"), ("tech_stack", "技术栈"), ("level", "级别")]:
        print(f"\n  [{mode}] Cross-verify...")

        # Ensure we're in 3D
        page.locator('.vm-btn:has-text("3D")').first.click()
        page.wait_for_timeout(2000)

        # Switch mode
        mode_btn = page.locator('.view-tabs').get_by_text(label, exact=True)
        if mode_btn.count() > 0:
            mode_btn.click()
        page.wait_for_timeout(5000)

        data_3d = page.evaluate(GET_STORE_JS)

        # Switch to 2D
        page.locator('.vm-btn:has-text("2D")').first.click()
        page.wait_for_timeout(4000)

        data_2d = page.evaluate(GET_STORE_JS)

        d3 = data_3d.get("domainsCount", 0)
        d2 = data_2d.get("domainsCount", 0)
        c3 = data_3d.get("connectionsCount", 0)
        c2 = data_2d.get("connectionsCount", 0)

        check(f"{mode}: 2D/3D domain count match", d3 == d2, f"(3D={d3}, 2D={d2})")
        check(f"{mode}: 2D/3D connection count match", c3 == c2, f"(3D={c3}, 2D={c2})")

    # Back to 3D
    page.locator('.vm-btn:has-text("3D")').first.click()
    page.wait_for_timeout(2000)

    # ── Phase 4: Rapid Switching ──
    print("\n=== Phase 4: Rapid Switching (10x) ===")
    errors_before = len(console_log)
    for i in range(10):
        modes = ["tech_stack", "level", "domain"]
        mode = modes[i % 3]
        mode_labels_map = {"domain": "领域", "tech_stack": "技术栈", "level": "级别"}
        btn = page.locator('.view-tabs').get_by_text(mode_labels_map[mode], exact=True)
        if btn.count() > 0:
            btn.click()
        page.wait_for_timeout(300)

    page.wait_for_timeout(6000)  # Let last layout fully settle
    page.screenshot(path=f"{ss_dir}/qa_final_stress.png")

    new_errors = [e for e in console_log[errors_before:]
                  if e["type"] == "error"
                  and "favicon" not in e["text"].lower()
                  and "devtools" not in e["text"].lower()]
    check("10x rapid switch: no new errors", len(new_errors) == 0, f"({len(new_errors)} errors)")
    check("10x rapid switch: canvas survives", len(page.query_selector_all("canvas")) > 0)

    # ── Phase 5: Node Drill-Down ──
    print("\n=== Phase 5: Node Drill-Down ===")

    # Switch to domain mode
    btn = page.locator('.view-tabs').get_by_text("领域", exact=True)
    if btn.count() > 0:
        btn.click()
    page.wait_for_timeout(4000)

    # Use goToPositionLayer to drill down
    drill_result = page.evaluate("""() => {
        const app = document.querySelector('#app').__vue_app__;
        const store = app.config.globalProperties.$pinia._s.get('graph');
        if (!store || store.domains.length === 0) return {error: 'No domains'};
        const domain = store.domains[0];
        return {id: domain.id, name: domain.name, layer: store.currentLayer};
    }""")
    first_id = drill_result.get("id")
    first_name = drill_result.get("name")
    print(f"  First domain: {first_name} (id: {first_id})")

    # Trigger drill-down via goToPositionLayer
    page.evaluate(f"""async () => {{
        const app = document.querySelector('#app').__vue_app__;
        const store = app.config.globalProperties.$pinia._s.get('graph');
        await store.goToPositionLayer('{first_id}', '{first_name}');
    }}""")
    page.wait_for_timeout(3000)
    page.screenshot(path=f"{ss_dir}/qa_final_drilldown.png")

    layer = page.evaluate("""() => {
        const app = document.querySelector('#app').__vue_app__;
        const store = app.config.globalProperties.$pinia._s.get('graph');
        return store ? store.currentLayer : 'unknown';
    }""")
    check("Drill-down to position layer", layer == "position", f"(got {layer})")

    # Breadcrumb back
    breadcrumb = page.query_selector(".graph-breadcrumb")
    if breadcrumb:
        first_crumb = breadcrumb.query_selector(".gb-item")
        if first_crumb:
            first_crumb.click()
            page.wait_for_timeout(3000)
            layer_back = page.evaluate("""() => {
                const app = document.querySelector('#app').__vue_app__;
                const store = app.config.globalProperties.$pinia._s.get('graph');
                return store ? store.currentLayer : 'unknown';
            }""")
            check("Breadcrumb back to domain", layer_back == "domain", f"(got {layer_back})")

    # ── Final Report ──
    print("\n" + "=" * 60)
    print("BROWSER QA REPORT — 3D Graph Differentiated Layout")
    print("=" * 60)
    print(f"\n  Passed: {len(passes)}")
    for p_item in passes:
        print(f"    ✓ {p_item}")
    print(f"\n  Failed: {len(fails)}")
    for f_item in fails:
        print(f"    ✗ {f_item}")

    real_errors = [e for e in console_log
                   if e["type"] == "error"
                   and "favicon" not in e["text"].lower()
                   and "devtools" not in e["text"].lower()]
    print(f"\n  Console errors (real): {len(real_errors)}")
    print(f"  Network failures: {len(net_fail)}")
    fps_final = page.evaluate(GET_FPS_JS)
    print(f"  FPS (final): {fps_final}")

    verdict = "SHIP" if len(fails) == 0 else "SHIP WITH FIXES"
    print(f"\n  Verdict: {verdict} ({len(fails)} issues, {len(fails)} blockers)")

    browser.close()
