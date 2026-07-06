#!/usr/bin/env python3
"""Quick debug: Find the correct selector for el-radio-button."""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
    page = ctx.new_page()

    page.goto("http://localhost:5173", wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(5000)

    # Check what the radio group looks like
    html = page.evaluate("""() => {
        const group = document.querySelector('.view-tabs');
        return group ? group.outerHTML : 'NOT FOUND';
    }""")
    print("Radio group HTML:")
    # Print first 500 chars
    print(html[:500])
    print("...")

    # Try different selectors
    selectors = [
        '.el-radio-button[value="domain"]',
        '.el-radio-button',
        '.view-tabs .el-radio-button',
        '.el-radio-button__inner',
        'label.el-radio-button',
    ]
    for sel in selectors:
        count = len(page.query_selector_all(sel))
        print(f"  Selector '{sel}': {count} matches")

    # Try locator-based approach
    locators = [
        page.locator('.view-tabs').get_by_text("领域"),
        page.locator('.view-tabs').locator('text=领域'),
        page.locator('.el-radio-button').first,
        page.get_by_role("radio", name="领域"),
        page.locator('[role="radio"]'),
    ]
    for loc in locators:
        try:
            count = loc.count()
            print(f"  Locator: {count} matches, text='{loc.first.text_content()}'")
        except Exception as e:
            print(f"  Locator error: {e}")

    browser.close()
