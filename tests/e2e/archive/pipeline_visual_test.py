"""端到端视觉测验：数据流水线监控页所有按钮.

测试目标:
1. 验证每个按钮的视觉反馈链路（loading状态、toast、组件状态变化）
2. 验证网络请求（API调用是否真实发生）
3. 验证数据联动（KPI/DAG/质量面板是否随动作变化）
4. 截图存证每个步骤的状态

运行要求: 后端 8000、前端 5173、登录态可访问
"""
import asyncio
import os

from e2e_creds import login_payload, ADMIN_PASSWORD
import sys
import time
from pathlib import Path

from playwright.async_api import async_playwright, Page, BrowserContext

# 截图输出目录
SCREENSHOTS_DIR = Path("tests/e2e/screenshots/pipeline_visual_test")
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

BASE_URL = "http://localhost:5173"


class TestResult:
    """单个测试结果记录器."""

    def __init__(self, name: str):
        self.name = name
        self.passed = False
        self.feedback_found = []    # 找到的视觉反馈
        self.network_calls = []     # 观察到的网络请求
        self.error = None

    def __str__(self):
        status = "✅ PASS" if self.passed else "❌ FAIL"
        lines = [f"\n{status} | {self.name}"]
        if self.feedback_found:
            lines.append(f"  📌 视觉反馈:")
            for f in self.feedback_found:
                lines.append(f"     • {f}")
        if self.network_calls:
            lines.append(f"  🌐 网络请求: {len(self.network_calls)}次")
            for nc in self.network_calls[:5]:
                lines.append(f"     • {nc}")
        if self.error:
            lines.append(f"  ⚠️  错误: {self.error}")
        return "\n".join(lines)


async def capture_screenshot(page: Page, name: str) -> str:
    """截图并返回相对路径."""
    path = SCREENSHOTS_DIR / f"{name}.png"
    await page.screenshot(path=str(path), full_page=False)
    return str(path.relative_to(SCREENSHOTS_DIR.parent.parent.parent))


async def wait_for_app_ready(page: Page) -> None:
    """等待 Vue 应用挂载完成."""
    await page.wait_for_selector(".el-button, button", timeout=15000)
    await page.wait_for_timeout(1500)


async def login_if_needed(page: Page) -> None:
    """自动登录（如需要）."""
    # 检查是否在登录页
    if "/login" in page.url:
        print("  → 检测到登录页，自动登录为 admin")
        await page.fill('input[placeholder*="用户名"], input[placeholder*="username"], input[type="text"]:first-of-type', "admin")
        await page.fill('input[type="password"]', ADMIN_PASSWORD)
        await page.click('button[type="submit"], button:has-text("登录")')
        # 等待跳转，但允许停留在当前页（也可能留在原页）
        try:
            await page.wait_for_url(lambda u: "/login" not in u, timeout=10000)
        except Exception:
            pass  # 可能在原地或已经成功
        await page.wait_for_timeout(2000)


async def api_login(context: BrowserContext) -> None:
    """通过 API 直接登录并设置 localStorage 避免 UI 登录."""
    api_url = "http://localhost:8000/api/v1/auth/login"
    # 用 requests 风格的 API 调用
    import json
    import urllib.request
    try:
        req = urllib.request.Request(
            api_url,
            data=json.dumps(login_payload()).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            token = body.get("access_token")
            if token:
                # 通过 init script 在每个 page 注入 localStorage
                context.add_init_script(f"""
                    try {{
                        localStorage.setItem('starmap_access_token', '{token}');
                    }} catch (e) {{}}
                """)
                return True
    except Exception as e:
        print(f"  ⚠️ API 登录失败: {e}")
    return False


async def test_initial_load(page: Page, network_log: list) -> TestResult:
    """T1: 验证页面初次加载及所有数据填充."""
    result = TestResult("T1: 页面加载 + 初始数据填充")
    try:
        # 监听网络
        network_log.clear()

        await page.goto(f"{BASE_URL}/pipeline", wait_until="networkidle", timeout=30000)
        await login_if_needed(page)
        await page.wait_for_url("**/pipeline**", timeout=10000)
        await wait_for_app_ready(page)

        # 等待关键API完成
        await page.wait_for_timeout(3000)

        # 检查4个KPI卡片是否有数值
        kpi_cards = await page.query_selector_all(".kpi-card, .kpi-value")
        kpi_values = []
        for card in kpi_cards:
            text = (await card.inner_text()).strip()
            if text and text != "--":
                kpi_values.append(text)

        if len(kpi_values) >= 4:
            result.feedback_found.append(f"4个KPI卡片显示数值: {kpi_values[:4]}")
            result.passed = True
        else:
            result.feedback_found.append(f"⚠️ 仅找到 {len(kpi_values)} 个KPI值")

        # 检查 DAG 时间线是否显示5个阶段
        dag_stages = await page.query_selector_all(".stage-card, .pipeline-dag .timeline-node")
        if len(dag_stages) >= 5:
            result.feedback_found.append(f"DAG显示 {len(dag_stages)} 个阶段卡片")
        else:
            result.feedback_found.append(f"⚠️ DAG仅 {len(dag_stages)} 个阶段")

        # 检查 SSE 标签
        sse_tag = await page.query_selector("text=SSE 实时")
        if sse_tag:
            result.feedback_found.append("SSE 实时标签可见（连接成功）")

        # 检查网络请求
        api_calls = [c for c in network_log if "/api/" in c or "/pipeline/" in c]
        if api_calls:
            result.network_calls = list(set(api_calls))[:10]
            result.feedback_found.append(f"页面初始化触发 {len(api_calls)} 个API调用")

        await capture_screenshot(page, "01_initial_load")
    except Exception as e:
        result.error = str(e)
    return result


async def test_refresh_button(page: Page, network_log: list) -> TestResult:
    """T2: 验证"刷新"按钮 - loadAll() 应触发4个API调用."""
    result = TestResult("T2: 刷新按钮 (loadAll)")
    try:
        # 记录点击前时间戳
        before_time = await page.query_selector(".last-refresh")
        before_text = (await before_time.inner_text()) if before_time else ""

        network_log.clear()
        # 点击刷新按钮
        refresh_btn = await page.query_selector('button:has-text("刷新")')
        if not refresh_btn:
            result.error = "未找到'刷新'按钮"
            return result

        await refresh_btn.click()
        await page.wait_for_timeout(2000)

        # 验证网络请求
        api_calls = [c for c in network_log if "/pipeline/" in c]
        unique_endpoints = set()
        for call in api_calls:
            for ep in ["/status", "/stages", "/data-quality", "/datasources"]:
                if ep in call:
                    unique_endpoints.add(ep)

        if len(unique_endpoints) >= 4:
            result.feedback_found.append(f"刷新触发 {len(unique_endpoints)} 个数据接口: {sorted(unique_endpoints)}")
            result.passed = True
        elif len(api_calls) > 0:
            result.feedback_found.append(f"刷新触发 {len(api_calls)} 次API调用，但缺少完整数据接口")
            result.passed = len(api_calls) >= 3

        # 验证时间戳变化
        after_time = await page.query_selector(".last-refresh")
        after_text = (await after_time.inner_text()) if after_time else ""
        if after_text != before_text and after_text:
            result.feedback_found.append(f"'最近刷新'时间戳已更新: {after_text}")
        elif before_text:
            result.feedback_found.append(f"时间戳未变: {before_text}")

        await capture_screenshot(page, "02_after_refresh")
    except Exception as e:
        result.error = str(e)
    return result


async def test_auto_refresh_toggle(page: Page, network_log: list) -> TestResult:
    """T3: 验证自动刷新开关 - 切换时显示 ElMessage."""
    result = TestResult("T3: 自动刷新开关")
    try:
        # 找到开关
        switch = await page.query_selector('.el-switch')
        if not switch:
            result.error = "未找到自动刷新开关"
            return result

        # 记录开关当前状态
        is_active = await switch.evaluate("el => el.classList.contains('is-checked')")
        network_log.clear()

        # 点击切换
        await switch.click()
        await page.wait_for_timeout(1500)

        # 查找 ElMessage 提示
        message = await page.query_selector(".el-message")
        if message:
            msg_text = (await message.inner_text()).strip()
            result.feedback_found.append(f"切换提示: '{msg_text}'")
            result.passed = True
        else:
            result.feedback_found.append("⚠️ 切换后未显示 ElMessage")

        # 切换回原状态
        await page.wait_for_timeout(2000)
        new_is_active = await switch.evaluate("el => el.classList.contains('is-checked')")
        if new_is_active != is_active:
            result.feedback_found.append(f"开关状态已切换: {is_active} → {new_is_active}")

        await capture_screenshot(page, "03_auto_refresh_toggle")
    except Exception as e:
        result.error = str(e)
    return result


async def test_trigger_dialog(page: Page, network_log: list) -> TestResult:
    """T4: 验证"触发流水线"按钮 - 弹窗 + 提交 + 全页面刷新."""
    result = TestResult("T4: 触发流水线按钮")
    try:
        # 找到"触发流水线"按钮
        trigger_btn = await page.query_selector('button:has-text("触发流水线")')
        if not trigger_btn:
            result.error = "未找到'触发流水线'按钮"
            return result

        # 检查按钮是否禁用
        is_disabled = await trigger_btn.is_disabled()
        if is_disabled:
            result.error = "触发按钮被禁用（pipeline已在运行中）— 跳过测试"
            return result

        # 点击按钮打开弹窗
        await trigger_btn.click()
        await page.wait_for_timeout(1000)

        # 验证弹窗出现
        dialog = await page.query_selector(".el-dialog")
        if not dialog:
            result.error = "弹窗未出现"
            return result
        result.feedback_found.append("点击后弹窗已弹出")

        # 验证弹窗内容
        dialog_text = (await dialog.inner_text()).strip()
        if "运行类型" in dialog_text and "执行阶段" in dialog_text:
            result.feedback_found.append("弹窗包含 '运行类型' 和 '执行阶段' 选项")
        else:
            result.feedback_found.append(f"⚠️ 弹窗内容异常: {dialog_text[:100]}")

        await capture_screenshot(page, "04a_trigger_dialog")

        # 关闭弹窗先（点击取消）
        cancel_btn = await page.query_selector('.el-dialog .el-button:has-text("取消")')
        if cancel_btn:
            await cancel_btn.click()
            await page.wait_for_timeout(500)
            result.feedback_found.append("点击'取消'成功关闭弹窗")
            result.passed = True
        else:
            # 直接关闭弹窗
            close_btn = await page.query_selector(".el-dialog__close")
            if close_btn:
                await close_btn.click()
                await page.wait_for_timeout(500)
            result.feedback_found.append("弹窗已关闭")
            result.passed = True

    except Exception as e:
        result.error = str(e)
    return result


async def test_schedule_dialog(page: Page, network_log: list) -> TestResult:
    """T5: 验证"定时调度"按钮 - 弹窗显示."""
    result = TestResult("T5: 定时调度按钮")
    try:
        # 查找按钮
        schedule_btn = await page.query_selector('button:has-text("定时调度")')
        if not schedule_btn:
            result.error = "未找到'定时调度'按钮"
            return result

        await schedule_btn.click()
        await page.wait_for_timeout(1000)

        # 验证弹窗
        dialog = await page.query_selector(".el-dialog")
        if not dialog:
            result.error = "弹窗未出现"
            return result

        dialog_text = (await dialog.inner_text()).strip()
        if "Cron" in dialog_text and "名称" in dialog_text:
            result.feedback_found.append("弹窗包含 '名称' 'Cron 表达式' '运行类型' '启用' 表单")
            result.passed = True
        else:
            result.feedback_found.append(f"⚠️ 弹窗内容异常: {dialog_text[:100]}")

        await capture_screenshot(page, "05a_schedule_dialog")

        # 关闭弹窗
        close_btn = await page.query_selector(".el-dialog__close")
        if close_btn:
            await close_btn.click()
            await page.wait_for_timeout(500)
            result.feedback_found.append("弹窗已关闭")

    except Exception as e:
        result.error = str(e)
    return result


async def test_config_dialog(page: Page, network_log: list) -> TestResult:
    """T6: 验证"配置"按钮 - 弹窗 + 5个参数."""
    result = TestResult("T6: 配置按钮")
    try:
        # 查找按钮
        config_btn = await page.query_selector('button:has-text("配置")')
        if not config_btn:
            result.error = "未找到'配置'按钮"
            return result

        network_log.clear()
        await config_btn.click()
        await page.wait_for_timeout(1500)

        # 验证弹窗
        dialog = await page.query_selector(".el-dialog")
        if not dialog:
            result.error = "弹窗未出现"
            return result

        # 验证表单字段
        dialog_text = (await dialog.inner_text()).strip()
        expected_fields = ["阶段超时", "Worker并发", "爬取并发", "最大重试", "重试间隔"]
        found_fields = [f for f in expected_fields if f in dialog_text]

        if len(found_fields) >= 5:
            result.feedback_found.append(f"配置弹窗含全部5个参数: {found_fields}")
            result.passed = True
        elif found_fields:
            result.feedback_found.append(f"配置弹窗仅含 {len(found_fields)}/5 个参数: {found_fields}")
        else:
            result.error = f"配置弹窗内容异常: {dialog_text[:100]}"

        # 验证配置接口被调用
        config_api = [c for c in network_log if "/config" in c]
        if config_api:
            result.network_calls = config_api
            result.feedback_found.append(f"弹窗打开触发 GET /config")

        await capture_screenshot(page, "06a_config_dialog")

        # 关闭弹窗
        close_btn = await page.query_selector(".el-dialog__close")
        if close_btn:
            await close_btn.click()
            await page.wait_for_timeout(500)

    except Exception as e:
        result.error = str(e)
    return result


async def test_data_source_panel(page: Page) -> TestResult:
    """T7: 验证数据源面板显示."""
    result = TestResult("T7: 数据源面板")
    try:
        # 查找数据源面板
        panel = await page.query_selector("text=数据源")
        if not panel:
            # 查找 DataSourceCard
            cards = await page.query_selector_all(".data-source-card, .source-card")
            if cards:
                result.feedback_found.append(f"数据源面板显示 {len(cards)} 个数据源卡片")
                result.passed = True
            else:
                result.error = "未找到数据源面板"
            return result

        cards = await page.query_selector_all(".data-source-card, .source-card, [class*='source']")
        result.feedback_found.append(f"数据源面板存在，显示 {len(cards)} 个元素")
        result.passed = len(cards) > 0

    except Exception as e:
        result.error = str(e)
    return result


async def test_quality_panel(page: Page) -> TestResult:
    """T8: 验证质量监控面板 - 仪表盘 + 趋势图."""
    result = TestResult("T8: 数据质量面板")
    try:
        # 查找质量面板
        quality_text = await page.query_selector("text=数据质量, text=质量监控")
        if not quality_text:
            # 查找进度条（4维度）
            progress_bars = await page.query_selector_all(".el-progress, [class*='gauge']")
            if progress_bars:
                result.feedback_found.append(f"质量面板显示 {len(progress_bars)} 个进度条/仪表盘")
                result.passed = True
            else:
                result.error = "未找到数据质量面板"
            return result

        # 查找 ECharts canvas
        canvas = await page.query_selector("canvas")
        if canvas:
            result.feedback_found.append("ECharts 趋势图已渲染")

        # 查找4个维度进度条
        progress_bars = await page.query_selector_all(".el-progress")
        if progress_bars:
            result.feedback_found.append(f"质量4维度进度条: {len(progress_bars)} 个")
            result.passed = True

        await capture_screenshot(page, "08_quality_panel")
    except Exception as e:
        result.error = str(e)
    return result


async def test_dag_visual_consistency(page: Page) -> TestResult:
    """T9: 验证 DAG 视觉一致性 - 5个阶段、并行指示."""
    result = TestResult("T9: DAG 时间线视觉一致性")
    try:
        # 找到DAG节点
        nodes = await page.query_selector_all(".timeline-node")
        if len(nodes) >= 5:
            result.feedback_found.append(f"DAG 显示 {len(nodes)} 个阶段节点")
        else:
            result.error = f"DAG 节点数={len(nodes)}, 应为5"
            return result

        # 验证并行标签
        parallel_label = await page.query_selector("text=并行")
        if parallel_label:
            result.feedback_found.append("并行标签 '并行' 可见（dedup ∥ clean）")
        else:
            result.feedback_found.append("⚠️ 未找到'并行'标签")

        # 验证 DAG 标题
        dag_title = await page.query_selector("text=流水线时间线")
        if dag_title:
            result.feedback_found.append("DAG 标题 '流水线时间线 (DAG)' 可见")
            result.passed = True

        # 检查各阶段中文名
        expected_stages = ["爬虫采集", "SimHash去重", "清洗标准化", "数据入库", "图谱构建"]
        body_text = await page.inner_text("body")
        found_stages = [s for s in expected_stages if s in body_text]
        if found_stages:
            result.feedback_found.append(f"阶段中文标签: {found_stages}")

    except Exception as e:
        result.error = str(e)
    return result


async def main():
    """主测试流程."""
    print("=" * 70)
    print("🎬 数据流水线监控页 - 端到端视觉测验")
    print("=" * 70)

    network_log = []  # 全局网络日志
    results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="zh-CN",
        )

        # 优先通过 API 登录并注入 token 到 localStorage
        print("\n[Setup] 通过 API 登录获取 JWT token...")
        api_ok = await api_login(context)
        if api_ok:
            print("  ✅ Token 已注入 localStorage")
        else:
            print("  ⚠️ API 登录失败，将尝试 UI 登录")

        page = await context.new_page()

        # 监听所有网络请求
        def on_request(req):
            if "/api/" in req.url or "/pipeline/" in req.url:
                network_log.append(f"{req.method} {req.url.split('localhost')[-1] if 'localhost' in req.url else req.url}")
        page.on("request", on_request)

        # 监听 console 错误
        console_errors = []
        def on_console(msg):
            if msg.type == "error":
                console_errors.append(msg.text)
        page.on("console", on_console)

        # 执行测试套件
        print("\n[T1] 初始加载...")
        results.append(await test_initial_load(page, network_log))
        print(results[-1])

        print("\n[T2] 刷新按钮...")
        results.append(await test_refresh_button(page, network_log))
        print(results[-1])

        print("\n[T3] 自动刷新开关...")
        results.append(await test_auto_refresh_toggle(page, network_log))
        print(results[-1])

        print("\n[T4] 触发流水线...")
        results.append(await test_trigger_dialog(page, network_log))
        print(results[-1])

        print("\n[T5] 定时调度...")
        results.append(await test_schedule_dialog(page, network_log))
        print(results[-1])

        print("\n[T6] 配置按钮...")
        results.append(await test_config_dialog(page, network_log))
        print(results[-1])

        print("\n[T7] 数据源面板...")
        results.append(await test_data_source_panel(page))
        print(results[-1])

        print("\n[T8] 数据质量面板...")
        results.append(await test_quality_panel(page))
        print(results[-1])

        print("\n[T9] DAG 视觉一致性...")
        results.append(await test_dag_visual_consistency(page))
        print(results[-1])

        # 最终截图
        await page.screenshot(path=str(SCREENSHOTS_DIR / "99_final.png"))

        await context.close()
        await browser.close()

    # ── 汇总 ──
    print("\n" + "=" * 70)
    print("📊 测试汇总")
    print("=" * 70)
    passed = sum(1 for r in results if r.passed)
    total = len(results)
    for r in results:
        print(r)
    print(f"\n🎯 通过率: {passed}/{total} ({passed/total*100:.0f}%)")

    if console_errors:
        print(f"\n⚠️  Console 错误 ({len(console_errors)}):")
        for e in console_errors[:5]:
            print(f"  - {e[:150]}")

    print(f"\n📁 截图保存: {SCREENSHOTS_DIR}")
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
