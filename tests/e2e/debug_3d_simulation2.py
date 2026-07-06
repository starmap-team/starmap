"""Debug: Check simulation"""
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
        
        # Check simulation
        result = await page.evaluate("""
            (function() {
                const container = document.querySelector('.graph3d-container');
                const vueComponent = container.__vueParentComponent;
                const graphInstance = vueComponent.setupState.graphInstance;
                
                // Check if d3ReheatSimulation is called
                const data = graphInstance.graphData();
                
                return {
                    nodeCount: data.nodes.length,
                    nodes: data.nodes.map(n => ({
                        id: n.id,
                        x: n.x,
                        y: n.y,
                        z: n.z,
                        vx: n.vx,
                        vy: n.vy,
                        vz: n.vz
                    }))
                };
            })()
        """)
        print(f"Result: {result}")
        
        await asyncio.sleep(3)
        await browser.close()

asyncio.run(main())
