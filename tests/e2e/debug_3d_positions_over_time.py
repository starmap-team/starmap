"""Debug: Check node positions over time"""
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
        
        # Check node positions over time
        result = await page.evaluate("""
            (function() {
                const graph = window.__graph3d;
                if (!graph) return 'No __graph3d found';
                
                const data = graph.graphData();
                
                // Check positions at different times
                const positions = [];
                for (let i = 0; i < 5; i++) {
                    const node = data.nodes[i];
                    if (node) {
                        positions.push({
                            id: node.id,
                            x: node.x,
                            y: node.y,
                            z: node.z
                        });
                    }
                }
                
                return positions;
            })()
        """)
        print(f"Result: {result}")
        
        await asyncio.sleep(3)
        await browser.close()

asyncio.run(main())
