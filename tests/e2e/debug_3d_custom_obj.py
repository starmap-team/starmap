"""Debug: Check custom object creation"""
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
        
        # Check custom objects
        result = await page.evaluate("""
            (function() {
                const graph = window.__graph3d;
                if (!graph) return 'No __graph3d found';
                
                const scene = graph.scene();
                const group = scene.children.find(c => c.type === 'Group');
                if (!group) return 'No group found';
                
                const results = [];
                for (const mesh of group.children) {
                    results.push({
                        type: mesh.type,
                        __graphObjType: mesh.__graphObjType,
                        __graphDefaultObj: mesh.__graphDefaultObj,
                        children: mesh.children.map(c => c.type)
                    });
                }
                
                return results;
            })()
        """)
        print(f"Result: {result}")
        
        await asyncio.sleep(3)
        await browser.close()

asyncio.run(main())
