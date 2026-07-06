"""Debug: Check nodePositionUpdate callback"""
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
        
        # Check nodePositionUpdate callback
        result = await page.evaluate("""
            (function() {
                const container = document.querySelector('.graph3d-container');
                const vueComponent = container.__vueParentComponent;
                const graphInstance = vueComponent.setupState.graphInstance;
                
                // Set a custom nodePositionUpdate callback
                let updateCount = 0;
                graphInstance.nodePositionUpdate((obj, pos, node) => {
                    updateCount++;
                    return false; // Don't skip default update
                });
                
                // Wait a bit
                setTimeout(() => {
                    window.__updateCount = updateCount;
                }, 100);
                
                return 'Callback set';
            })()
        """)
        print(f"Result: {result}")
        
        await asyncio.sleep(1)
        
        # Check update count
        result2 = await page.evaluate("""
            (function() {
                return window.__updateCount || 0;
            })()
        """)
        print(f"Update count: {result2}")
        
        await asyncio.sleep(3)
        await browser.close()

asyncio.run(main())
