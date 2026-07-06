"""Debug: Check update mechanism"""
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
        
        # Check update mechanism
        result = await page.evaluate("""
            (function() {
                const container = document.querySelector('.graph3d-container');
                const vueComponent = container.__vueParentComponent;
                const graphInstance = vueComponent.setupState.graphInstance;
                
                // Check if nodePositionUpdate is set
                const nodePositionUpdate = graphInstance.nodePositionUpdate();
                
                return {
                    hasNodePositionUpdate: !!nodePositionUpdate,
                    nodePositionUpdateType: typeof nodePositionUpdate
                };
            })()
        """)
        print(f"Result: {result}")
        
        await asyncio.sleep(3)
        await browser.close()

asyncio.run(main())
