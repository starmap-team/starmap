#!/usr/bin/env python3
"""Browser QA Full Test - Tests all 8 pages of StarMap frontend."""
import json
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE_URL = "http://localhost:5173"
SCREENSHOT_DIR = Path(__file__).parent.parent.parent / "screenshots" / "qa_run"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

class QAResults:
    def __init__(self):
        self.issues = []
        self.passed = []
        self.screenshots = []
    def add_issue(self, page, sev, cat, desc, ss=None):
        self.issues.append({"page": page, "severity": sev, "category": cat, "description": desc, "screenshot": ss})
    def add_pass(self, page, check):
        self.passed.append({"page": page, "check": check})
    def report(self):
        print("\n" + "=" * 70)
        print("BROWSER QA REPORT")
        print("=" * 70)
        print(f"\nPassed: {len(self.passed)}")
        for p in self.passed:
            print(f"  [PASS] {p['page']}: {p['check']}")
        print(f"\nIssues: {len(self.issues)}")
        for sev in ["P0","P1","P2","P3"]:
            items = [i for i in self.issues if i["severity"] == sev]
            if items:
                print(f"\n  [{sev}] ({len(items)} issues)")
                for i in items:
                    ss = f" -> {i['screenshot']}" if i['screenshot'] else ""
                    print(f"    [{i['category']}] {i['page']}: {i['description']}{ss}")

def run_qa():
    results = QAResults()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width":1440,"height":900}, locale="zh-CN")
        page = ctx.new_page()
        console_msgs = []
        page.on("console", lambda m: console_msgs.append({"type":m.type,"text":m.text}))
        net_fail = []
        page.on("response", lambda r: net_fail.append({"url":r.url,"status":r.status}) if r.status>=400 else None)

        def ss(name):
            path = SCREENSHOT_DIR / f"{name}.png"
            page.screenshot(path=str(path), full_page=True)
            results.screenshots.append(str(path))
            return str(path)

        def check_errors(pname):
            errs = [m for m in console_msgs if m["type"]=="error" and "favicon" not in m["text"].lower()]
            for e in errs[:5]:
                results.add_issue(pname, "P1", "backend", f"Console error: {e['text'][:200]}")
            console_msgs.clear()
            srv_errs = [f for f in net_fail if f["status"]>=500]
            for f in srv_errs[:5]:
                results.add_issue(pname, "P0", "backend", f"Server {f['status']}: {f['url'][:150]}")
            net_fail.clear()

        # HOME
        print("[1/8] HOME...")
        page.goto(BASE_URL, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(3000)
        s = ss("01_home")
        body = page.inner_text("body")
        if len(body)>100: results.add_pass("Home","Page has content")
        else: results.add_issue("Home","P0","ux","Page empty",s)
        graphs = page.query_selector_all("canvas,svg,[class*=graph],[class*=chart]")
        if graphs: results.add_pass("Home",f"Visualizations: {len(graphs)}")
        else: results.add_issue("Home","P1","visual","No graph/chart on home",s)
        check_errors("Home")

        # POSITIONS
        print("[2/8] POSITIONS...")
        page.goto(f"{BASE_URL}/positions", wait_until="networkidle", timeout=15000)
        page.wait_for_timeout(2000)
        s = ss("02_positions")
        body = page.inner_text("body")
        items = page.query_selector_all("tr,.el-table__row,[class*=item]")
        if items and len(items)>1: results.add_pass("Positions",f"List: {len(items)} items")
        else: results.add_issue("Positions","P1","logic","List empty",s)
        search = page.query_selector("input[type=text],.el-input__inner")
        if search:
            results.add_pass("Positions","Search found")
            search.fill("Python")
            page.wait_for_timeout(1000)
            search.press("Enter")
            page.wait_for_timeout(2000)
            ss("02_positions_search")
        check_errors("Positions")

        # POSITION DETAIL
        print("[3/8] DETAIL...")
        page.goto(f"{BASE_URL}/positions", wait_until="networkidle", timeout=15000)
        page.wait_for_timeout(1000)
        first = page.query_selector("tr:nth-child(2),.el-card,[class*=item]")
        if first:
            first.click()
            page.wait_for_timeout(3000)
        s = ss("03_detail")
        url = page.url
        body = page.inner_text("body")
        if "/position/" in url or "skill" in body.lower() or "\u6280\u80fd" in body: results.add_pass("Detail","Page loaded")
        else: results.add_issue("Detail","P1","logic",f"Not on detail. URL: {url}",s)
        radar = page.query_selector("canvas,svg,[class*=radar],[class*=chart]")
        if radar: results.add_pass("Detail","Chart found")
        else: results.add_issue("Detail","P2","visual","No chart",s)
        check_errors("Detail")

        # EXTRACT JD
        print("[4/8] EXTRACT...")
        page.goto(f"{BASE_URL}/extract", wait_until="networkidle", timeout=15000)
        page.wait_for_timeout(2000)
        s = ss("04_extract")
        # Use textarea selector specifically
        ta = page.query_selector("textarea")
        if not ta:
            ta = page.query_selector(".el-textarea textarea")
        if ta:
            results.add_pass("Extract","Input found")
            # Use page.fill with the textarea selector
            page.locator("textarea").first.fill("Python Backend Developer\nSkills: Python, Django, FastAPI, MySQL, Redis, Docker, Git")
            page.wait_for_timeout(500)
            ss("04_extract_filled")
            btn = None
            for b in page.query_selector_all("button"):
                t = b.inner_text()
                if any(k in t for k in ["\u62bd","\u63d0\u53d6","\u5206\u6790","Extract","Submit","\u63d0\u4ea4"]): btn=b; break
            if btn:
                btn.click()
                page.wait_for_timeout(10000)
                s2 = ss("04_extract_result")
                body = page.inner_text("body")
                if "Python" in body: results.add_pass("Extract","Results contain Python")
                else: results.add_issue("Extract","P1","logic","No extraction results",s2)
            else: results.add_issue("Extract","P1","ux","No submit button",s)
        else: results.add_issue("Extract","P0","ux","No input area",s)
        check_errors("Extract")

        # MATCH
        print("[5/8] MATCH...")
        page.goto(f"{BASE_URL}/match", wait_until="networkidle", timeout=15000)
        page.wait_for_timeout(2000)
        s = ss("05_match")
        body = page.inner_text("body")
        if "\u5339\u914d" in body or "Match" in body: results.add_pass("Match","Page loaded")
        sel = page.query_selector("input[placeholder],.el-input__inner")
        if sel:
            sel.click()
            page.wait_for_timeout(500)
            sel.fill("Python")
            page.wait_for_timeout(2000)
            opt = page.query_selector(".el-select-dropdown__item,[class*=option]")
            if opt:
                opt.click()
                page.wait_for_timeout(1000)
                results.add_pass("Match","Position selected")
        ss("05_match_selected")
        nxt = page.query_selector("button:has-text('\u4e0b\u4e00\u6b65'),button:has-text('Next'),button:has-text('\u7ee7\u7eed')")
        if nxt:
            nxt.click()
            page.wait_for_timeout(2000)
            ss("05_match_step2")
            results.add_pass("Match","Step 2 reached")
        check_errors("Match")

        # EVOLUTION
        print("[6/8] EVOLUTION...")
        page.goto(f"{BASE_URL}/evolution", wait_until="networkidle", timeout=15000)
        page.wait_for_timeout(3000)
        s = ss("06_evolution")
        body = page.inner_text("body")
        if "\u6f14\u5316" in body or "\u8d8b\u52bf" in body: results.add_pass("Evolution","Content loaded")
        charts = page.query_selector_all("canvas,svg,[class*=chart]")
        if charts: results.add_pass("Evolution",f"Charts: {len(charts)}")
        else: results.add_issue("Evolution","P1","visual","No charts",s)
        check_errors("Evolution")

        # QUALITY
        print("[7/8] QUALITY...")
        page.goto(f"{BASE_URL}/quality", wait_until="networkidle", timeout=15000)
        page.wait_for_timeout(2000)
        s = ss("07_quality")
        body = page.inner_text("body")
        if "\u8d28\u91cf" in body or "Quality" in body: results.add_pass("Quality","Page loaded")
        has_m = any(k in body for k in ["F1","\u7cbe\u786e","Precision","\u4fe1\u4efb","Trust"])
        if has_m: results.add_pass("Quality","Metrics found")
        else: results.add_issue("Quality","P1","logic","No metrics",s)
        check_errors("Quality")

        # ADMIN
        print("[8/8] ADMIN...")
        page.goto(f"{BASE_URL}/admin", wait_until="networkidle", timeout=15000)
        page.wait_for_timeout(2000)
        s = ss("08_admin")
        body = page.inner_text("body")
        if "\u7ba1\u7406" in body or "Admin" in body: results.add_pass("Admin","Page loaded")
        btns = page.query_selector_all("button")
        if btns: results.add_pass("Admin",f"Buttons: {len(btns)}")
        check_errors("Admin")

        browser.close()
    return results

if __name__=="__main__":
    r = run_qa()
    r.report()
    out = {"timestamp":datetime.now().isoformat(),"passed":len(r.passed),"issues":len(r.issues),"details":r.issues,"passed_details":r.passed,"screenshots":r.screenshots}
    p = SCREENSHOT_DIR / "qa_results.json"
    with open(p,"w",encoding="utf-8") as f: json.dump(out,f,ensure_ascii=False,indent=2)
    print(f"\nSaved: {p}")
