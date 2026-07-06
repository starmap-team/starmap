"""Debug: Access graph instance via Vue component"""
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
        
        # Access the graph instance via Vue devtools or global
        result = await page.evaluate("""
            (function() {
                // Try to find Vue app and access component
                const container = document.querySelector('.graph3d-container');
                if (!container) return 'No container';
                
                // Check for Vue instance
                const vueEl = container.querySelector('[data-v-app]') || container;
                const vueInstance = vueEl.__vueParentComponent || vueEl.__vue_app__;
                
                // Try to access the graph instance from the component
                // The graph instance is stored in graphInstance ref
                // Let's try to find it in the Vue component tree
                
                // Alternative: check if there's a global graph instance
                for (const key in window) {
                    try {
                        const val = window[key];
                        if (val && typeof val === 'object') {
                            // Check if it has graphData method
                            if (typeof val.graphData === 'function') {
                                const data = val.graphData();
                                if (data && data.nodes) {
                                    return {
                                        found: key,
                                        nodeCount: data.nodes.length,
                                        nodes: data.nodes.slice(0, 3).map(n => ({
                                            id: n.id,
                                            x: n.x,
                                            y: n.y,
                                            z: n.z,
                                            vx: n.vx,
                                            vy: n.vy,
                                            vz: n.vz
                                        }))
                                    };
                                }
                            }
                        }
                    } catch (e) {}
                }
                
                return 'No graph instance found';
            })()
        """)
        print(f"Result: {result}")
        
        await asyncio.sleep(3)
        await browser.close()

asyncio.run(main())
