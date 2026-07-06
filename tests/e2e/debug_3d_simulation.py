"""Debug: Check simulation state"""
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
        
        # Check simulation state
        result = await page.evaluate("""
            (function() {
                const graph = window.__graph3d;
                if (!graph) return 'No __graph3d found';
                
                // Check d3 force layout
                const d3ForceLayout = graph.d3ForceLayout && graph.d3ForceLayout();
                
                return {
                    hasD3ForceLayout: !!d3ForceLayout,
                    alpha: d3ForceLayout ? d3ForceLayout.alpha() : 'N/A',
                    nodes: d3ForceLayout ? d3ForceLayout.nodes().map(n => ({id: n.id, x: n.x, y: n.y, z: n.z})).slice(0, 2) : 'N/A'
                };
            })()
        """)
        print(f"Result: {result}")
        
        await asyncio.sleep(3)
        await browser.close()

asyncio.run(main())
