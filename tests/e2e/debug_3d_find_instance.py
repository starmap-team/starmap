"""Debug: Find graph instance"""
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
        
        # Find graph instance
        result = await page.evaluate("""
            (function() {
                // Look for graph instance in all possible locations
                const candidates = [];
                
                // Check window
                for (const key in window) {
                    if (key.toLowerCase().includes('graph')) {
                        const val = window[key];
                        if (val && typeof val === 'object' && val.graphData) {
                            candidates.push({key: key, type: typeof val});
                        }
                    }
                }
                
                return candidates;
            })()
        """)
        print(f"Result: {result}")
        
        await asyncio.sleep(3)
        await browser.close()

asyncio.run(main())
