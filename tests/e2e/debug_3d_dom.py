"""Debug: Check DOM structure"""
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
        await page.wait_for_timeout(5000)
        
        # Check DOM structure
        result = await page.evaluate("""
            (function() {
                const containers = document.querySelectorAll('[id*="graph"], [class*="graph"]');
                const canvas = document.querySelectorAll('canvas');
                return {
                    containerCount: containers.length,
                    containers: Array.from(containers).map(c => ({id: c.id, class: c.className, tag: c.tagName})),
                    canvasCount: canvas.length,
                    canvasSizes: Array.from(canvas).map(c => ({width: c.width, height: c.height, clientWidth: c.clientWidth, clientHeight: c.clientHeight}))
                };
            })()
        """)
        print(f"DOM: {result}")
        
        await asyncio.sleep(3)
        await browser.close()

asyncio.run(main())
