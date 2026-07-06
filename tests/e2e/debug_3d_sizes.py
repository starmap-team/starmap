"""Debug: Check node sizes and camera distance"""
import asyncio
import math
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
        
        # Check node sizes and camera distance
        result = await page.evaluate("""
            (function() {
                const graph = window.__graph3d;
                if (!graph) return 'No __graph3d found';
                
                const data = graph.graphData();
                const camera = graph.camera();
                
                // Calculate distances
                const nodes = data.nodes.map(n => ({
                    id: n.id,
                    x: n.x,
                    y: n.y,
                    z: n.z,
                    distanceFromOrigin: Math.sqrt(n.x*n.x + n.y*n.y + n.z*n.z),
                    distanceFromCamera: Math.sqrt(
                        (n.x - camera.position.x)**2 + 
                        (n.y - camera.position.y)**2 + 
                        (n.z - camera.position.z)**2
                    )
                }));
                
                // Get node radius from the scene
                const scene = graph.scene();
                let totalRadius = 0;
                let count = 0;
                
                scene.traverse((obj) => {
                    if (obj.isMesh && obj.geometry && obj.geometry.parameters) {
                        totalRadius += obj.geometry.parameters.radius || 0;
                        count++;
                    }
                });
                
                const avgRadius = count > 0 ? totalRadius / count : 0;
                
                return {
                    nodes: nodes,
                    cameraPosition: {
                        x: camera.position.x,
                        y: camera.position.y,
                        z: camera.position.z
                    },
                    avgNodeRadius: avgRadius,
                    nodeCount: count
                };
            })()
        """)
        print(f"Result: {result}")
        
        await asyncio.sleep(3)
        await browser.close()

asyncio.run(main())
