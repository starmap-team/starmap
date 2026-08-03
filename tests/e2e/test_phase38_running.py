"""Phase 3.8 真实运行端到端测试 - 触发 + 等待运行 + 截图 DAG 实时数据 + 取消."""
import asyncio
import json
import urllib.request
from pathlib import Path
from playwright.async_api import async_playwright


SCREENSHOTS_DIR = Path("tests/e2e/screenshots/phase38_running")
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)


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

    # 取消任何 stuck run
    status = json.loads(urllib.request.urlopen(urllib.request.Request("http://localhost:8000/api/v1/pipeline/status", headers=H)).read())
    if status.get("current_run"):
        rid = status["current_run"]["id"]
        print(f"取消 stuck run {rid[:8]}...")
        urllib.request.urlopen(urllib.request.Request(
            f"http://localhost:8000/api/v1/pipeline/runs/{rid}/cancel",
            data=b"{}", headers=H, method="POST"
        ), timeout=10).read()
    await asyncio.sleep(2)

    # 通过 API 触发一个新 pipeline
    print("触发 pipeline (增量, only crawl)...")
    trigger_req = urllib.request.Request(
        "http://localhost:8000/api/v1/pipeline/trigger",
        data=json.dumps({"run_type": "incremental", "selected_stages": ["crawl"]}).encode(),
        headers=H, method="POST",
    )
    resp = json.loads(urllib.request.urlopen(trigger_req, timeout=10).read())
    run_id = resp["run_id"]
    print(f"  触发成功, run_id={run_id[:8]}")

    # 等待 3 秒让 stage 标记为 running
    await asyncio.sleep(3)
    status = json.loads(urllib.request.urlopen(urllib.request.Request("http://localhost:8000/api/v1/pipeline/status", headers=H)).read())
    if status.get("current_run"):
        for s in status["current_run"]["stages"]:
            if s["status"] != "skipped":
                print(f"  Stage {s['name']}: status={s['status']} started_at={s.get('started_at') is not None}")

    # 现在打开页面查看实时 DAG
    print("\n打开页面查看实时 DAG...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1920, "height": 1500}, locale="zh-CN")
        await context.add_init_script(f"""
            localStorage.setItem('starmap_access_token', '{token}');
            localStorage.setItem('starmap_user', '{json.dumps(user_info)}');
        """)
        page = await context.new_page()

        await page.goto("http://localhost:5173/pipeline", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(8000)

        # 截图: 正在运行的 DAG
        await page.screenshot(path=str(SCREENSHOTS_DIR / "01_running_dag.png"), full_page=True)
        print(f"  ✅ 截图: 01_running_dag.png")

        # 检查 DAG 卡片状态
        cards = await page.query_selector_all(".stage-card")
        print(f"\n  DAG 卡片状态:")
        for c in cards:
            txt = (await c.inner_text())[:100].replace("\n", " | ")
            print(f"    {txt}")

        # 检查校验日志
        await page.click("button:has-text('校验状态')")
        await page.wait_for_timeout(2000)
        log_items = await page.query_selector_all(".verify-log-item")
        print(f"\n  验证日志条目: {len(log_items)}")
        if log_items:
            log_text = await log_items[0].inner_text()
            print(f"  最新日志: {log_text.replace(chr(10), ' | ')[:200]}")

        # 截图: 验证日志
        await page.screenshot(path=str(SCREENSHOTS_DIR / "02_with_verify_log.png"), full_page=True)
        print(f"  ✅ 截图: 02_with_verify_log.png")

        # 取消 pipeline
        print("\n点击'取消运行'按钮...")
        cancel_btn = await page.query_selector('button:has-text("取消运行")')
        if cancel_btn:
            await cancel_btn.click()
            # 等待 ElMessageBox 确认对话框
            await page.wait_for_selector('.el-message-box', timeout=5000)
            await page.wait_for_timeout(500)
            await page.screenshot(path=str(SCREENSHOTS_DIR / "03a_confirm_dialog.png"), full_page=True)
            # 点击确认取消
            confirm_btn = await page.query_selector('.el-message-box .el-button--primary')
            if confirm_btn:
                await confirm_btn.click()
            await page.wait_for_timeout(5000)
            await page.screenshot(path=str(SCREENSHOTS_DIR / "03_after_cancel.png"), full_page=True)
            print(f"  ✅ 截图: 03a_confirm_dialog.png + 03_after_cancel.png")

            # 验证日志应该新增
            log_items = await page.query_selector_all(".verify-log-item")
            print(f"\n  取消后日志条目: {len(log_items)}")
            for i, log in enumerate(log_items[:2]):
                txt = await log.inner_text()
                print(f"    [{i}] {txt.replace(chr(10), ' | ')[:150]}")

            # 按钮应该消失
            cancel_btn_after = await page.query_selector('button:has-text("取消运行")')
            print(f"  取消按钮: {'已消失 ✅' if not cancel_btn_after else '仍在 ⚠️'}")

        await context.close()
        await browser.close()

    print(f"\n截图保存于: {SCREENSHOTS_DIR}")


if __name__ == "__main__":
    asyncio.run(main())
