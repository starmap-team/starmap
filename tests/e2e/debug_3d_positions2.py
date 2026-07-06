"""Debug: Check node positions in scene vs data"""
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
        
        # Check node positions
        result = await page.evaluate("""
            (function() {
                const graph = window.__graph3d;
                if (!graph) return 'No __graph3d found';
                
                const data = graph.graphData();
                const scene = graph.scene();
                
                // Find the group that contains the nodes
                const group = scene.children.find(c => c.type === 'Group');
                if (!group) return 'No group found';
                
                // Map data nodes to scene meshes
                const results = [];
                for (let i = 0; i < data.nodes.length; i++) {
                    const node = data.nodes[i];
                    const mesh = group.children[i];
                    if (mesh) {
                        results.push({
                            id: node.id,
                            dataPos: {x: node.x, y: node.y, z: node.z},
                            meshPos: {x: mesh.position.x, y: mesh.position.y, z: mesh.position.z},
                            meshType: mesh.type
                        });
                    }
                }
                
                return results;
            })()
        """)
        print(f"Result: {result}")
        
        await asyncio.sleep(3)
        await browser.close()

asyncio.run(main())
