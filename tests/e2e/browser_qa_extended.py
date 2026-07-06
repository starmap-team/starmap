#!/usr/bin/env python3
"""Extended Browser QA — visits all 15 pages, captures screenshots, console errors, network failures, and visual/functional issues."""
import json
import re
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE_URL = "http://localhost:5173"
SCREENSHOT_DIR = Path(__file__).parent.parent.parent / "screenshots" / "qa_extended"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

PAGES = [
    ("home",          "/",            "Home"),
    ("positions",     "/positions",   "PositionList"),
    ("position-detail","/position/Python后端开发工程师", "PositionDetail"),
    ("match",         "/match",       "MatchDiagnosis"),
    ("evolution",     "/evolution",   "EvolutionDashboard"),
    ("quality",       "/quality",     "QualityDashboard"),
    ("pipeline",      "/pipeline",    "PipelineMonitor"),
    ("datasources",   "/datasources", "DataSources"),
    ("analysis",      "/analysis",    "PipelineAnalysis"),
    ("extract",       "/extract",     "ExtractJD"),
    ("loop",          "/loop",        "LoopDemo"),
    ("admin",         "/admin",       "Admin"),
    ("dashboard",     "/dashboard",   "DataDashboard"),
    ("learning",      "/learning",    "LearningCenter"),
]


class Issue:
    def __init__(self, page, sev, cat, desc, ss=None, url=None):
        self.page = page
        self.sev = sev
        self.cat = cat
        self.desc = desc
        self.ss = ss
        self.url = url

    def as_dict(self):
        return {"page": self.page, "severity": self.sev, "category": self.cat, "description": self.desc, "screenshot": self.ss, "url": self.url}


def main():
    issues = []
    passed = []
    screenshots = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
        page = ctx.new_page()
        console_msgs = []
        net_fail = []
        page.on("console", lambda m: console_msgs.append({"type": m.type, "text": m.text}))
        page.on("response", lambda r: net_fail.append({"url": r.url, "status": r.status}) if r.status >= 400 else None)

        for slug, path, label in PAGES:
            console_msgs.clear()
            net_fail.clear()
            print(f"[{label}] {path}")
            try:
                page.goto(BASE_URL + path, wait_until="domcontentloaded", timeout=60000)
            except Exception as e:
                issues.append(Issue(label, "P0", "navigation", f"Navigation failed: {e}", url=path))
                continue
            page.wait_for_timeout(2500)
            ss_path = SCREENSHOT_DIR / f"{slug}.png"
            try:
                page.screenshot(path=str(ss_path), full_page=True)
            except Exception as e:
                issues.append(Issue(label, "P1", "screenshot", f"Screenshot failed: {e}"))
            screenshots.append(str(ss_path))
            url = page.url
            body = page.inner_text("body")
            if len(body) > 200:
                passed.append({"page": label, "check": "Page has content"})
            else:
                issues.append(Issue(label, "P0", "content", f"Page body empty or too short ({len(body)} chars)", ss=str(ss_path), url=url))
            errs = [m for m in console_msgs if m["type"] == "error" and "favicon" not in m["text"].lower()]
            for e in errs[:5]:
                issues.append(Issue(label, "P1", "console", f"Console error: {e['text'][:300]}", ss=str(ss_path)))
            warns = [m for m in console_msgs if m["type"] == "warning" and ("Vue" in m["text"] or "AntV" in m["text"] or "Invalid" in m["text"])]
            for w in warns[:3]:
                issues.append(Issue(label, "P2", "console", f"Vue/AntV warning: {w['text'][:300]}", ss=str(ss_path)))
            srv_errs = [f for f in net_fail if f["status"] >= 500]
            for f in srv_errs[:5]:
                issues.append(Issue(label, "P0", "backend", f"Server {f['status']}: {f['url'][:200]}", ss=str(ss_path)))
            api_errs = [f for f in net_fail if f["status"] >= 400 and ("/api/" in f["url"] or "localhost:8000" in f["url"])]
            for f in api_errs[:5]:
                issues.append(Issue(label, "P1", "backend", f"API {f['status']}: {f['url'][:200]}", ss=str(ss_path)))
            if "暂无" in body and "加载中" not in body:
                issues.append(Issue(label, "P2", "visual", f"Page shows no-data placeholder", ss=str(ss_path), url=url))
            if re.search(r"\d\.\d{6,}", body):
                issues.append(Issue(label, "P1", "visual", f"Float precision noise: {re.findall(r'\\d\\.\\d{6,}', body)[:3]}", ss=str(ss_path), url=url))

        # Specific checks
        print("\n--- Specific checks ---")
        # Position detail click
        print("[Check] Position detail click navigation")
        page.goto(BASE_URL + "/positions", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(2000)
        cards = page.query_selector_all(".position-card")
        if cards and len(cards) > 0:
            cards[0].click()
            page.wait_for_timeout(3000)
            url = page.url
            if "/position/" not in url:
                issues.append(Issue("PositionList", "P0", "navigation", f"Click on position card did not navigate to /position/ (URL: {url})", url=url))
            else:
                passed.append({"page": "PositionList", "check": "Click navigates to detail"})
                page.wait_for_timeout(2000)
                body = page.inner_text("body")
                if "技能要求" in body:
                    passed.append({"page": "PositionDetail", "check": "Skill list rendered"})
                else:
                    issues.append(Issue("PositionDetail", "P1", "render", f"Skill list not rendered (URL: {url})", url=url))
        # Extract end-to-end
        print("[Check] Extract JD end-to-end")
        page.goto(BASE_URL + "/extract", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(2000)
        ta = page.query_selector("textarea")
        if ta:
            ta.fill("Senior Python Backend Developer\nSkills: Python, Django, FastAPI, MySQL, Redis, Docker, Git, Kubernetes\nRequirements: 5+ years experience, BS in CS")
            page.wait_for_timeout(500)
            btn = None
            for b in page.query_selector_all("button"):
                t = b.inner_text()
                if any(k in t for k in ["开始抽取", "抽", "Extract"]):
                    btn = b
                    break
            if btn:
                btn.click()
                page.wait_for_timeout(20000)
                page.screenshot(path=str(SCREENSHOT_DIR / "extract_after_submit.png"), full_page=True)
                body = page.inner_text("body")
                if "Python" in body and ("技能" in body or "skill" in body.lower()):
                    passed.append({"page": "Extract", "check": "Extraction returns results"})
                elif "失败" in body or "错误" in body or "error" in body.lower():
                    issues.append(Issue("Extract", "P1", "extraction", f"Extraction failed", ss=str(SCREENSHOT_DIR / "extract_after_submit.png")))
                else:
                    issues.append(Issue("Extract", "P2", "extraction", f"Extraction unclear: page text doesn't show Python skills", ss=str(SCREENSHOT_DIR / "extract_after_submit.png")))
        # Evolution check
        print("[Check] Evolution trend table format")
        page.goto(BASE_URL + "/evolution", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3000)
        body = page.inner_text("body")
        m = re.search(r"[\+\-]?\d+\.\d{6,}", body)
        if m:
            issues.append(Issue("Evolution", "P1", "format", f"Float precision noise: {m.group(0)}", url=page.url))
        # Quality check
        print("[Check] Quality dashboard data")
        page.goto(BASE_URL + "/quality", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3000)
        body = page.inner_text("body")
        if "数据加载中" in body:
            issues.append(Issue("Quality", "P1", "ui", f"Loading placeholder not cleared: '数据加载中' shown", url=page.url))
        # Admin data source
        print("[Check] Admin data source")
        page.goto(BASE_URL + "/admin", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(2000)
        tab = None
        for t in page.query_selector_all(".el-tabs__item"):
            tx = t.inner_text()
            if "数据源" in tx:
                tab = t
                break
        if tab:
            tab.click()
            page.wait_for_timeout(2000)
            page.screenshot(path=str(SCREENSHOT_DIR / "admin_datasource.png"), full_page=True)

        browser.close()
    print("\n" + "=" * 70)
    print("EXTENDED BROWSER QA REPORT")
    print("=" * 70)
    print(f"\nPages tested: {len(PAGES)}")
    print(f"Passed: {len(passed)}")
    for p in passed:
        print(f"  [PASS] {p['page']}: {p['check']}")
    print(f"\nIssues: {len(issues)}")
    by_sev = {}
    for i in issues:
        by_sev.setdefault(i.sev, []).append(i)
    for sev in ["P0", "P1", "P2", "P3"]:
        items = by_sev.get(sev, [])
        if items:
            print(f"\n  [{sev}] ({len(items)} issues)")
            for i in items:
                ss = f" -> {i.ss}" if i.ss else ""
                url = f" [{i.url}]" if i.url else ""
                print(f"    [{i.cat}] {i.page}: {i.desc}{url}{ss}")
    out = {
        "timestamp": datetime.now().isoformat(),
        "pages_tested": len(PAGES),
        "passed": len(passed),
        "issues": len(issues),
        "details": [i.as_dict() for i in issues],
        "passed_details": passed,
        "screenshots": screenshots,
    }
    p_out = SCREENSHOT_DIR / "qa_extended_results.json"
    with open(p_out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\nSaved: {p_out}")


if __name__ == "__main__":
    main()
