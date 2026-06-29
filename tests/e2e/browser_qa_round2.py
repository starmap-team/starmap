"""StarMap Browser QA - Full 8-page smoke + interaction test"""
import json, time, os
from playwright.sync_api import sync_playwright

BASE = "http://localhost:5173"
OUT = "screenshots/qa_round2"
os.makedirs(OUT, exist_ok=True)

results = []
console_errors = []
network_errors = []

def collect_console(msg):
    if msg.type in ("error", "warning"):
        entry = {"type": msg.type, "text": msg.text[:300], "url": msg.location.get("url","")}
        console_errors.append(entry)

def collect_response(resp):
    if resp.status >= 400:
        network_errors.append({"url": resp.url[:200], "status": resp.status})

pages = [
    {"name": "home", "path": "/", "wait": 3000},
    {"name": "positions", "path": "/positions", "wait": 2000},
    {"name": "extract", "path": "/extract", "wait": 2000},
    {"name": "match", "path": "/match", "wait": 2000},
    {"name": "evolution", "path": "/evolution", "wait": 2000},
    {"name": "quality", "path": "/quality", "wait": 2000},
    {"name": "admin", "path": "/admin", "wait": 2000},
]

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    page.on("console", collect_console)
    page.on("response", collect_response)

    for pg in pages:
        name = pg["name"]
        url = f"{BASE}{pg['path']}"
        print(f"\n{'='*60}")
        print(f"Testing: {name} -> {url}")
        try:
            page.goto(url, wait_until="networkidle", timeout=15000)
            time.sleep(pg["wait"] / 1000)
            
            # Screenshot
            shot = f"{OUT}/{name}.png"
            page.screenshot(path=shot, full_page=True)
            print(f"  Screenshot: {shot}")
            
            # Page title
            title = page.title()
            print(f"  Title: {title}")
            
            # Check for visible content
            body_text = page.inner_text("body")[:500]
            has_content = len(body_text.strip()) > 50
            
            # Check for error states
            error_elements = page.locator(".el-alert--error, .error, [class*='error']").count()
            
            # Check for loading states stuck
            loading = page.locator(".el-loading-mask, .el-skeleton, [class*='loading']").count()
            
            result = {
                "page": name,
                "url": url,
                "title": title,
                "has_content": has_content,
                "error_elements": error_elements,
                "loading_elements": loading,
                "body_preview": body_text[:200].replace("\n", " "),
                "status": "OK" if has_content and error_elements == 0 else "ISSUE"
            }
            results.append(result)
            print(f"  Content: {'YES' if has_content else 'NO'} | Errors: {error_elements} | Loading: {loading}")
            print(f"  Status: {result['status']}")
            
        except Exception as e:
            print(f"  ERROR: {e}")
            results.append({"page": name, "url": url, "status": "FAIL", "error": str(e)[:200]})

    # Save results
    report = {
        "results": results,
        "console_errors": console_errors[:50],
        "network_errors": network_errors[:50],
    }
    with open(f"{OUT}/qa_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    browser.close()

print(f"\n{'='*60}")
print(f"SUMMARY: {len([r for r in results if r['status']=='OK'])}/{len(results)} pages OK")
print(f"Console errors: {len(console_errors)}")
print(f"Network errors: {len(network_errors)}")
if console_errors:
    print("\nTop console errors:")
    for e in console_errors[:10]:
        print(f"  [{e['type']}] {e['text'][:100]}")
if network_errors:
    print("\nTop network errors:")
    for e in network_errors[:10]:
        print(f"  [{e['status']}] {e['url'][:100]}")
