"""
StarMap Browser QA - Full Role-Based Business Flow Testing
Browser QA SKILL: Phase 1-4
"""
import asyncio
import json
import os
import time
from pathlib import Path
from datetime import datetime

from playwright.sync_api import sync_playwright, Page, Browser

BASE_URL = "http://localhost:5176"
BACKEND_URL = "http://localhost:8000"
SCREENSHOT_DIR = Path("starmap/tests/e2e/browser-qa/screenshots")
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

REPORT = {
    "timestamp": datetime.now().isoformat(),
    "base_url": BASE_URL,
    "backend_url": BACKEND_URL,
    "smoke_test": {},
    "interactions": [],
    "visual": [],
    "issues_found": [],
    "console_errors": [],
    "network_errors": [],
}


def take_screenshot(page: Page, name: str, viewport: str = "desktop"):
    path = SCREENSHOT_DIR / f"{name}_{viewport}.png"
    page.screenshot(path=str(path), full_page=True)
    return str(path)


def setup_console_network_logging(page: Page):
    page.on("console", lambda msg: REPORT["console_errors"].append({
        "type": msg.type,
        "text": msg.text,
        "timestamp": datetime.now().isoformat()
    }) if msg.type in ["error", "warning"] else None)

    page.on("response", lambda response: REPORT["network_errors"].append({
        "url": response.url,
        "status": response.status,
        "timestamp": datetime.now().isoformat()
    }) if response.status >= 400 else None)


def smoke_test(page: Page):
    print("\n=== PHASE 1: SMOKE TEST ===")

    routes = [
        ("/", "home", "全景图谱"),
        ("/positions", "position-list", "岗位列表"),
        ("/match", "match", "匹配诊断"),
        ("/evolution", "evolution", "演化看板"),
        ("/quality", "quality", "图谱质量"),
        ("/admin", "admin", "管理后台"),
    ]

    smoke_results = []

    for path, name, title in routes:
        url = f"{BASE_URL}{path}"
        print(f"  Testing: {url} ({title})")
        try:
            response = page.goto(url, wait_until="networkidle", timeout=15000)
            status = response.status if response else 0
            page.wait_for_timeout(2000)
            screenshot_path = take_screenshot(page, f"smoke_{name}")
            body_text = page.inner_text("body")
            has_content = len(body_text.strip()) > 50

            result = {
                "route": path,
                "name": name,
                "title": title,
                "http_status": status,
                "has_content": has_content,
                "body_preview": body_text[:200] if body_text else "",
                "screenshot": screenshot_path,
                "status": "PASS" if status == 200 and has_content else "FAIL"
            }
            smoke_results.append(result)
            print(f"    -> Status: {status}, Content: {has_content}, Result: {result['status']}")
        except Exception as e:
            result = {"route": path, "name": name, "error": str(e), "status": "ERROR"}
            smoke_results.append(result)
            REPORT["issues_found"].append({
                "phase": "smoke_test",
                "route": path,
                "severity": "critical",
                "description": f"Page failed to load: {str(e)}"
            })
            print(f"    -> ERROR: {e}")

    REPORT["smoke_test"] = smoke_results
    return smoke_results


def test_home_page(page: Page):
    print("\n=== PHASE 2: HOME PAGE INTERACTION ===")
    page.goto(BASE_URL, wait_until="networkidle", timeout=15000)
    page.wait_for_timeout(2000)
    take_screenshot(page, "home_initial")

    nav_links = page.query_selector_all("a[href], .nav-link, .router-link, nav a, .menu a")
    print(f"  Found {len(nav_links)} navigation links")

    graph_elements = page.query_selector_all("svg, canvas, .graph, .chart, .visualization, [class*='graph'], [class*='chart']")
    print(f"  Found {len(graph_elements)} graph/chart elements")

    search_inputs = page.query_selector_all("input[type='search'], input[placeholder*='搜索'], input[placeholder*='search'], .search-input")
    print(f"  Found {len(search_inputs)} search inputs")

    if search_inputs:
        try:
            search_inputs[0].fill("Python")
            page.wait_for_timeout(1000)
            take_screenshot(page, "home_search_python")
            print("  Searched for 'Python'")
        except Exception as e:
            REPORT["issues_found"].append({"phase": "home_page", "severity": "medium", "description": f"Search input interaction failed: {e}"})

    stats_elements = page.query_selector_all(".stat, .metric, .count, [class*='stat'], [class*='count'], [class*='metric']")
    print(f"  Found {len(stats_elements)} stat/metric elements")

    REPORT["interactions"].append({"page": "home", "nav_links": len(nav_links), "graph_elements": len(graph_elements), "search_inputs": len(search_inputs), "stats_elements": len(stats_elements)})


def test_position_list(page: Page):
    print("\n=== PHASE 2: POSITION LIST INTERACTION ===")
    page.goto(f"{BASE_URL}/positions", wait_until="networkidle", timeout=15000)
    page.wait_for_timeout(2000)
    take_screenshot(page, "position_list_initial")

    position_items = page.query_selector_all(".position-card, .position-item, .card, .list-item, [class*='position'], tr, .el-card, .ant-card")
    print(f"  Found {len(position_items)} position items")

    search_inputs = page.query_selector_all("input[type='search'], input[type='text'], .search-input, input[placeholder]")
    print(f"  Found {len(search_inputs)} search/filter inputs")

    if search_inputs:
        try:
            search_inputs[0].fill("前端")
            page.wait_for_timeout(1500)
            take_screenshot(page, "position_search_frontend")
            print("  Searched for '前端'")
        except Exception as e:
            REPORT["issues_found"].append({"phase": "position_list", "severity": "medium", "description": f"Position search failed: {e}"})

    REPORT["interactions"].append({"page": "position_list", "position_items": len(position_items), "search_inputs": len(search_inputs)})


def test_position_detail(page: Page):
    print("\n=== PHASE 2: POSITION DETAIL INTERACTION ===")
    page.goto(f"{BASE_URL}/positions", wait_until="networkidle", timeout=15000)
    page.wait_for_timeout(2000)

    position_links = page.query_selector_all("a[href*='/position/'], .position-card a, .card a")
    if position_links:
        try:
            first_link = position_links[0]
            href = first_link.get_attribute("href")
            print(f"  Clicking position link: {href}")
            first_link.click()
            page.wait_for_timeout(3000)
            take_screenshot(page, "position_detail")

            radar_elements = page.query_selector_all("svg, canvas, .radar, .chart, [class*='radar'], [class*='skill']")
            print(f"  Found {len(radar_elements)} radar/skill elements")

            skill_items = page.query_selector_all(".skill-item, .skill-tag, .tag, [class*='skill'], li")
            print(f"  Found {len(skill_items)} skill items")

            body_text = page.inner_text("body")
            print(f"  Page content length: {len(body_text)} chars")

            REPORT["interactions"].append({"page": "position_detail", "radar_elements": len(radar_elements), "skill_items": len(skill_items), "content_length": len(body_text)})
        except Exception as e:
            REPORT["issues_found"].append({"phase": "position_detail", "severity": "medium", "description": f"Position detail navigation failed: {e}"})
    else:
        print("  No position links found to click")
        REPORT["issues_found"].append({"phase": "position_detail", "severity": "high", "description": "No position links found - list may be empty or links not rendered"})


def test_match_diagnosis(page: Page):
    print("\n=== PHASE 2: MATCH DIAGNOSIS INTERACTION ===")
    page.goto(f"{BASE_URL}/match", wait_until="networkidle", timeout=15000)
    page.wait_for_timeout(2000)
    take_screenshot(page, "match_initial")

    upload_elements = page.query_selector_all("input[type='file'], .upload, .el-upload, [class*='upload'], [class*='drop']")
    print(f"  Found {len(upload_elements)} upload elements")

    selects = page.query_selector_all("select, .el-select, [class*='select'], [role='combobox']")
    print(f"  Found {len(selects)} select elements")

    text_inputs = page.query_selector_all("textarea, input[type='text'], .el-textarea, [class*='textarea']")
    print(f"  Found {len(text_inputs)} text inputs")

    buttons = page.query_selector_all("button, .btn, [class*='submit'], [class*='match']")
    print(f"  Found {len(buttons)} buttons")
    for btn in buttons[:5]:
        try:
            btn_text = btn.inner_text()
            print(f"    Button: '{btn_text}'")
        except:
            pass

    take_screenshot(page, "match_filled")
    REPORT["interactions"].append({"page": "match_diagnosis", "upload_elements": len(upload_elements), "selects": len(selects), "text_inputs": len(text_inputs), "buttons": len(buttons)})


def test_evolution_dashboard(page: Page):
    print("\n=== PHASE 2: EVOLUTION DASHBOARD INTERACTION ===")
    page.goto(f"{BASE_URL}/evolution", wait_until="networkidle", timeout=15000)
    page.wait_for_timeout(2000)
    take_screenshot(page, "evolution_initial")

    chart_elements = page.query_selector_all("svg, canvas, .chart, [class*='chart'], [class*='graph'], .visualization")
    print(f"  Found {len(chart_elements)} chart elements")

    timeline_elements = page.query_selector_all("[class*='timeline'], [class*='date'], [class*='period'], .el-date-editor")
    print(f"  Found {len(timeline_elements)} timeline/date elements")

    filter_elements = page.query_selector_all("select, .el-select, [class*='filter'], [class*='select']")
    print(f"  Found {len(filter_elements)} filter elements")

    body_text = page.inner_text("body")
    print(f"  Page content: {body_text[:200]}")

    REPORT["interactions"].append({"page": "evolution_dashboard", "chart_elements": len(chart_elements), "timeline_elements": len(timeline_elements), "filter_elements": len(filter_elements)})


def test_quality_dashboard(page: Page):
    print("\n=== PHASE 2: QUALITY DASHBOARD INTERACTION ===")
    page.goto(f"{BASE_URL}/quality", wait_until="networkidle", timeout=15000)
    page.wait_for_timeout(2000)
    take_screenshot(page, "quality_initial")

    metric_elements = page.query_selector_all(".metric, .kpi, .stat, [class*='metric'], [class*='kpi'], [class*='stat'], .el-statistic")
    print(f"  Found {len(metric_elements)} metric elements")

    chart_elements = page.query_selector_all("svg, canvas, .chart, [class*='chart']")
    print(f"  Found {len(chart_elements)} chart elements")

    body_text = page.inner_text("body")
    print(f"  Page content: {body_text[:300]}")

    REPORT["interactions"].append({"page": "quality_dashboard", "metric_elements": len(metric_elements), "chart_elements": len(chart_elements)})


def test_admin_page(page: Page):
    print("\n=== PHASE 2: ADMIN PAGE INTERACTION ===")
    page.goto(f"{BASE_URL}/admin", wait_until="networkidle", timeout=15000)
    page.wait_for_timeout(2000)
    take_screenshot(page, "admin_initial")

    table_elements = page.query_selector_all("table, .el-table, [class*='table'], [class*='list']")
    print(f"  Found {len(table_elements)} table/list elements")

    buttons = page.query_selector_all("button, .btn, [class*='action']")
    print(f"  Found {len(buttons)} action buttons")
    for btn in buttons[:5]:
        try:
            print(f"    Button: '{btn.inner_text()}'")
        except:
            pass

    body_text = page.inner_text("body")
    print(f"  Page content: {body_text[:300]}")

    REPORT["interactions"].append({"page": "admin", "table_elements": len(table_elements), "buttons": len(buttons)})


def test_visual_regression(page: Page):
    print("\n=== PHASE 3: VISUAL REGRESSION ===")
    viewports = [("mobile", 375, 812), ("tablet", 768, 1024), ("desktop", 1440, 900)]
    routes = ["/", "/positions", "/match", "/admin"]

    for route in routes:
        for viewport_name, width, height in viewports:
            page.set_viewport_size({"width": width, "height": height})
            page.goto(f"{BASE_URL}{route}", wait_until="networkidle", timeout=15000)
            page.wait_for_timeout(1500)
            screenshot_path = take_screenshot(page, f"visual_{route.replace('/', '_').strip('_')}_{viewport_name}")

            overflow_check = page.evaluate("""() => {
                const body = document.body;
                const html = document.documentElement;
                return {
                    body_scroll_width: body.scrollWidth,
                    body_client_width: body.clientWidth,
                    has_horizontal_overflow: body.scrollWidth > body.clientWidth + 5
                }
            }""")

            if overflow_check.get("has_horizontal_overflow"):
                REPORT["visual"].append({"route": route, "viewport": viewport_name, "issue": "horizontal_overflow", "scroll_width": overflow_check["body_scroll_width"], "client_width": overflow_check["body_client_width"], "screenshot": screenshot_path})
                REPORT["issues_found"].append({"phase": "visual_regression", "severity": "medium", "description": f"Horizontal overflow on {route} at {viewport_name} viewport ({width}x{height})"})
                print(f"  WARNING: Horizontal overflow on {route} at {viewport_name}")
            else:
                print(f"  OK: {route} at {viewport_name}")


def run_backend_api_check(page: Page):
    print("\n=== BACKEND API CHECK ===")
    api_endpoints = [
        "/api/v1/graph/stats",
        "/api/v1/positions",
        "/api/v1/skills",
        "/api/v1/match/diagnose",
        "/api/v1/evolution/timeline",
        "/api/v1/quality/metrics",
        "/api/v1/admin/stats",
    ]

    for endpoint in api_endpoints:
        try:
            response = page.evaluate(f"""async () => {{
                try {{
                    const res = await fetch('{BACKEND_URL}{endpoint}');
                    return {{ status: res.status, ok: res.ok, url: '{BACKEND_URL}{endpoint}' }};
                }} catch(e) {{
                    return {{ error: e.message, url: '{BACKEND_URL}{endpoint}' }};
                }}
            }}""")

            status = response.get("status", "error")
            ok = response.get("ok", False)
            print(f"  {endpoint}: status={status}, ok={ok}")

            if not ok:
                REPORT["issues_found"].append({"phase": "backend_api", "severity": "high", "description": f"API endpoint {endpoint} returned status {status}"})
        except Exception as e:
            print(f"  {endpoint}: ERROR - {e}")
            REPORT["issues_found"].append({"phase": "backend_api", "severity": "critical", "description": f"API endpoint {endpoint} failed: {e}"})


def main():
    print("=" * 60)
    print("STARMAP BROWSER QA - FULL INTERACTION TEST")
    print(f"Target: {BASE_URL}")
    print(f"Backend: {BACKEND_URL}")
    print(f"Screenshots: {SCREENSHOT_DIR}")
    print("=" * 60)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        page = context.new_page()
        setup_console_network_logging(page)

        smoke_test(page)
        test_home_page(page)
        test_position_list(page)
        test_position_detail(page)
        test_match_diagnosis(page)
        test_evolution_dashboard(page)
        test_quality_dashboard(page)
        test_admin_page(page)
        run_backend_api_check(page)
        test_visual_regression(page)

        browser.close()

    report_path = SCREENSHOT_DIR / "qa_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(REPORT, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 60)
    print("QA REPORT SUMMARY")
    print("=" * 60)
    print(f"Console Errors: {len(REPORT['console_errors'])}")
    print(f"Network Errors: {len(REPORT['network_errors'])}")
    print(f"Issues Found: {len(REPORT['issues_found'])}")

    if REPORT["issues_found"]:
        print("\nISSUES:")
        for i, issue in enumerate(REPORT["issues_found"], 1):
            print(f"  {i}. [{issue['severity']}] {issue['phase']}: {issue['description']}")

    if REPORT["console_errors"]:
        print("\nCONSOLE ERRORS:")
        for err in REPORT["console_errors"][:10]:
            print(f"  [{err['type']}] {err['text'][:100]}")

    if REPORT["network_errors"]:
        print("\nNETWORK ERRORS:")
        for err in REPORT["network_errors"][:10]:
            print(f"  [{err['status']}] {err['url']}")

    print(f"\nReport saved to: {report_path}")
    print(f"Screenshots saved to: {SCREENSHOT_DIR}")
    return REPORT


if __name__ == "__main__":
    main()
