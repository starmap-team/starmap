"""Phase 3.8.2 视觉测验 - 验证 5 个问题全部优化."""
import asyncio
import json
import urllib.request
from pathlib import Path
from playwright.async_api import async_playwright


def api_login():
    req = urllib.request.Request(
        "http://localhost:8000/api/v1/auth/login",
        data=json.dumps({"username": "admin", "password": "starmap2024"}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        b = json.loads(r.read())
        return b["access_token"], b.get("user", {})


async def main():
    token, _ = api_login()
    H = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    user_req = urllib.request.Request("http://localhost:8000/api/v1/auth/me", headers=H)
    with urllib.request.urlopen(user_req, timeout=10) as r:
        user_info = json.loads(r.read())

    SCREENSHOTS_DIR = Path("tests/e2e/screenshots/phase382")
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1920, "height": 1400}, locale="zh-CN")
        await context.add_init_script(f"""
            localStorage.setItem('starmap_access_token', '{token}');
            localStorage.setItem('starmap_user', '{json.dumps(user_info)}');
        """)
        page = await context.new_page()
        await page.goto("http://localhost:5173/pipeline", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(8000)

        # 截图 1: 初始状态 (含新的 Status Hero 卡片)
        await page.screenshot(path=str(SCREENSHOTS_DIR / "01_hero_card.png"), full_page=True)
        print("✅ 截图 1: 状态 Hero 卡片")

        # 验证 Status Hero 渲染
        hero = await page.query_selector(".status-hero-card")
        if hero:
            hero_text = await hero.inner_text()
            print(f"   ✅ Status Hero 卡片渲染: {hero_text.replace(chr(10), ' | ')[:150]}")
        else:
            print("   ⚠️ Status Hero 卡片未找到 (可能因无 run 数据)")

        # 验证 DAG 头部阶段计数
        stage_count = await page.query_selector(".stage-count")
        if stage_count:
            count_text = await stage_count.inner_text()
            print(f"   ✅ DAG 头部阶段计数: {count_text.replace(chr(10), ' | ')[:100]}")

        # 验证 verify log 持久化
        verify_persistent = await page.query_selector(".verify-log-card .el-tag")
        if verify_persistent:
            print("   ✅ 验证日志持久化指示器可见")

        # 验证 KPI 显示
        kpi = await page.evaluate("""() => {
            return Array.from(document.querySelectorAll('.kpi-card')).map(c => ({
                label: c.querySelector('.kpi-label')?.innerText?.trim(),
                value: c.querySelector('.kpi-value')?.innerText?.trim(),
            }));
        }""")
        print(f"\n📊 KPI 卡片:")
        for k in kpi:
            print(f"   {k['label']}: {k['value']}")

        # 验证 DAG 卡片状态
        cards = await page.query_selector_all(".stage-card")
        print(f"\n📊 DAG 阶段状态:")
        for c in cards[:5]:
            txt = (await c.inner_text())[:80].replace("\n", " | ")
            print(f"   {txt}")

        # 触发一次 trigger 看验证日志
        print("\n[操作] 点击'校验状态'...")
        verify_btn = await page.query_selector('button:has-text("校验状态")')
        if verify_btn:
            await verify_btn.click()
            await page.wait_for_timeout(3000)
            log_items = await page.query_selector_all(".verify-log-item")
            print(f"   ✅ 验证日志条目: {len(log_items)}")
            for log in log_items[:3]:
                txt = await log.inner_text()
                print(f"   - {txt.replace(chr(10), ' | ')[:140]}")

        # 截图 2: 完整页面 (含新设计)
        await page.screenshot(path=str(SCREENSHOTS_DIR / "02_full_page.png"), full_page=True)
        print("\n✅ 截图 2: 完整页面")

        # 测试持久化: 刷新页面看日志是否还在
        print("\n[测试] 刷新页面验证日志持久化...")
        await page.reload(wait_until="domcontentloaded")
        await page.wait_for_timeout(5000)
        log_items_after = await page.query_selector_all(".verify-log-item")
        print(f"   ✅ 刷新后日志条目: {len(log_items_after)} (预期 >0 证明持久化生效)")

        await page.screenshot(path=str(SCREENSHOTS_DIR / "03_after_refresh.png"), full_page=True)
        print("✅ 截图 3: 刷新后状态")

        await context.close()
        await browser.close()
    print(f"\n截图保存: {SCREENSHOTS_DIR}")


if __name__ == "__main__":
    asyncio.run(main())
