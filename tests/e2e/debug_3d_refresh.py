#!/usr/bin/env python3
"""Debug: Force refresh and check logs."""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
    page = ctx.new_page()

    console_messages = []
    def on_console(msg):
        console_messages.append({"type": msg.type, "text": msg.text[:200]})
    page.on("console", on_console)

    # Clear cache and reload
    page.goto("http://localhost:5173?nocache=" + str(__import__('time').time()), wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(10000)

    print(f"All console messages ({len(console_messages)}):")
    for msg in console_messages:
        print(f"  [{msg['type']}] {msg['text']}")

    browser.close()
