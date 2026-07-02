# -*- coding: utf-8 -*-
from playwright.sync_api import sync_playwright
import os
import time

BASE_URL = "http://localhost:5173"
SCREENSHOT_DIR = "test-screenshots"

PAGES = [
    {
        "name": "home",
        "path": "/",
        "wait_selector": "canvas",
        "data_checks": {"keywords": ["node", "edge", "2750", "5299"], "min_chars": 100},
    },
    {
        "name": "dashboard",
        "path": "/dashboard",
        "wait_selector": "canvas, svg, .chart, [class*=chart]",
        "data_checks": {"keywords": ["2750", "5299"], "min_chars": 100},
    },
    {
        "name": "positions",
        "path": "/positions",
        "wait_selector": "table, [class*=list], [class*=card], [class*=position]",
        "data_checks": {"keywords": ["position", "skill"], "min_chars": 50},
    },
    {
        "name": "match",
        "path": "/match",
        "wait_selector": "form, input, select, [class*=form], [class*=match]",
        "data_checks": {"keywords": ["match", "skill"], "min_chars": 50},
    },
    {
        "name": "extract",
        "path": "/extract",
        "wait_selector": "form, textarea, input, [class*=extract]",
        "data_checks": {"keywords": ["JD", "extract"], "min_chars": 50},
    },
    {
        "name": "evolution",
        "path": "/evolution",
        "wait_selector": "canvas, svg, .chart, [class*=chart], [class*=dashboard]",
        "data_checks": {"keywords": ["evolution"], "min_chars": 100},
    },
    {
        "name": "quality",
        "path": "/quality",
        "wait_selector": "canvas, svg, .chart, [class*=chart], [class*=dashboard]",
        "data_checks": {"keywords": ["quality"], "min_chars": 50},
    },
    {
        "name": "pipeline",
        "path": "/pipeline",
        "wait_selector": "[class*=pipeline], [class*=monitor], table, .card",
        "data_checks": {"keywords": ["pipeline"], "min_chars": 50},
    },
    {
        "name": "datasources",
        "path": "/datasources",
        "wait_selector": "[class*=source], [class*=platform], table, .card, li",
        "data_checks": {"keywords": ["platform", "source"], "min_chars": 50},
    },
    {
        "name": "admin",
        "path": "/admin",
        "wait_selector": ".card, [class*=stat], table, [class*=admin]",
        "data_checks": {"keywords": ["admin", "stat"], "min_chars": 50},
    },
    {
        "name": "loop-demo",
        "path": "/loop",
        "wait_selector": "[class*=loop], [class*=demo], .card, main, [class*=step]",
        "data_checks": {"keywords": ["loop", "demo"], "min_chars": 30},
    },
]


def test_page(page, page_info, screenshot_dir):
    name = page_info["name"]
    url = f'{BASE_URL}{page_info["path"]}'
    result = {
        "name": name,
        "path": page_info["path"],
        "url": url,
        "status": "FAIL",
        "errors": [],
        "console_errors": [],
        "checks": [],
    }

    try:
        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        print(f'\n{"=" * 60}')
        print(f"Testing: {name} ({url})")
        print(f'{"=" * 60}')

        response = page.goto(url, wait_until="domcontentloaded", timeout=15000)
        if response and response.status >= 400:
            result["errors"].append(f"HTTP {response.status}")
            print(f"  X HTTP Error: {response.status}")
            return result

        wait_sel = page_info["wait_selector"]
        found_element = False
        try:
            page.wait_for_selector(wait_sel, timeout=20000, state="visible")
            print(f"  [OK] Found element: {wait_sel}")
            found_element = True
        except Exception:
            print(f"  [WARN] Could not find: {wait_sel} (continuing...)")

        time.sleep(2)

        body_text = page.inner_text("body")
        char_count = len(body_text.strip())
        min_chars = page_info["data_checks"]["min_chars"]

        if char_count < min_chars:
            result["errors"].append(f"Page appears blank or minimal content ({char_count} chars, need {min_chars})")
            print(f"  X Minimal content: {char_count} chars")
        else:
            print(f"  [OK] Content: {char_count} chars")

        dc = page_info["data_checks"]
        matched_keywords = [kw for kw in dc["keywords"] if kw.lower() in body_text.lower()]
        if matched_keywords:
            result["checks"].append(f"Keywords found: {', '.join(matched_keywords)}")
            print(f"  [OK] Data keywords: {', '.join(matched_keywords)}")
        else:
            print(f"  [WARN] None of keywords {dc['keywords']} found")

        if name == "home":
            canvas_count = page.locator("canvas").count()
            result["checks"].append(f"Canvas elements: {canvas_count}")
            print(f"  [INFO] Canvas elements: {canvas_count}")
        elif name == "dashboard":
            chart_els = page.locator("svg, canvas, .chart, [class*=chart]").count()
            result["checks"].append(f"Chart elements: {chart_els}")
            print(f"  [INFO] Chart elements: {chart_els}")
        elif name == "datasources":
            if "10" in body_text or "platform" in body_text.lower():
                result["checks"].append("Platform count data present")
                print(f"  [OK] Platform data present")

        screenshot_path = os.path.join(screenshot_dir, f"{name}.png")
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"  [OK] Screenshot: {screenshot_path}")
        result["screenshot"] = screenshot_path

        result["console_errors"] = console_errors[:10]
        if console_errors:
            print(f"  [WARN] Console errors: {len(console_errors)}")
            for err in console_errors[:3]:
                print(f"    - {err[:120]}")

        if not result["errors"] and char_count >= min_chars:
            result["status"] = "PASS"
            print(f"  >>> PASS")
        else:
            print(f"  >>> FAIL")

    except Exception as e:
        result["errors"].append(str(e)[:300])
        print(f"  X Exception: {str(e)[:200]}")
        try:
            err_path = os.path.join(screenshot_dir, f"{name}_error.png")
            page.screenshot(path=err_path, full_page=True)
            result["screenshot"] = err_path
        except Exception:
            pass

    return result


def main():
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)

    print(f'\n{"=" * 60}')
    print("STARMAP FRONTEND E2E TEST SUITE")
    print(f"Base URL: {BASE_URL}")
    print(f"Screenshots: {os.path.abspath(SCREENSHOT_DIR)}")
    print(f'{"=" * 60}')

    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            ignore_https_errors=True,
        )
        page = context.new_page()

        for page_info in PAGES:
            result = test_page(page, page_info, SCREENSHOT_DIR)
            results.append(result)

        browser.close()

    print(f'\n{"=" * 60}')
    print("TEST RESULTS SUMMARY")
    print(f'{"=" * 60}')

    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")

    print(f"\nTotal: {len(results)} | Passed: {passed} | Failed: {failed}")
    print(f"Pass Rate: {passed / len(results) * 100:.1f}%\n")

    print(f'{"Page":<15} {"Status":<8} {"Checks"}')
    print("-" * 70)

    for r in results:
        checks_str = "; ".join(r["checks"][:2]) if r["checks"] else "basic load"
        cerr = f' ({len(r["console_errors"])} console err)' if r["console_errors"] else ""
        marker = "PASS" if r["status"] == "PASS" else "FAIL"
        print(f'{r["name"]:<15} {marker:<8} {checks_str}{cerr}')

    failures = [r for r in results if r["status"] == "FAIL"]
    if failures:
        print(f'\n{"=" * 60}')
        print("FAILURE DETAILS")
        print(f'{"=" * 60}')
        for r in failures:
            print(f'\n  {r["name"]} ({r["url"]})')
            for err in r["errors"]:
                print(f"    - {err}")

    all_console = [(r["name"], r["console_errors"]) for r in results if r["console_errors"]]
    if all_console:
        print(f'\n{"=" * 60}')
        print("CONSOLE ERRORS SUMMARY")
        print(f'{"=" * 60}')
        for name, errors in all_console:
            print(f'\n  {name}: {len(errors)} errors')
            for err in errors[:2]:
                print(f"    - {err[:150]}")

    print(f'\nScreenshots: {os.path.abspath(SCREENSHOT_DIR)}')
    print(f'{"=" * 60}')

    return passed == len(results)


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
