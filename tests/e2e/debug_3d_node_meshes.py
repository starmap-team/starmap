"""Debug: Check node meshes in scene"""
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
        
        # Check node meshes
        result = await page.evaluate("""
            (function() {
                const graph = window.__graph3d;
                if (!graph) return 'No __graph3d found';
                
                const scene = graph.scene();
                const meshes = [];
                
                scene.traverse((obj) => {
                    if (obj.isMesh) {
                        meshes.push({
                            type: obj.type,
                            name: obj.name,
                            visible: obj.visible,
                            position: {x: obj.position.x, y: obj.position.y, z: obj.position.z},
                            scale: {x: obj.scale.x, y: obj.scale.y, z: obj.scale.z},
                            geometry: obj.geometry ? {
                                type: obj.geometry.type,
                                radius: obj.geometry.parameters ? obj.geometry.parameters.radius : 'no radius'
                            } : 'no geometry',
                            material: obj.material ? {
                                type: obj.material.type,
                                color: obj.material.color ? obj.material.color.getHexString() : 'none',
                                transparent: obj.material.transparent,
                                opacity: obj.material.opacity
                            } : 'no material'
                        });
                    }
                });
                
                return meshes;
            })()
        """)
        print(f"Result: {result}")
        
        await asyncio.sleep(3)
        await browser.close()

asyncio.run(main())
