"""Debug: Check node groups in scene"""
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
        
        # Check scene hierarchy
        result = await page.evaluate("""
            (function() {
                const graph = window.__graph3d;
                if (!graph) return 'No __graph3d found';
                
                const scene = graph.scene();
                const hierarchy = [];
                
                function traverse(obj, depth) {
                    const info = {
                        type: obj.type,
                        name: obj.name,
                        visible: obj.visible,
                        position: {x: obj.position.x, y: obj.position.y, z: obj.position.z},
                        children: []
                    };
                    
                    for (const child of obj.children) {
                        info.children.push(traverse(child, depth + 1));
                    }
                    
                    return info;
                }
                
                return traverse(scene, 0);
            })()
        """)
        print(f"Result: {result}")
        
        await asyncio.sleep(3)
        await browser.close()

asyncio.run(main())
