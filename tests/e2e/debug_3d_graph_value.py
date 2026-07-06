"""Debug: Check graph instance value"""
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
        
        # Check graph instance value
        result = await page.evaluate("""
            (function() {
                const container = document.querySelector('.graph3d-container');
                if (!container) return 'No container found';
                
                const vueComponent = container.__vueParentComponent;
                if (!vueComponent) return 'No Vue component';
                
                const graphInstance = vueComponent.setupState.graphInstance;
                if (!graphInstance) return 'No graph instance';
                
                return {
                    hasGraphData: typeof graphInstance.graphData === 'function',
                    hasScene: typeof graphInstance.scene === 'function',
                    hasCamera: typeof graphInstance.camera === 'function',
                    nodeCount: graphInstance.graphData().nodes.length
                };
            })()
        """)
        print(f"Result: {result}")
        
        await asyncio.sleep(3)
        await browser.close()

asyncio.run(main())
