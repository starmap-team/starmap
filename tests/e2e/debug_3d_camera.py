"""Debug: Check camera and node positions"""
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
        
        # Check camera and node positions
        result = await page.evaluate("""
            (function() {
                const graph = document.querySelector('#graph-3d-container');
                if (!graph) return 'No graph container';
                
                // Try to access the graph instance
                const graphInstance = graph.__graph || window._graph;
                if (!graphInstance) return 'No graph instance';
                
                const data = graphInstance.graphData();
                const nodes = data.nodes.slice(0, 3).map(n => ({
                    id: n.id,
                    x: n.x,
                    y: n.y,
                    z: n.z
                }));
                
                // Get camera position
                const camera = graphInstance.camera();
                const cameraPos = camera ? {
                    x: camera.position.x,
                    y: camera.position.y,
                    z: camera.position.z
                } : 'No camera';
                
                return {nodes: nodes, camera: cameraPos};
            })()
        """)
        print(f"Result: {result}")
        
        await asyncio.sleep(3)
        await browser.close()

asyncio.run(main())
