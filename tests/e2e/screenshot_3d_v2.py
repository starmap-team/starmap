#!/usr/bin/env python3
"""Take a screenshot of the 3D graph with longer wait for layout convergence."""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
    page = ctx.new_page()

    page.goto("http://localhost:5173", wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(8000)

    # Take screenshot of default (domain) view
    page.screenshot(path="tests/e2e/screenshot_3d_v2_domain.png", full_page=False)
    print("Saved: domain")

    # Switch to tech_stack mode
    btn = page.locator(".view-tabs").get_by_text("技术栈", exact=True)
    if btn.count() > 0:
        btn.click()
    page.wait_for_timeout(12000)  # longer wait for force simulation
    page.screenshot(path="tests/e2e/screenshot_3d_v2_techstack.png", full_page=False)
    print("Saved: techstack")

    # Switch to level mode
    btn = page.locator(".view-tabs").get_by_text("级别", exact=True)
    if btn.count() > 0:
        btn.click()
    page.wait_for_timeout(8000)
    page.screenshot(path="tests/e2e/screenshot_3d_v2_level.png", full_page=False)
    print("Saved: level")

    browser.close()
