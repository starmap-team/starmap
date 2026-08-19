import asyncio, json
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1920, "height": 1080})
        
        # Login
        await page.goto("http://localhost:5173/login", timeout=15000)
        await page.wait_for_load_state("networkidle", timeout=10000)
        inputs = page.locator("input")
        await inputs.nth(0).fill("admin")
        await inputs.nth(1).fill("starmap2024")
        await page.locator("button[type='submit']").click()
        await page.wait_for_url("**/", timeout=10000)
        print("LOGIN: OK")
        
        # Collect API responses via route interception
        api_responses = {}
        
        async def handle_response(response):
            url = response.url
            if "/api/v1/" in url:
                try:
                    body = await response.json()
                    api_responses[url.split("/api/v1/")[1].split("?")[0]] = {
                        "status": response.status,
                        "data_type": type(body).__name__,
                        "length": len(body) if isinstance(body, (list, dict)) else 0,
                    }
                except:
                    api_responses[url.split("/api/v1/")[1].split("?")[0]] = {
                        "status": response.status,
                        "data_type": "parse_error",
                    }
        
        page.on("response", handle_response)
        
        # Test each page and collect API calls
        test_pages = [
            ("/", "全景图谱", ["graph/overview"]),
            ("/positions", "岗位列表", ["positions"]),
            ("/datasources", "数据源管理", ["datasources"]),
            ("/match", "匹配诊断", []),
            ("/extract", "JD抽取", []),
            ("/evolution", "演化看板", ["evolution"]),
            ("/quality", "图谱质量", ["quality"]),
            ("/admin", "管理后台", ["admin/users"]),
        ]
        
        results = []
        for path, title, expected_apis in test_pages:
            api_responses.clear()
            await page.goto("http://localhost:5173" + path, timeout=15000)
            await page.wait_for_load_state("domcontentloaded", timeout=10000)
            await asyncio.sleep(2)
            
            errors = await page.locator(".el-message--error").count()
            body_text = await page.locator("body").inner_text()
            
            # Check expected APIs were called
            api_ok = True
            for api in expected_apis:
                found = any(api in k for k in api_responses.keys())
                if not found:
                    api_ok = False
            
            status = "OK" if errors == 0 and api_ok else "ISSUE"
            results.append({
                "title": title,
                "path": path,
                "errors": errors,
                "apis_called": list(api_responses.keys()),
                "expected_apis": expected_apis,
                "api_ok": api_ok,
                "has_content": len(body_text) > 50,
            })
            print("[%s] %s | APIs: %s | Content: %s" % (
                status, title,
                ", ".join(api_responses.keys())[:60],
                "YES" if len(body_text) > 50 else "NO"
            ))
        
        # Check position detail page
        print("\n--- Position Detail ---")
        api_responses.clear()
        await page.goto("http://localhost:5173/positions", timeout=15000)
        await page.wait_for_load_state("domcontentloaded", timeout=10000)
        await asyncio.sleep(2)
        
        # Click first position card
        cards = page.locator(".position-card, .el-card").first
        if await cards.count() > 0:
            await cards.click()
            await asyncio.sleep(2)
            print("Position detail APIs: %s" % ", ".join(api_responses.keys()))
            errors = await page.locator(".el-message--error").count()
            print("Position detail errors: %d" % errors)
        
        # Summary
        print("\n" + "=" * 60)
        print("E2E DATA CONSISTENCY SUMMARY")
        print("=" * 60)
        ok = sum(1 for r in results if r["errors"] == 0 and r["api_ok"])
        print("Pages tested: %d | All OK: %d" % (len(results), ok))
        for r in results:
            icon = "OK" if r["errors"] == 0 and r["api_ok"] else "ISSUE"
            print("  [%s] %s (errors=%d, api_ok=%s)" % (icon, r["title"], r["errors"], r["api_ok"]))
        
        await browser.close()

asyncio.run(main())
