import json
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = "http://localhost:5173"
OUT = Path(__file__).resolve().parent / "browser_qa_match_extract"
OUT.mkdir(parents=True, exist_ok=True)


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
        page = ctx.new_page()

        logs = []
        responses = []
        page.on("console", lambda m: logs.append({"type": m.type, "text": m.text}))

        def on_resp(resp):
            info = {"url": resp.url, "status": resp.status, "method": resp.request.method}
            if "match/position" in resp.url or "extract/jd" in resp.url:
                try:
                    info["body"] = resp.text()
                except Exception:
                    info["body"] = None
            responses.append(info)

        page.on("response", on_resp)

        def ss(name):
            page.screenshot(path=str(OUT / f"{name}.png"), full_page=True)

        # Match flow
        page.goto(f"{BASE}/match", wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(2000)
        ss("01_match_start")
        page.get_by_placeholder("输入技能名称后回车添加").fill("Python")
        page.get_by_placeholder("输入技能名称后回车添加").press("Enter")
        page.wait_for_timeout(500)
        page.get_by_role("button", name="确认").click()
        page.wait_for_timeout(1000)
        ss("02_match_skills_added")
        page.locator(".el-select .el-input__inner").first.wait_for(state="visible")
        page.locator(".el-select .el-input__inner").first.click()
        page.locator(".el-select .el-input__inner").first.fill("Python")
        page.wait_for_timeout(2000)
        page.locator(".el-select-dropdown__item").first.wait_for(state="visible")
        page.locator(".el-select-dropdown__item").first.click()
        page.wait_for_timeout(3000)
        ss("03_match_position_selected")
        page.get_by_role("button", name="开始诊断").click()
        page.wait_for_timeout(8000)
        ss("04_match_diagnosis")

        # Extract flow
        page.goto(f"{BASE}/extract", wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(2000)
        page.locator("textarea").first.fill(
            "Python Backend Developer\nSkills: Python, Django, FastAPI, MySQL, Redis, Docker, Git"
        )
        page.locator("button:has-text('提交分析')").click()
        page.wait_for_timeout(10000)
        ss("05_extract_result")

        match_resps = [r for r in responses if "match/position" in r.get("url", "")]
        match_failures = [r for r in match_resps if r.get("status", 0) >= 400]
        extract_resps = [r for r in responses if "extract/jd" in r.get("url", "")]
        console_errs = [m for m in logs if m["type"] == "error" and "favicon" not in m["text"].lower()]

        print("match_responses", len(match_resps))
        print("match_failures", len(match_failures))
        for r in match_failures[:5]:
            print("MATCH_FAIL", r.get("status"), r.get("url"))
            print((r.get("body") or "")[:500])
        print("extract_responses", len(extract_resps))
        for r in extract_resps[:5]:
            print("EXTRACT", r.get("status"), r.get("url"))
            print((r.get("body") or "")[:500])
        print("console_errors", len(console_errs))
        for e in console_errs[:10]:
            print("ERR", e["text"][:500])

        out = {
            "match_resps": match_resps,
            "match_failures": match_failures,
            "extract_resps": extract_resps,
            "console_errs": console_errs,
            "responses_count": len(responses),
        }
        (OUT / "summary.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        browser.close()


if __name__ == "__main__":
    main()
