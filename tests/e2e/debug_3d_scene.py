"""Debug: Check Three.js scene contents"""
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
        
        # Check Three.js scene
        result = await page.evaluate("""
            (function() {
                // Find the Three.js renderer
                const canvas = document.querySelector('canvas[data-engine="three.js r185"]');
                if (!canvas) return 'No canvas found';
                
                // Try to find the renderer by looking at Three.js internals
                // The renderer is typically stored in the scene container
                const container = canvas.parentElement;
                
                // Check if we can access the scene through the canvas
                // Three.js stores the renderer in a closure, but we can try to find it
                
                // Alternative: check if there are any objects in the scene
                // by looking at the WebGL context
                const gl = canvas.getContext('webgl2') || canvas.getContext('webgl');
                if (!gl) return 'No WebGL context';
                
                // Get WebGL parameters
                const params = {
                    viewport: gl.getParameter(gl.VIEWPORT),
                    clearColor: [
                        gl.getParameter(gl.COLOR_CLEAR_VALUE)[0],
                        gl.getParameter(gl.COLOR_CLEAR_VALUE)[1],
                        gl.getParameter(gl.COLOR_CLEAR_VALUE)[2],
                        gl.getParameter(gl.COLOR_CLEAR_VALUE)[3]
                    ],
                    depthTest: gl.getParameter(gl.DEPTH_TEST),
                    blend: gl.getParameter(gl.BLEND),
                    cullFace: gl.getParameter(gl.CULL_FACE)
                };
                
                return {
                    webglParams: params,
                    canvasSize: {width: canvas.width, height: canvas.height}
                };
            })()
        """)
        print(f"Result: {result}")
        
        await asyncio.sleep(3)
        await browser.close()

asyncio.run(main())
