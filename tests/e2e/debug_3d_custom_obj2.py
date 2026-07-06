"""Debug: Check custom object creation"""
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
        
        # Check custom object creation
        result = await page.evaluate("""
            (function() {
                const container = document.querySelector('.graph3d-container');
                const vueComponent = container.__vueParentComponent;
                const graphInstance = vueComponent.setupState.graphInstance;
                
                const scene = graphInstance.scene();
                const group = scene.children.find(c => c.type === 'Group');
                
                const objects = [];
                for (const child of group.children) {
                    if (child.__graphObjType === 'node') {
                        objects.push({
                            hasGraphData: !!child.__graphData,
                            graphDataId: child.__graphData ? child.__graphData.id : 'no data',
                            position: {x: child.position.x, y: child.position.y, z: child.position.z},
                            scale: {x: child.scale.x, y: child.scale.y, z: child.scale.z}
                        });
                    }
                }
                
                return objects;
            })()
        """)
        print(f"Result: {result}")
        
        await asyncio.sleep(3)
        await browser.close()

asyncio.run(main())
