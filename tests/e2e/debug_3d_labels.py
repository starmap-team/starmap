"""Debug: Check what labels nodes have in 3D graph"""
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(viewport={'width': 1280, 'height': 720})
        page = await context.new_page()
        
        # Enable console logging
        page.on("console", lambda msg: print(f"[Console] {msg.type}: {msg.text}"))
        
        await page.goto("http://localhost:5177/")
        await page.wait_for_timeout(3000)
        
        # Click 3D button
        await page.click("button:has-text('3D')")
        await page.wait_for_timeout(3000)
        
        # Check node labels via JS
        labels = await page.evaluate("""
            // Access the graph instance if available
            const graph = document.querySelector('#graph-3d-container')?.__graph;
            if (graph) {
                const data = graph.graphData();
                return data.nodes.map(n => ({id: n.id, labels: n.labels, name: n.properties?.name})).slice(0, 5);
            }
            return 'No graph found';
        """)
        print(f"Node labels: {labels}")
        
        await asyncio.sleep(5)
        await browser.close()

asyncio.run(main())
