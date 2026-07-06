"""Debug: Find graph instance ref"""
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
        
        # Find graph instance ref
        result = await page.evaluate("""
            (function() {
                const container = document.querySelector('.graph3d-container');
                if (!container) return 'No container found';
                
                const vueComponent = container.__vueParentComponent;
                if (!vueComponent) return 'No Vue component';
                
                // Check all refs
                const refs = vueComponent.refs || {};
                const setupState = vueComponent.setupState || {};
                
                return {
                    refs: Object.keys(refs),
                    setupState: Object.keys(setupState),
                    hasGraphInstance: 'graphInstance' in setupState
                };
            })()
        """)
        print(f"Result: {result}")
        
        await asyncio.sleep(3)
        await browser.close()

asyncio.run(main())
