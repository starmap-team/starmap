import asyncio
from playwright.async_api import async_playwright

RECHECK = [
    ("/pipeline", "数据流水线", "pipeline"),
    ("/dashboard", "数据大屏", "dashboard"),
]

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
        print("Login OK")
        
        for path, title, name in RECHECK:
            print("\n=== %s (%s) ===" % (title, path))
            await page.goto("http://localhost:5173" + path, timeout=15000)
            # Use domcontentloaded instead of networkidle for SSE pages
            await page.wait_for_load_state("domcontentloaded", timeout=10000)
            # Wait extra time for content to render
            await asyncio.sleep(3)
            
            errors = await page.locator(".el-message--error").count()
            body_text = await page.locator("body").inner_text()
            has_content = len(body_text.strip()) > 50
            
            await page.screenshot(path="screenshots/%s.png" % name, full_page=False)
            
            print("  Errors: %d | Content: %d chars | Has content: %s" % (errors, len(body_text), "YES" if has_content else "EMPTY"))
            # Show first 200 chars of body
            print("  Preview: %s" % body_text[:200].replace("\n", " "))
        
        await browser.close()

asyncio.run(main())
