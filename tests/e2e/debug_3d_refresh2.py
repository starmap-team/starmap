#!/usr/bin/env python3
"""Debug: Force refresh browser cache."""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
    page = ctx.new_page()

    # Clear browser cache
    ctx.clear_cookies()

    page.goto("http://localhost:5173", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(5000)

    # Force reload
    page.reload(wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(10000)

    # Check console messages
    console_messages = []
    def on_console(msg):
        console_messages.append({"type": msg.type, "text": msg.text[:200]})
    page.on("console", on_console)

    # Trigger a new page load to capture console messages
    page.goto("http://localhost:5173?nocache=" + str(__import__('time').time()), wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(10000)

    print(f"Console messages ({len(console_messages)}):")
    for msg in console_messages:
        print(f"  [{msg['type']}] {msg['text']}")

    browser.close()
