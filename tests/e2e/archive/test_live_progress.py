"""截图测试: 验证 PipelineLiveProgress 面板正确渲染."""
import asyncio
import json

from e2e_creds import login_payload
import urllib.request
from playwright.async_api import async_playwright


def api_login():
    req = urllib.request.Request(
        "http://localhost:8000/api/v1/auth/login",
        data=json.dumps(login_payload()).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        b = json.loads(r.read())
        return b["access_token"], b.get("user", {})


async def main():
    token, _ = api_login()
    user_req = urllib.request.Request("http://localhost:8000/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(user_req, timeout=10) as r:
        user_info = json.loads(r.read())

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1920, "height": 1200}, locale="zh-CN")
        await context.add_init_script(f"""
            localStorage.setItem('starmap_access_token', '{token}');
            localStorage.setItem('starmap_user', '{json.dumps(user_info)}');
        """)
        page = await context.new_page()
        await page.goto("http://localhost:5173/pipeline", wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(8000)

        # 截图1: 整体页面 (含新的实时面板)
        await page.screenshot(path="tests/e2e/screenshots/pipeline_live_progress.png", full_page=True)
        print("✅ 截图 1: 完整页面 (含实时面板) - pipeline_live_progress.png")

        # 检查新面板是否出现
        live_panel = await page.query_selector("text=实时数据流")
        if live_panel:
            print("✅ 新实时进度面板已渲染")
        else:
            print("❌ 实时数据流面板未找到")

        # 检查数据流可视化
        flow_steps = await page.query_selector_all(".flow-step")
        print(f"   数据流步骤数: {len(flow_steps)} (期望: 5)")

        # 检查阶段卡片
        live_cards = await page.query_selector_all(".stage-card-live")
        print(f"   实时阶段卡片数: {len(live_cards)} (期望: 5-6)")

        # 滚动到实时面板截图
        await page.evaluate("""() => {
            const el = document.querySelector('.live-progress-card');
            if (el) el.scrollIntoView({ behavior: 'smooth' });
        }""")
        await page.wait_for_timeout(1000)
        await page.screenshot(path="tests/e2e/screenshots/pipeline_live_panel_zoom.png", clip={"x": 0, "y": 0, "width": 1920, "height": 1200})
        print("✅ 截图 2: 实时面板 - pipeline_live_panel_zoom.png")

        # 检查 KPI 是否显示真实数据 (确认 429 限流修复有效)
        kpi = await page.evaluate("""() => {
            return Array.from(document.querySelectorAll('.kpi-card')).map(c => ({
                label: c.querySelector('.kpi-label')?.innerText?.trim(),
                value: c.querySelector('.kpi-value')?.innerText?.trim(),
            }));
        }""")
        print(f"\n📊 KPI 实际显示:")
        for k in kpi:
            print(f"   {k['label']}: {k['value']}")

        await context.close()
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
