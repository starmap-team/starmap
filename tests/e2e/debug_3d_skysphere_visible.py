"""Debug: Check skysphere visibility"""
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
        
        # Check skysphere
        result = await page.evaluate("""
            (function() {
                const graph = window.__graph3d;
                if (!graph) return 'No __graph3d found';
                
                const scene = graph.scene();
                let skysphere = null;
                
                scene.traverse((obj) => {
                    if (obj.isMesh && obj.geometry && obj.geometry.parameters && obj.geometry.parameters.radius === 50000) {
                        skysphere = {
                            visible: obj.visible,
                            material: obj.material ? {
                                type: obj.material.type,
                                transparent: obj.material.transparent,
                                opacity: obj.material.opacity,
                                side: obj.material.side,
                                map: obj.material.map ? 'has map' : 'no map'
                            } : 'no material'
                        };
                    }
                });
                
                return skysphere || 'No skysphere found';
            })()
        """)
        print(f"Result: {result}")
        
        await asyncio.sleep(3)
        await browser.close()

asyncio.run(main())
