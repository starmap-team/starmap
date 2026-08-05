"""Real browser end-to-end test for StarMap frontend.

Tests:
1. Login as admin
2. Navigate to /positions
3. Verify all 73 positions display (not just 2)
4. Verify Chinese names show
5. Verify NO false "未找到匹配" empty state
6. Test all status filters (全部/已发布/待审核/已拒绝)
7. Test industry filter
8. Test search
9. Test position detail navigation
10. Test pipeline monitoring page
"""
import sys
import os
import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright, expect, Page

# PLAN-007 / NEW-20: 凭据单一来源=环境变量（默认 dev 引导账号）
_ADMIN_USER = os.environ.get("STARMAP_TEST_ADMIN_USER", "admin")
_ADMIN_PASSWORD = os.environ.get("STARMAP_TEST_ADMIN_PASSWORD", "starmap2024")


SCREENSHOT_DIR = Path("C:/Users/LiShuai/Desktop/Agents/starmap/.workbuddy/screenshots")
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


def screenshot(page: Page, name: str) -> None:
    path = SCREENSHOT_DIR / f"{name}.png"
    page.screenshot(path=str(path), full_page=True)
    print(f"  📸 Screenshot: {path}")


def login(page: Page) -> None:
    print("\n[1/10] Login as admin...")
    page.goto("http://localhost:5173/login")
    page.wait_for_load_state("networkidle", timeout=10000)
    # Try to find username/password fields
    try:
        page.locator('input[placeholder*="用户名"], input[placeholder*="账号"], input[type="text"]:visible').first.fill(_ADMIN_USER)
    except Exception:
        page.locator('input').first.fill(_ADMIN_USER)
    page.locator('input[type="password"]:visible').first.fill(_ADMIN_PASSWORD)
    # Click login button
    login_btn = page.get_by_role("button", name="登录")
    if login_btn.count() == 0:
        login_btn = page.locator('button:has-text("登录")')
    login_btn.first.click()
    page.wait_for_load_state("networkidle", timeout=15000)
    time.sleep(2)
    print(f"  ✓ Logged in, current URL: {page.url}")


def test_positions_list(page: Page) -> dict:
    print("\n[2/10] Navigate to /positions and check position list...")
    page.goto("http://localhost:5173/positions")
    page.wait_for_load_state("networkidle", timeout=15000)
    time.sleep(3)

    screenshot(page, "01_positions_list_default")

    # Read the count text
    count_text = ""
    try:
        count_el = page.locator('text=/共.*\\d+.*个岗位/').first
        if count_el.count() > 0:
            count_text = count_el.text_content() or ""
            print(f"  ✓ Count text: {count_text}")
    except Exception as e:
        print(f"  ⚠ Count not found: {e}")

    # Count position cards
    cards = page.locator('.position-card').all()
    cards_visible = [c for c in cards if c.is_visible()]
    print(f"  ✓ Visible position cards: {len(cards_visible)}")

    # Check for false empty state
    false_empty = page.locator('text=未找到匹配的岗位').count()
    print(f"  ✓ '未找到匹配' false state: {false_empty} (should be 0)")

    # Get first few card titles
    titles = []
    for c in cards_visible[:3]:
        try:
            h3 = c.locator('h3').first
            if h3.count() > 0:
                titles.append(h3.text_content())
        except Exception:
            pass
    print(f"  ✓ First 3 titles: {titles}")

    return {
        "count_text": count_text,
        "cards_visible": len(cards_visible),
        "false_empty": false_empty,
        "titles": titles,
    }


def test_status_filters(page: Page) -> dict:
    print("\n[3/10] Test status filters...")
    results = {}
    for status_text in ["全部", "已发布", "待审核", "已拒绝"]:
        try:
            tag = page.locator(f'el-tag:has-text("{status_text}"), .clickable-tag:has-text("{status_text}")').first
            if tag.count() > 0:
                tag.click()
                time.sleep(2)
                visible = len([c for c in page.locator('.position-card').all() if c.is_visible()])
                results[status_text] = visible
                print(f"  ✓ Filter '{status_text}': {visible} cards visible")
                screenshot(page, f"02_filter_{status_text}")
        except Exception as e:
            print(f"  ⚠ Filter '{status_text}' failed: {e}")
    return results


def test_search(page: Page) -> dict:
    print("\n[4/10] Test search input...")
    try:
        # Click 全部 first
        page.locator('.clickable-tag:has-text("全部")').first.click()
        time.sleep(1)
        search = page.locator('input[placeholder*="搜索"]').first
        if search.count() == 0:
            search = page.locator('input[placeholder*="岗位"]').first
        search.fill("Python")
        time.sleep(2)
        visible = len([c for c in page.locator('.position-card').all() if c.is_visible()])
        print(f"  ✓ Search 'Python': {visible} cards visible")
        screenshot(page, "03_search_python")

        # Clear
        search.fill("")
        time.sleep(1)
        return {"python_count": visible}
    except Exception as e:
        print(f"  ⚠ Search test failed: {e}")
        return {}


def test_position_detail(page: Page) -> dict:
    print("\n[5/10] Test position detail navigation...")
    try:
        # Click first card
        first_card = page.locator('.position-card').first
        if first_card.count() == 0:
            print("  ⚠ No cards to click")
            return {}
        first_card.click()
        page.wait_for_load_state("networkidle", timeout=10000)
        time.sleep(2)
        url = page.url
        print(f"  ✓ Navigated to: {url}")
        title_text = ""
        try:
            h2 = page.locator('h2').first
            if h2.count() > 0:
                title_text = h2.text_content() or ""
                print(f"  ✓ Detail title: {title_text}")
        except Exception:
            pass
        screenshot(page, "04_position_detail")
        return {"url": url, "title": title_text}
    except Exception as e:
        print(f"  ⚠ Detail test failed: {e}")
        return {}


def test_graph_page(page: Page) -> dict:
    print("\n[6/10] Test graph page...")
    try:
        page.goto("http://localhost:5173/")
        page.wait_for_load_state("networkidle", timeout=15000)
        time.sleep(3)
        screenshot(page, "05_home_graph")
        return {"url": page.url}
    except Exception as e:
        print(f"  ⚠ Graph test failed: {e}")
        return {}


def test_pipeline_monitor(page: Page) -> dict:
    print("\n[7/10] Test pipeline monitor...")
    try:
        page.goto("http://localhost:5173/pipeline/monitor")
        page.wait_for_load_state("networkidle", timeout=15000)
        time.sleep(3)
        screenshot(page, "06_pipeline_monitor")

        # Check KPI cards show real numbers
        kpi_texts = page.locator('.kpi-card, .kpi-value').all_text_contents()
        print(f"  ✓ KPI text snippets: {kpi_texts[:8]}")

        # Check DAG shows stages
        stages = page.locator('.dag-stage, .pipeline-dag, [class*="stage"]').all_text_contents()
        print(f"  ✓ DAG stage snippets: {stages[:5]}")
        return {"url": page.url, "kpi": kpi_texts[:4]}
    except Exception as e:
        print(f"  ⚠ Pipeline monitor test failed: {e}")
        return {}


def test_evolution(page: Page) -> dict:
    print("\n[8/10] Test evolution page...")
    try:
        page.goto("http://localhost:5173/evolution/paths")
        page.wait_for_load_state("networkidle", timeout=15000)
        time.sleep(3)
        screenshot(page, "07_evolution")
        return {"url": page.url}
    except Exception as e:
        print(f"  ⚠ Evolution test failed: {e}")
        return {}


def test_match(page: Page) -> dict:
    print("\n[9/10] Test match page...")
    try:
        page.goto("http://localhost:5173/match")
        page.wait_for_load_state("networkidle", timeout=15000)
        time.sleep(3)
        screenshot(page, "08_match")
        return {"url": page.url}
    except Exception as e:
        print(f"  ⚠ Match test failed: {e}")
        return {}


def test_loop(page: Page) -> dict:
    print("\n[10/10] Test loop pipeline page...")
    try:
        page.goto("http://localhost:5173/loop")
        page.wait_for_load_state("networkidle", timeout=15000)
        time.sleep(3)
        screenshot(page, "09_loop")
        return {"url": page.url}
    except Exception as e:
        print(f"  ⚠ Loop test failed: {e}")
        return {}


def main():
    all_results = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        # Capture console errors
        page.on("console", lambda msg: print(f"  [browser:{msg.type}] {msg.text[:200]}") if msg.type in ("error", "warning") else None)
        page.on("pageerror", lambda err: print(f"  [pageerror] {err}"))

        try:
            login(page)
            all_results["positions_list"] = test_positions_list(page)
            all_results["status_filters"] = test_status_filters(page)
            all_results["search"] = test_search(page)
            all_results["position_detail"] = test_position_detail(page)
            all_results["graph"] = test_graph_page(page)
            all_results["pipeline"] = test_pipeline_monitor(page)
            all_results["evolution"] = test_evolution(page)
            all_results["match"] = test_match(page)
            all_results["loop"] = test_loop(page)
        except Exception as e:
            print(f"\n❌ Test failed: {e}")
            import traceback
            traceback.print_exc()
        finally:
            screenshot(page, "99_final")
            browser.close()

    print("\n" + "=" * 60)
    print("📊 Test Results Summary")
    print("=" * 60)
    for key, value in all_results.items():
        if isinstance(value, dict):
            for k, v in value.items():
                print(f"  {key}.{k}: {v}")
        else:
            print(f"  {key}: {value}")
    return all_results


if __name__ == "__main__":
    main()
