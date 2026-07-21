"""测试 cancel 后 store 是否真实更新."""
import asyncio
import json
import urllib.request
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

    # 触发 pipeline
    print("触发 pipeline...")
    trigger = urllib.request.Request(
        "http://localhost:8000/api/v1/pipeline/trigger",
        data=json.dumps({"run_type": "incremental", "selected_stages": ["crawl"]}).encode(),
        headers=H, method="POST",
    )
    urllib.request.urlopen(trigger, timeout=10).read()
    await asyncio.sleep(2)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1920, "height": 1200}, locale="zh-CN")
        await context.add_init_script(f"""
            localStorage.setItem('starmap_access_token', '{token}');
            localStorage.setItem('starmap_user', '{json.dumps(user_info)}');
        """)
        page = await context.new_page()

        # 拦截 API 调用
        api_calls = []
        page.on("response", lambda r: api_calls.append(f"{r.status} {r.url.split('localhost')[-1]}") if "/api/v1/pipeline" in r.url and "events" not in r.url else None)

        await page.goto("http://localhost:5173/pipeline", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(8000)

        # 在 store 中检查 cancel 前的状态
        before = await page.evaluate("""() => {
            const app = document.querySelector('#app')?.__vue_app__;
            const pinia = app?.config?.globalProperties?.$pinia;
            const store = pinia?._s?.get('pipelineRun');
            return {
                is_running: store?.pipelineStatus?.is_running,
                current_run_status: store?.pipelineStatus?.current_run?.status,
                current_run_id: store?.pipelineStatus?.current_run?.id,
            };
        }""")
        print(f"\n取消前 store 状态: {before}")

        # 点击 cancel
        print("\n点击取消按钮...")
        cancel_btn = await page.query_selector('button:has-text("取消运行")')
        if not cancel_btn:
            print("❌ 取消按钮未出现")
            return

        await cancel_btn.click()
        await page.wait_for_selector('.el-message-box', timeout=5000)
        confirm_btn = await page.query_selector('.el-message-box .el-button--primary')
        await confirm_btn.click()

        # 立即检查 store 状态 (这是关键 - 看是否在 cancel API 返回后 loadAll 立即更新)
        await page.wait_for_timeout(500)
        during_verify = await page.evaluate("""() => {
            const app = document.querySelector('#app')?.__vue_app__;
            const pinia = app?.config?.globalProperties?.$pinia;
            const store = pinia?._s?.get('pipelineRun');
            return {
                is_running: store?.pipelineStatus?.is_running,
                current_run_status: store?.pipelineStatus?.current_run?.status,
                current_run_id: store?.pipelineStatus?.current_run?.id,
            };
        }""")
        print(f"取消后 500ms store 状态: {during_verify}")

        await page.wait_for_timeout(3000)
        after = await page.evaluate("""() => {
            const app = document.querySelector('#app')?.__vue_app__;
            const pinia = app?.config?.globalProperties?.$pinia;
            const store = pinia?._s?.get('pipelineRun');
            return {
                is_running: store?.pipelineStatus?.is_running,
                current_run_status: store?.pipelineStatus?.current_run?.status,
                current_run_id: store?.pipelineStatus?.current_run?.id,
            };
        }""")
        print(f"取消后 3.5s store 状态: {after}")

        # 检查 UI
        cancel_btn_after = await page.query_selector('button:has-text("取消运行")')
        print(f"取消按钮: {'已消失 ✅' if not cancel_btn_after else '仍在 ⚠️'}")

        # 检查验证日志
        log_items = await page.query_selector_all(".verify-log-item")
        if log_items:
            latest = log_items[0]
            log_text = await latest.inner_text()
            print(f"\n最新验证日志: {log_text.replace(chr(10), ' | ')[:200]}")

        # API 调用记录
        print(f"\nAPI 调用记录 (cancel 后):")
        for c in api_calls[-15:]:
            print(f"  {c}")

        await page.screenshot(path="tests/e2e/screenshots/cancel_debug.png", full_page=False)
        await context.close()
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
