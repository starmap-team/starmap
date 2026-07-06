"""Debug: Access exposed graph instance"""
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
        
        # Access the exposed graph instance
        result = await page.evaluate("""
            (function() {
                const graph = window.__graph3d;
                if (!graph) return 'No __graph3d found';
                
                const data = graph.graphData();
                const camera = graph.camera();
                const scene = graph.scene();
                
                // Count objects in scene
                let meshCount = 0;
                let spriteCount = 0;
                let otherCount = 0;
                
                scene.traverse((obj) => {
                    if (obj.isMesh) meshCount++;
                    else if (obj.isSprite) spriteCount++;
                    else otherCount++;
                });
                
                return {
                    nodeCount: data.nodes.length,
                    linkCount: data.links.length,
                    nodes: data.nodes.slice(0, 3).map(n => ({
                        id: n.id,
                        x: n.x,
                        y: n.y,
                        z: n.z,
                        vx: n.vx,
                        vy: n.vy,
                        vz: n.vz
                    })),
                    cameraPosition: camera ? {
                        x: camera.position.x,
                        y: camera.position.y,
                        z: camera.position.z
                    } : 'No camera',
                    sceneStats: {
                        meshCount: meshCount,
                        spriteCount: spriteCount,
                        otherCount: otherCount
                    }
                };
            })()
        """)
        print(f"Result: {result}")
        
        await asyncio.sleep(3)
        await browser.close()

asyncio.run(main())
