import os, sys, json, time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from playwright.sync_api import sync_playwright

SCREENSHOT_DIR = r"C:\Users\LiShuai\Desktop\Agents\starmap\test-screenshots"
os.makedirs(SCREENSHOT_DIR, exist_ok=True)
BASE = "http://localhost:5173"

results = []

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(viewport={"width": 1920, "height": 1080})
    page = context.new_page()
    
    console_errors = []
    page.on("console", lambda msg: console_errors.append(f"[{msg.type}] {msg.text}") if msg.type in ("error", "warning") else None)

    # Test LoopDemo at correct /loop path
    name = "loopdemo_fixed"
    path = "/loop"
    url = f"{BASE}{path}"
    print(f"\n=== Testing {name}: {url} ===")
    try:
        console_errors.clear()
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(3)  # wait for Vue to mount
        
        # Check body content
        body_text = page.evaluate("document.body.innerText")
        body_len = len(body_text.strip())
        print(f"  Body text length: {body_len}")
        
        # Check for specific elements
        has_content = body_len > 50
        
        # Take screenshot
        ss_path = os.path.join(SCREENSHOT_DIR, f"{name}.png")
        page.screenshot(path=ss_path, full_page=True)
        print(f"  Screenshot: {ss_path}")
        
        # Check console errors
        if console_errors:
            print(f"  Console errors: {len(console_errors)}")
            for e in console_errors[:5]:
                print(f"    {e}")
        
        status = "PASS" if has_content else "FAIL"
        print(f"  Result: {status}")
        
        results.append({
            "name": name,
            "path": path,
            "status": status,
            "body_length": body_len,
            "console_errors": len(console_errors),
            "screenshot": ss_path,
        })
        
    except Exception as e:
        print(f"  ERROR: {e}")
        results.append({"name": name, "path": path, "status": "FAIL", "error": str(e)})
    
    browser.close()

# Save results
results_path = os.path.join(SCREENSHOT_DIR, "loopdemo_retest.json")
with open(results_path, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print(f"\nResults saved to {results_path}")
