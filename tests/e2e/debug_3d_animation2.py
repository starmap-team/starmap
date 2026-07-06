"""Debug: Check animation loop"""
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
        
        # Check animation loop
        result = await page.evaluate("""
            (function() {
                const container = document.querySelector('.graph3d-container');
                const vueComponent = container.__vueParentComponent;
                const graphInstance = vueComponent.setupState.graphInstance;
                
                // Check if animation is running
                const scene = graphInstance.scene();
                const group = scene.children.find(c => c.type === 'Group');
                
                // Get positions at different times
                const positions1 = group.children.filter(c => c.__graphObjType === 'node').map(c => ({
                    x: c.position.x,
                    y: c.position.y,
                    z: c.position.z
                }));
                
                // Wait a bit and check again
                setTimeout(() => {
                    const positions2 = group.children.filter(c => c.__graphObjType === 'node').map(c => ({
                        x: c.position.x,
                        y: c.position.y,
                        z: c.position.z
                    }));
                    window.__positions2 = positions2;
                }, 100);
                
                return {
                    positions1: positions1,
                    hasPositions2: 'undefined'
                };
            })()
        """)
        print(f"Result: {result}")
        
        await asyncio.sleep(1)
        
        # Check positions after delay
        result2 = await page.evaluate("""
            (function() {
                return window.__positions2 || 'Not set';
            })()
        """)
        print(f"Positions after delay: {result2}")
        
        await asyncio.sleep(3)
        await browser.close()

asyncio.run(main())
