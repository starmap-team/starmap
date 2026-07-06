"""Debug: Check node positions after simulation"""
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(viewport={'width': 1280, 'height': 720})
        page = await context.new_page()
        
        # Listen for console messages
        console_logs = []
        page.on("console", lambda msg: console_logs.append(msg.text))
        
        await page.goto("http://localhost:5177/")
        await page.wait_for_timeout(3000)
        
        # Click 3D button
        await page.click("button:has-text('3D')")
        await page.wait_for_timeout(10000)  # Wait longer for simulation
        
        # Execute script to check node positions
        result = await page.evaluate("""
            (function() {
                // Try to find the graph instance
                const container = document.querySelector('.graph3d-container');
                if (!container) return 'No graph3d-container found';
                
                // The graph instance might be stored on the container or accessible via window
                // Let's check if we can find any global graph instance
                for (const key in window) {
                    if (key.toLowerCase().includes('graph')) {
                        const val = window[key];
                        if (val && typeof val === 'object' && val.graphData) {
                            const data = val.graphData();
                            return {
                                found: key,
                                nodeCount: data.nodes.length,
                                nodes: data.nodes.slice(0, 3).map(n => ({
                                    id: n.id,
                                    x: n.x,
                                    y: n.y,
                                    z: n.z
                                }))
                            };
                        }
                    }
                }
                
                // Check if the container has any data
                return {
                    containerChildren: container.children.length,
                    containerHTML: container.innerHTML.substring(0, 500)
                };
            })()
        """)
        print(f"Result: {result}")
        
        # Print console logs
        print("\n=== Console Logs ===")
        for log in console_logs:
            if 'Graph3D' in log or 'nodeThreeObject' in log:
                print(log)
        
        await asyncio.sleep(3)
        await browser.close()

asyncio.run(main())
