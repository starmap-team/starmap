"""Debug: Check animation loop"""
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
        
        # Check animation loop
        result = await page.evaluate("""
            (function() {
                const graph = window.__graph3d;
                if (!graph) return 'No __graph3d found';
                
                // Check if animation is running
                const scene = graph.scene();
                const group = scene.children.find(c => c.type === 'Group');
                
                // Get node positions at different times
                const positions1 = group.children.filter(c => c.__graphObjType === 'node').map(c => ({
                    x: c.position.x,
                    y: c.position.y,
                    z: c.position.z
                }));
                
                return {
                    positions: positions1,
                    nodeCount: group.children.filter(c => c.__graphObjType === 'node').length
                };
            })()
        """)
        print(f"Result: {result}")
        
        await asyncio.sleep(3)
        await browser.close()

asyncio.run(main())
