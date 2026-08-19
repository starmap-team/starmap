import asyncio
from playwright.async_api import async_playwright

PAGES = [
    ("/", "全景图谱", "home"),
    ("/positions", "岗位列表", "positions"),
    ("/pipeline", "数据流水线", "pipeline"),
    ("/datasources", "数据源管理", "datasources"),
    ("/match", "匹配诊断", "match"),
    ("/extract", "JD抽取", "extract"),
    ("/loop", "闭环演示", "loop"),
    ("/learning", "学习中心", "learning"),
    ("/dashboard", "数据大屏", "dashboard"),
    ("/evolution", "演化看板", "evolution"),
    ("/quality", "图谱质量", "quality"),
    ("/admin", "管理后台", "admin"),
]

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1920, "height": 1080})
        
        # 1. Login
        print("=== LOGIN ===")
        await page.goto("http://localhost:5173/login", timeout=15000)
        await page.wait_for_load_state("networkidle", timeout=10000)
        
        inputs = page.locator("input")
        count = await inputs.count()
        print("  Found %d inputs" % count)
        
        if count >= 2:
            await inputs.nth(0).fill("admin")
            await inputs.nth(1).fill("starmap2024")
            await page.locator("button[type='submit']").click()
            await page.wait_for_url("**/", timeout=10000)
            print("  Login OK -> %s" % page.url)
        else:
            print("  WARNING: Could not find login form")
        
        # 2. Navigate all pages
        results = []
        for path, title, name in PAGES:
            print("\n=== %s (%s) ===" % (title, path))
            try:
                await page.goto("http://localhost:5173" + path, timeout=15000)
                await page.wait_for_load_state("networkidle", timeout=10000)
                
                errors = await page.locator(".el-message--error").count()
                warnings = await page.locator(".el-message--warning").count()
                body_text = await page.locator("body").inner_text()
                has_content = len(body_text.strip()) > 50
                
                await page.screenshot(path="screenshots/%s.png" % name, full_page=False)
                
                status = "OK" if errors == 0 else "ERRORS:%d" % errors
                print("  Status: %s | Warnings: %d | Content: %s" % (status, warnings, "YES" if has_content else "EMPTY"))
                results.append({"page": name, "path": path, "title": title, "errors": errors, "warnings": warnings, "has_content": has_content})
                
            except Exception as e:
                print("  FAILED: %s" % str(e)[:100])
                results.append({"page": name, "path": path, "title": title, "errors": -1, "warnings": 0, "has_content": False, "error": str(e)})
        
        # 3. Summary
        print("\n" + "=" * 60)
        print("E2E SUMMARY")
        print("=" * 60)
        ok = sum(1 for r in results if r["errors"] == 0)
        fail = sum(1 for r in results if r["errors"] < 0)
        err = sum(1 for r in results if r["errors"] > 0)
        print("  Total: %d | OK: %d | Errors: %d | Failed: %d" % (len(results), ok, err, fail))
        for r in results:
            icon = "OK" if r["errors"] == 0 else ("FAIL" if r["errors"] < 0 else "WARN")
            extra = ""
            if r["errors"] != 0:
                if "error" in r:
                    extra = " (%s)" % r["error"][:60]
                else:
                    extra = " (%d errors)" % r["errors"]
            print("  [%s] %s %s%s" % (icon, r["title"], r["path"], extra))
        
        await browser.close()

asyncio.run(main())
