"""Debug: Access Vue component directly"""
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
        
        # Inject script to access Vue internals
        result = await page.evaluate("""
            (function() {
                // Find Vue app instance
                const app = document.querySelector('#app');
                if (!app) return 'No #app found';
                
                // Try to access Vue component tree
                // Vue 3 stores component instance on elements
                const graphContainer = document.querySelector('.graph3d-container');
                if (!graphContainer) return 'No graph container';
                
                // Look for Vue component instance
                let vueInstance = null;
                for (const key in graphContainer) {
                    if (key.startsWith('__vue')) {
                        vueInstance = graphContainer[key];
                        break;
                    }
                }
                
                if (!vueInstance) {
                    // Try parent elements
                    let parent = graphContainer.parentElement;
                    while (parent) {
                        for (const key in parent) {
                            if (key.startsWith('__vue')) {
                                vueInstance = parent[key];
                                break;
                            }
                        }
                        if (vueInstance) break;
                        parent = parent.parentElement;
                    }
                }
                
                if (!vueInstance) {
                    // Try to find any Vue component with graphInstance
                    const allElements = document.querySelectorAll('*');
                    for (const el of allElements) {
                        for (const key in el) {
                            if (key.startsWith('__vue')) {
                                const instance = el[key];
                                if (instance && instance.graphInstance) {
                                    vueInstance = instance;
                                    break;
                                }
                            }
                        }
                        if (vueInstance) break;
                    }
                }
                
                if (!vueInstance) return 'No Vue instance found';
                
                // Access graph instance
                const graph = vueInstance.graphInstance;
                if (!graph) return 'No graph instance in Vue component';
                
                const data = graph.graphData();
                const camera = graph.camera();
                
                return {
                    nodeCount: data.nodes.length,
                    nodes: data.nodes.slice(0, 3).map(n => ({
                        id: n.id,
                        x: n.x,
                        y: n.y,
                        z: n.z
                    })),
                    cameraPosition: camera ? {
                        x: camera.position.x,
                        y: camera.position.y,
                        z: camera.position.z
                    } : 'No camera'
                };
            })()
        """)
        print(f"Result: {result}")
        
        await asyncio.sleep(3)
        await browser.close()

asyncio.run(main())
