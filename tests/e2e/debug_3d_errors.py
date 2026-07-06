#!/usr/bin/env python3
"""Debug: Check console errors after window.THREE fix."""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
    page = ctx.new_page()

    console_messages = []
    def on_console(msg):
        console_messages.append({"type": msg.type, "text": msg.text})
    page.on("console", on_console)

    page.goto("http://localhost:5173", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(10000)

    # Switch to tech_stack mode
    btn = page.locator('.view-tabs').get_by_text("技术栈", exact=True)
    if btn.count() > 0:
        btn.click()
    page.wait_for_timeout(5000)

    # Switch to level mode
    btn = page.locator('.view-tabs').get_by_text("级别", exact=True)
    if btn.count() > 0:
        btn.click()
    page.wait_for_timeout(5000)

    print(f"Console messages ({len(console_messages)}):")
    for msg in console_messages:
        if msg['type'] == 'error':
            print(f"  [ERROR] {msg['text'][:200]}")

    browser.close()
