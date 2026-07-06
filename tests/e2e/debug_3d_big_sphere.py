"""Debug: Check the big sphere"""
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
        
        # Check the big sphere
        result = await page.evaluate("""
            (function() {
                const graph = window.__graph3d;
                if (!graph) return 'No __graph3d found';
                
                const scene = graph.scene();
                let bigSphere = null;
                
                scene.traverse((obj) => {
                    if (obj.isMesh && obj.geometry && obj.geometry.parameters && obj.geometry.parameters.radius === 50000) {
                        bigSphere = {
                            type: obj.type,
                            name: obj.name,
                            uuid: obj.uuid,
                            material: obj.material ? {
                                type: obj.material.type,
                                color: obj.material.color ? obj.material.color.getHexString() : 'none',
                                transparent: obj.material.transparent,
                                opacity: obj.material.opacity
                            } : 'no material',
                            parent: obj.parent ? obj.parent.type : 'no parent'
                        };
                    }
                });
                
                return bigSphere || 'No big sphere found';
            })()
        """)
        print(f"Result: {result}")
        
        await asyncio.sleep(3)
        await browser.close()

asyncio.run(main())
