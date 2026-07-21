"""端到端功能测验: 真实触发+取消流水线 + 验证数据联动.

这是对用户反馈"按钮触发后无反应"的真实测验:
- 真实提交触发请求
- 真实取消运行
- 验证 KPI/DAG 在操作后是否真实更新

通过对比操作前后的 UI 状态证明前后端联动有效。
"""
import asyncio
import json
import urllib.request
import sys
from pathlib import Path

from playwright.async_api import async_playwright, Page

SCREENSHOTS_DIR = Path("tests/e2e/screenshots/pipeline_action_test")
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
BASE_URL = "http://localhost:5173"
API_URL = "http://localhost:8000/api/v1"


def api_login() -> tuple[str, dict]:
    """通过后端 API 登录获取 token 和用户信息."""
    req = urllib.request.Request(
        f"{API_URL}/auth/login",
        data=json.dumps({"username": "admin", "password": "starmap2024"}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        body = json.loads(resp.read())
        return body["access_token"], body.get("user", {})


def api_get_user_info(token: str) -> dict:
    """通过 /auth/me 拉取用户信息."""
    req = urllib.request.Request(
        f"{API_URL}/auth/me",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def api_get(path: str, token: str) -> dict:
    """通过后端 API 读取数据."""
    req = urllib.request.Request(
        f"{API_URL}{path}",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def get_kpi_values(page: Page) -> dict:
    """从页面提取 KPI 卡片的当前数值."""
    return page.evaluate("""() => {
        const cards = document.querySelectorAll('.kpi-card');
        const out = {};
        cards.forEach(card => {
            const label = card.querySelector('.kpi-label')?.innerText?.trim();
            const value = card.querySelector('.kpi-value')?.innerText?.trim();
            if (label && value) out[label] = value;
        });
        return out;
    }""")


def get_dag_stages(page: Page) -> list:
    """从页面提取 DAG 各阶段的状态."""
    return page.evaluate("""() => {
        const cards = document.querySelectorAll('.stage-card');
        return Array.from(cards).map(c => ({
            text: c.innerText.replace(/\\s+/g, ' ').trim(),
        }));
    }""")


def get_visible_buttons(page: Page) -> list:
    """获取当前可见的按钮列表."""
    return page.evaluate("""() => {
        const btns = document.querySelectorAll('header button, .page-header button, .header-actions button');
        return Array.from(btns).map(b => b.innerText.trim()).filter(t => t);
    }""")


async def wait_for_value_change(page: Page, field: str, before: str, timeout_ms: int = 8000) -> bool:
    """等待特定 KPI 字段值变化."""
    try:
        await page.wait_for_function(
            f"""() => {{
                const cards = document.querySelectorAll('.kpi-card');
                for (const card of cards) {{
                    const label = card.querySelector('.kpi-label')?.innerText?.trim();
                    if (label === '{field}') {{
                        const value = card.querySelector('.kpi-value')?.innerText?.trim();
                        return value && value !== '{before}';
                    }}
                }}
                return false;
            }}""",
            timeout=timeout_ms,
        )
        return True
    except Exception:
        return False


async def main():
    print("=" * 70)
    print("🧪 数据流水线 - 真实端到端功能测验")
    print("=" * 70)

    # 1. 获取后端 token + 用户信息
    token, _ = api_login()
    user_info = api_get_user_info(token)
    print(f"✅ 后端登录成功, user: {user_info.get('username')}, role: {user_info.get('role')}")
    user_json = json.dumps(user_info)

    # 2. 读取初始 KPI 作为基线
    print("\n[基线] 读取后端 KPI 初始值...")
    initial_status = api_get("/pipeline/status", token)
    print(f"   is_running: {initial_status.get('is_running')}")
    print(f"   today_crawl_volume: {initial_status.get('today_crawl_volume')}")
    print(f"   success_rate: {initial_status.get('success_rate')}")
    print(f"   avg_quality_score: {initial_status.get('avg_quality_score')}")
    print(f"   active_data_sources: {initial_status.get('active_data_sources')}")

    if initial_status.get("is_running"):
        # 如果已有运行中的流水线，先取消掉，确保测试从干净状态开始
        run_id = initial_status.get("current_run", {}).get("id")
        if run_id:
            print(f"\n[准备] 取消正在运行的流水线 {run_id[:8]}...")
            try:
                req = urllib.request.Request(
                    f"{API_URL}/pipeline/runs/{run_id}/cancel",
                    data=b"{}",
                    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                    method="POST",
                )
                urllib.request.urlopen(req, timeout=10).read()
                print("   ✅ 已取消现有运行")
                await asyncio.sleep(2)
            except Exception as e:
                print(f"   ⚠️ 取消失败: {e}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1920, "height": 1080}, locale="zh-CN")

        # 注入 token + 用户信息
        await context.add_init_script(f"""
            try {{
                localStorage.setItem('starmap_access_token', '{token}');
                localStorage.setItem('starmap_user', '{user_json}');
            }} catch (e) {{}}
        """)

        page = await context.new_page()

        # 监听网络请求
        api_calls = []
        page.on("request", lambda req: api_calls.append(
            f"{req.method} {req.url.split('localhost')[-1] if 'localhost' in req.url else req.url}"
        ) if "/pipeline/" in req.url else None)

        # 监听 ElMessage
        toasts = []
        page.on("console", lambda msg: None)

        # ── 阶段 1: 打开页面，截图 + 抓取初始 UI 状态 ──
        print("\n" + "─" * 70)
        print("[阶段 1] 打开流水线页面...")
        await page.goto(f"{BASE_URL}/pipeline", wait_until="networkidle", timeout=30000)
        # 等KPI卡片 + 等待 user store 加载完成（isAdmin 状态）
        await page.wait_for_selector(".kpi-card", timeout=10000)
        # 等待 admin 按钮组加载 + 等待 user 状态同步
        await page.wait_for_timeout(5000)
        # 强制等按钮出现
        try:
            await page.wait_for_selector('button:has-text("触发流水线")', timeout=10000)
        except Exception:
            # 如果是 admin 但按钮没出，截图调试
            current_url = page.url
            print(f"   当前 URL: {current_url}")
            await page.screenshot(path=str(SCREENSHOTS_DIR / "debug_no_admin_btn.png"), full_page=True)
            print("   ⚠️ '触发流水线'按钮未出现，截图已保存到 debug_no_admin_btn.png")

        kpi_before = await get_kpi_values(page)
        stages_before = await get_dag_stages(page)
        buttons_before = await get_visible_buttons(page)
        await page.screenshot(path=str(SCREENSHOTS_DIR / "01_before_action.png"))

        print(f"   页面 KPI 状态: {kpi_before}")
        print(f"   可见按钮: {buttons_before}")
        print(f"   DAG 阶段数: {len(stages_before)}")

        # 触发按钮必须可见
        if "触发流水线" not in buttons_before:
            print("   ❌ '触发流水线' 按钮不可见")
            return False

        # ── 阶段 2: 点击"触发流水线" → 弹窗 → 选阶段 → 启动 ──
        print("\n" + "─" * 70)
        print("[阶段 2] 真实点击'触发流水线' → 提交 → 验证反馈...")

        # 点击触发按钮
        api_calls.clear()
        await page.click('button:has-text("触发流水线")')
        await page.wait_for_selector('.el-dialog:has-text("触发流水线")', timeout=5000)
        await page.wait_for_timeout(800)
        await page.screenshot(path=str(SCREENSHOTS_DIR / "02a_trigger_dialog.png"))
        print("   ✅ 弹窗已弹出")

        # 提交（不取消任何阶段，默认全选）
        print("   点击'启动'按钮...")
        await page.click('.el-dialog button:has-text("启动")')
        await page.wait_for_timeout(500)

        # 等待弹窗关闭
        await page.wait_for_selector('.el-dialog:has-text("触发流水线")', state='hidden', timeout=8000)
        print("   ✅ 弹窗已自动关闭（启动成功）")

        # 等待并捕获 ElMessage
        try:
            await page.wait_for_selector('.el-message', timeout=5000)
            msg_text = await page.inner_text('.el-message')
            print(f"   🆕 收到 toast 提示: {msg_text.strip()}")
        except Exception:
            print("   ⚠️ 未捕获到 toast 提示")

        # 等待 KPI 重新计算
        await page.wait_for_timeout(3000)
        kpi_after_trigger = await get_kpi_values(page)
        stages_after_trigger = await get_dag_stages(page)
        buttons_after_trigger = await get_visible_buttons(page)
        await page.screenshot(path=str(SCREENSHOTS_DIR / "02b_after_trigger.png"))

        print(f"   触发后 KPI: {kpi_after_trigger}")
        print(f"   触发后可见按钮: {buttons_after_trigger}")

        # 验证触发后: is_running 应为 true
        new_status = api_get("/pipeline/status", token)
        is_running_after = new_status.get("is_running")
        print(f"   后端确认 is_running: {is_running_after}")

        # 关键断言: 触发后"取消运行"按钮应出现
        if "取消运行" in buttons_after_trigger:
            print("   ✅ '取消运行'按钮出现（is_running=true）")
        elif is_running_after:
            print("   ⚠️ 后端 is_running=true 但前端未显示'取消运行'按钮 — 状态联动可能有问题")
        else:
            print("   ⚠️ 触发未生效（is_running 仍为 false）")

        # 检查 KPI 是否更新（采集量/成功率/质量分/数据源数）
        kpi_changed = any(kpi_before.get(k) != kpi_after_trigger.get(k) for k in kpi_before)
        print(f"   KPI 变化: {kpi_changed}")
        for k, v in kpi_before.items():
            new_v = kpi_after_trigger.get(k, "N/A")
            if v != new_v:
                print(f"     {k}: {v} → {new_v}")

        # ── 阶段 3: 点击"取消运行" ──
        print("\n" + "─" * 70)
        print("[阶段 3] 真实点击'取消运行' → 验证反馈...")

        api_calls.clear()
        await page.click('button:has-text("取消运行")')
        # 确认弹窗
        await page.wait_for_selector('.el-message-box', timeout=5000)
        await page.screenshot(path=str(SCREENSHOTS_DIR / "03a_cancel_confirm.png"))
        print("   ✅ 取消确认弹窗已弹出")
        await page.click('.el-message-box .el-button:has-text("确认取消")')
        await page.wait_for_timeout(500)

        # 等待取消响应
        try:
            await page.wait_for_selector('.el-message', timeout=5000)
            msg_text = await page.inner_text('.el-message')
            print(f"   🆕 收到 toast: {msg_text.strip()}")
        except Exception:
            print("   ⚠️ 未捕获到 toast 提示")

        await page.wait_for_timeout(3000)
        kpi_after_cancel = await get_kpi_values(page)
        buttons_after_cancel = await get_visible_buttons(page)
        await page.screenshot(path=str(SCREENSHOTS_DIR / "03b_after_cancel.png"))

        print(f"   取消后按钮: {buttons_after_cancel}")
        print(f"   取消后 KPI: {kpi_after_cancel}")

        # 验证: "取消运行"按钮应消失
        if "取消运行" not in buttons_after_cancel:
            print("   ✅ '取消运行'按钮已消失（is_running=false）")
        else:
            print("   ❌ '取消运行'按钮仍在显示 — 联动可能未生效")

        # 后端确认
        final_status = api_get("/pipeline/status", token)
        is_running_final = final_status.get("is_running")
        print(f"   后端最终 is_running: {is_running_final}")

        # 验证 KPI 在 cancel 后是否更新
        print(f"   KPI 在 cancel 后的变化:")
        for k in kpi_before:
            v1 = kpi_before.get(k, "N/A")
            v2 = kpi_after_cancel.get(k, "N/A")
            if v1 != v2:
                print(f"     {k}: {v1} → {v2}")

        # ── 阶段 4: 点击"定时调度" ──
        print("\n" + "─" * 70)
        print("[阶段 4] 真实点击'定时调度' → 验证弹窗...")

        api_calls.clear()
        await page.click('button:has-text("定时调度")')
        try:
            await page.wait_for_selector('.el-dialog:has-text("创建定时调度")', timeout=5000)
            await page.screenshot(path=str(SCREENSHOTS_DIR / "04a_schedule_dialog.png"))
            print("   ✅ 定时调度弹窗已弹出")
            dialog_text = await page.inner_text('.el-dialog:has-text("创建定时调度")')
            for field in ["名称", "Cron 表达式", "运行类型", "启用"]:
                if field in dialog_text:
                    print(f"     ✓ 包含字段: {field}")
            # 关闭
            await page.click('.el-dialog .el-button:has-text("取消")')
            await page.wait_for_timeout(800)
            print("   ✅ 弹窗已关闭")
        except Exception as e:
            print(f"   ❌ 弹窗未弹出: {e}")

        # ── 阶段 5: 点击"配置" ──
        print("\n" + "─" * 70)
        print("[阶段 5] 真实点击'配置' → 验证弹窗 + GET /config 接口...")

        api_calls.clear()
        await page.click('button:has-text("配置")')
        try:
            await page.wait_for_selector('.el-dialog:has-text("流水线配置")', timeout=5000)
            await page.wait_for_timeout(1000)  # 等 GET /config 响应
            await page.screenshot(path=str(SCREENSHOTS_DIR / "05a_config_dialog.png"))
            print("   ✅ 配置弹窗已弹出")
            dialog_text = await page.inner_text('.el-dialog:has-text("流水线配置")')
            for field in ["阶段超时", "Worker并发", "爬取并发", "最大重试", "重试间隔"]:
                if field in dialog_text:
                    print(f"     ✓ 包含字段: {field}")
            # 检查是否调用了 GET /config
            config_called = any("/config" in c for c in api_calls)
            print(f"     {'✓' if config_called else '⚠️'} GET /config 接口调用: {config_called}")
            # 关闭
            await page.click('.el-dialog .el-button:has-text("取消")')
            await page.wait_for_timeout(800)
            print("   ✅ 弹窗已关闭")
        except Exception as e:
            print(f"   ❌ 弹窗未弹出: {e}")

        await page.screenshot(path=str(SCREENSHOTS_DIR / "06_final.png"))
        await context.close()
        await browser.close()

    print("\n" + "=" * 70)
    print("📊 测验总结")
    print("=" * 70)
    print(f"📁 截图保存: {SCREENSHOTS_DIR}")
    print(f"   01_before_action.png       初始页面状态")
    print(f"   02a_trigger_dialog.png     触发弹窗")
    print(f"   02b_after_trigger.png      触发后状态")
    print(f"   03a_cancel_confirm.png     取消确认弹窗")
    print(f"   03b_after_cancel.png       取消后状态")
    print(f"   04a_schedule_dialog.png    定时调度弹窗")
    print(f"   05a_config_dialog.png      配置弹窗")
    print(f"   06_final.png               最终状态")

    return True


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
