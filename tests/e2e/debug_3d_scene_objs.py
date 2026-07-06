"""Debug: Check what's in the scene"""
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
        
        # Check scene objects
        result = await page.evaluate("""
            (function() {
                const graph = window.__graph3d;
                if (!graph) return 'No __graph3d found';
                
                const scene = graph.scene();
                const objects = [];
                
                scene.traverse((obj) => {
                    if (obj.isMesh) {
                        const info = {
                            type: obj.type,
                            name: obj.name,
                            position: {x: obj.position.x, y: obj.position.y, z: obj.position.z},
                            scale: {x: obj.scale.x, y: obj.scale.y, z: obj.scale.z},
                        };
                        if (obj.geometry && obj.geometry.parameters) {
                            info.radius = obj.geometry.parameters.radius;
                        }
                        objects.push(info);
                    }
                });
                
                return {
                    meshCount: objects.length,
                    objects: objects
                };
            })()
        """)
        print(f"Result: {result}")
        
        await asyncio.sleep(3)
        await browser.close()

asyncio.run(main())
