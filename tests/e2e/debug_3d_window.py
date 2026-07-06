"""Debug: Check window object"""
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(viewport={'width': 1280, 'height': 720})
        page = await context.new_page()
        
        await page.goto("http://localhost:5177/")
        await page.wait_for_timeout(3000)
        
        # Click 3D button
        await page.click("button:has-text('3D')")
        await page.wait_for_timeout(10000)
        
        # Check window object
        result = await page.evaluate("""
            (function() {
                return {
                    hasGraph3d: !!window.__graph3d,
                    graphType: typeof window.__graph3d,
                    graphKeys: window.__graph3d ? Object.keys(window.__graph3d).slice(0, 10) : 'N/A'
                };
            })()
        """)
        print(f"Result: {result}")
        
        await asyncio.sleep(3)
        await browser.close()

asyncio.run(main())
