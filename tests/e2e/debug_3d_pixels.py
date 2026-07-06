"""Debug: Check pixel data in WebGL canvas"""
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
        
        # Check pixel data
        result = await page.evaluate("""
            (function() {
                const canvas = document.querySelector('canvas[data-engine="three.js r185"]');
                if (!canvas) return 'No Three.js canvas found';
                
                const gl = canvas.getContext('webgl2') || canvas.getContext('webgl');
                if (!gl) return 'No WebGL context';
                
                // Read pixels from center of canvas
                const pixels = new Uint8Array(4);
                gl.readPixels(Math.floor(canvas.width/2), Math.floor(canvas.height/2), 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, pixels);
                
                // Also check a few more points
                const points = [
                    [0.5, 0.5],  // center
                    [0.3, 0.3],  // top-left-ish
                    [0.7, 0.7],  // bottom-right-ish
                    [0.5, 0.2],  // top-center
                ];
                
                const results = points.map(([x, y]) => {
                    const px = new Uint8Array(4);
                    const cx = Math.floor(canvas.width * x);
                    const cy = Math.floor(canvas.height * y);
                    gl.readPixels(cx, cy, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, px);
                    return {x: cx, y: cy, r: px[0], g: px[1], b: px[2], a: px[3]};
                });
                
                return {
                    canvasSize: {width: canvas.width, height: canvas.height},
                    centerPixel: {r: pixels[0], g: pixels[1], b: pixels[2], a: pixels[3]},
                    samplePixels: results
                };
            })()
        """)
        print(f"Result: {result}")
        
        await asyncio.sleep(3)
        await browser.close()

asyncio.run(main())
