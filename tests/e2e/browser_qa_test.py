"""StarMap Browser QA - Automated visual and interaction testing."""
import json, time, os
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE_URL = "http://127.0.0.1:5173"
SCREENSHOT_DIR = Path(r"C:\Users\LiShuai\Desktop\Agents\starmap\tests\e2e\browser_qa_screenshots")
SCREENSHOT_DIR.mkdir(exist_ok=True)

issues = []
screenshots = []

def log_issue(severity, page, description, details=""):
    issues.append({"severity": severity, "page": page, "description": description, "details": details})
    tag = {"critical": "CRIT", "major": "MAJOR", "minor": "MINOR", "info": "INFO"}[severity]
    print(f"  [{tag}] {description}")

def take_screenshot(page, name):
    path = SCREENSHOT_DIR / f"{name}.png"
    page.screenshot(path=str(path), full_page=True)
    screenshots.append(str(path))
    print(f"  [SCREENSHOT] {name}.png")

def test_home(page):
    print("\n=== Home Page (/) ===")
    page.goto(BASE_URL, wait_until="networkidle", timeout=30000)
    time.sleep(2)
    
    # Check page loads
    title = page.title()
    print(f"  Title: {title}")
    
    # Check for console errors
    console_errors = []
    page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
    
    # Check key elements
    graph_area = page.query_selector(".graph-layout, .graph-container, canvas, svg, .home-page, #app")
    if graph_area:
        print("  [OK] Graph/app container found")
    else:
        log_issue("major", "Home", "No graph/app container found")
    
    # Check for node/edge count display
    body_text = page.inner_text("body")
    if "节点" in body_text or "node" in body_text.lower():
        print("  [OK] Node count displayed")
    else:
        log_issue("minor", "Home", "No node count displayed")
    
    if "关联" in body_text or "edge" in body_text.lower():
        print("  [OK] Edge count displayed")
    else:
        log_issue("minor", "Home", "No edge count displayed")
    
    # Check navigation links
    nav_links = page.query_selector_all("nav a, .nav-link, .sidebar a, a[href]")
    print(f"  Navigation links: {len(nav_links)}")
    
    take_screenshot(page, "01_home")

def test_positions(page):
    print("\n=== Positions Page (/positions) ===")
    page.goto(f"{BASE_URL}/positions", wait_until="networkidle", timeout=30000)
    time.sleep(2)
    
    body_text = page.inner_text("body")
    
    # Check position cards
    cards = page.query_selector_all(".position-card, .card, .el-card, [class*=position]")
    if len(cards) > 0:
        print(f"  [OK] Position cards found: {len(cards)}")
    else:
        log_issue("major", "Positions", "No position cards found")
    
    # Check loading state
    if "加载" in body_text or "loading" in body_text.lower():
        time.sleep(3)  # Wait for loading
    
    # Check search/filter
    search = page.query_selector("input[type=search], input[placeholder*=搜索], input[placeholder*=search], .search-input")
    if search:
        print("  [OK] Search input found")
        # Test search
        search.fill("Python")
        time.sleep(1)
        print("  [OK] Search 'Python' submitted")
    else:
        log_issue("minor", "Positions", "No search input found")
    
    take_screenshot(page, "02_positions")

def test_position_detail(page):
    print("\n=== Position Detail ===")
    # Try clicking first position card
    page.goto(f"{BASE_URL}/positions", wait_until="networkidle", timeout=30000)
    time.sleep(2)
    
    card = page.query_selector(".position-card, .card, .el-card, [class*=position]")
    if card:
        card.click()
        time.sleep(2)
        body_text = page.inner_text("body")
        
        if "技能" in body_text or "skill" in body_text.lower():
            print("  [OK] Skills displayed in detail")
        else:
            log_issue("major", "PositionDetail", "No skills in position detail")
        
        take_screenshot(page, "03_position_detail")
    else:
        log_issue("major", "PositionDetail", "Cannot click position card - none found")
        take_screenshot(page, "03_position_detail_empty")

def test_match_diagnosis(page):
    print("\n=== Match Diagnosis (/match) ===")
    page.goto(f"{BASE_URL}/match", wait_until="networkidle", timeout=30000)
    time.sleep(2)
    
    body_text = page.inner_text("body")
    
    # Check form elements
    inputs = page.query_selector_all("input, select, textarea")
    print(f"  Form inputs found: {len(inputs)}")
    
    # Check for file upload
    upload = page.query_selector("input[type=file], .upload, .el-upload")
    if upload:
        print("  [OK] File upload found")
    else:
        log_issue("minor", "Match", "No file upload found")
    
    # Check for position selection
    select = page.query_selector("select, .el-select, [class*=select]")
    if select:
        print("  [OK] Position selector found")
    else:
        log_issue("minor", "Match", "No position selector found")
    
    take_screenshot(page, "04_match")

def test_admin(page):
    print("\n=== Admin Page (/admin) ===")
    page.goto(f"{BASE_URL}/admin", wait_until="networkidle", timeout=30000)
    time.sleep(2)
    
    body_text = page.inner_text("body")
    
    # Check key admin sections
    sections = ["审核", "review", "数据源", "source", "Prompt", "prompt"]
    found = [s for s in sections if s in body_text.lower() or s in body_text]
    print(f"  Admin sections found: {found}")
    
    if "审核" in body_text:
        print("  [OK] Review queue section found")
    else:
        log_issue("major", "Admin", "No review queue section")
    
    if "Prompt" in body_text or "prompt" in body_text:
        print("  [OK] Prompt management found")
    else:
        log_issue("minor", "Admin", "No prompt management")
    
    # Check data table
    table = page.query_selector("table, .el-table, .data-table")
    if table:
        print("  [OK] Data table found")
    else:
        log_issue("minor", "Admin", "No data table found")
    
    take_screenshot(page, "05_admin")

def test_quality(page):
    print("\n=== Quality Dashboard (/quality) ===")
    page.goto(f"{BASE_URL}/quality", wait_until="networkidle", timeout=30000)
    time.sleep(2)
    
    body_text = page.inner_text("body")
    
    quality_indicators = ["质量", "quality", "信任", "trust", "幻觉", "hallucination", "分布", "distribution"]
    found = [s for s in quality_indicators if s in body_text.lower() or s in body_text]
    print(f"  Quality indicators: {found}")
    
    # Check charts
    charts = page.query_selector_all("canvas, svg, .chart, .echarts, [class*=chart]")
    if len(charts) > 0:
        print(f"  [OK] Charts found: {len(charts)}")
    else:
        log_issue("minor", "Quality", "No charts found")
    
    take_screenshot(page, "06_quality")

def test_evolution(page):
    print("\n=== Evolution Dashboard (/evolution) ===")
    page.goto(f"{BASE_URL}/evolution", wait_until="networkidle", timeout=30000)
    time.sleep(2)
    
    body_text = page.inner_text("body")
    
    evolution_indicators = ["演化", "evolution", "趋势", "trend", "新兴", "emerging"]
    found = [s for s in evolution_indicators if s in body_text.lower() or s in body_text]
    print(f"  Evolution indicators: {found}")
    
    # Check charts
    charts = page.query_selector_all("canvas, svg, .chart, .echarts, [class*=chart]")
    if len(charts) > 0:
        print(f"  [OK] Charts found: {len(charts)}")
    else:
        log_issue("minor", "Evolution", "No charts found")
    
    take_screenshot(page, "07_evolution")

def main():
    print("StarMap Browser QA - Automated Testing")
    print("=" * 50)
    print(f"Target: {BASE_URL}")
    print(f"Screenshots: {SCREENSHOT_DIR}")
    print("=" * 50)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            locale="zh-CN"
        )
        
        # Capture console errors
        all_console = []
        context.on("console", lambda msg: all_console.append({"type": msg.type, "text": msg.text}))
        
        page = context.new_page()
        
        try:
            test_home(page)
            test_positions(page)
            test_position_detail(page)
            test_match_diagnosis(page)
            test_admin(page)
            test_quality(page)
            test_evolution(page)
        except Exception as e:
            log_issue("critical", "General", f"Test execution error: {e}")
        
        # Report console errors
        errors = [c for c in all_console if c["type"] == "error"]
        if errors:
            print(f"\n=== Console Errors ({len(errors)}) ===")
            for e in errors[:10]:
                print(f"  [CONSOLE ERROR] {e['text'][:200]}")
        
        browser.close()
    
    # Summary
    print(f"\n{'='*50}")
    print("QA SUMMARY")
    print(f"{'='*50}")
    print(f"Screenshots: {len(screenshots)}")
    print(f"Issues found: {len(issues)}")
    
    by_severity = {}
    for issue in issues:
        sev = issue["severity"]
        by_severity[sev] = by_severity.get(sev, 0) + 1
    
    for sev in ["critical", "major", "minor", "info"]:
        if sev in by_severity:
            print(f"  {sev}: {by_severity[sev]}")
    
    for issue in issues:
        tag = issue["severity"].upper()
        print(f"  [{tag}] {issue['page']}: {issue['description']}")
    
    # Save results
    results = {
        "test_date": "2026-06-28",
        "base_url": BASE_URL,
        "screenshots": screenshots,
        "issues": issues,
        "console_errors": [{"type": c["type"], "text": c["text"][:500]} for c in all_console if c["type"] == "error"]
    }
    with open(str(SCREENSHOT_DIR / "qa_results.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nResults saved to {SCREENSHOT_DIR / 'qa_results.json'}")

if __name__ == "__main__":
    main()
