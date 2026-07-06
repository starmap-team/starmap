"""Debug: Check camera position and node positions"""
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
        
        # Inject a script to access the graph instance
        result = await page.evaluate("""
            (function() {
                // Try to find the graph instance by looking for the ForceGraph3D instance
                // It's typically stored in a closure or on the container
                
                // Look for any object that has graphData method
                const candidates = [];
                for (const key in window) {
                    try {
                        const val = window[key];
                        if (val && typeof val === 'object' && val.graphData) {
                            candidates.push(key);
                        }
                    } catch (e) {}
                }
                
                // Try to access the graph through Vue component
                // The Graph3D component stores the graph in graphInstance ref
                const graphContainer = document.querySelector('.graph3d-container');
                
                return {
                    windowCandidates: candidates,
                    containerFound: !!graphContainer,
                    containerHTML: graphContainer ? graphContainer.innerHTML.substring(0, 200) : 'No container'
                };
            })()
        """)
        print(f"Result: {result}")
        
        await asyncio.sleep(3)
        await browser.close()

asyncio.run(main())
