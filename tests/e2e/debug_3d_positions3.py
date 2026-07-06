"""Debug: Check node positions in scene"""
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
        
        # Check node positions in scene
        result = await page.evaluate("""
            (function() {
                const container = document.querySelector('.graph3d-container');
                const vueComponent = container.__vueParentComponent;
                const graphInstance = vueComponent.setupState.graphInstance;
                
                const scene = graphInstance.scene();
                const group = scene.children.find(c => c.type === 'Group');
                
                const positions = [];
                for (const child of group.children) {
                    if (child.__graphObjType === 'node') {
                        positions.push({
                            id: child.__graphData ? child.__graphData.id : 'unknown',
                            x: child.position.x,
                            y: child.position.y,
                            z: child.position.z
                        });
                    }
                }
                
                return positions;
            })()
        """)
        print(f"Result: {result}")
        
        await asyncio.sleep(3)
        await browser.close()

asyncio.run(main())
