"""Debug: Take screenshot of 3D graph"""
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
        await page.wait_for_timeout(5000)
        
        # Take screenshot
        await page.screenshot(path="C:/Users/LiShuai/Desktop/Agents/starmap/tests/e2e/3d_visual.png", full_page=False)
        print("Screenshot saved to 3d_visual.png")
        
        # Check if canvas has any content
        canvas_data = await page.evaluate("""
            const canvas = document.querySelector('canvas');
            if (!canvas) return 'No canvas found';
            const ctx = canvas.getContext('webgl') || canvas.getContext('webgl2');
            if (!ctx) return 'No WebGL context';
            return {
                width: canvas.width,
                height: canvas.height,
                clientWidth: canvas.clientWidth,
                clientHeight: canvas.clientHeight
            };
        """)
        print(f"Canvas info: {canvas_data}")
        
        await asyncio.sleep(3)
        await browser.close()

asyncio.run(main())
