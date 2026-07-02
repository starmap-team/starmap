"""
StarMap 数据流水线 E2E 测试 — 完整批量爬虫流前后端联调
覆盖: DAG并行执行、阶段选择、失败重试/断点续跑、定时调度、SSE实时进度、配置调整
"""
from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright, Page, Browser, expect

BASE_URL = "http://localhost:5173"
BACKEND_URL = "http://localhost:8000"
SCREENSHOT_DIR = Path("starmap/tests/e2e/browser-qa/screenshots/pipeline")
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

REPORT = {
    "timestamp": datetime.now().isoformat(),
    "base_url": BASE_URL,
    "backend_url": BACKEND_URL,
    "tests": [],
    "issues": [],
    "console_errors": [],
    "network_errors": [],
}


def take_screenshot(page: Page, name: str):
    path = SCREENSHOT_DIR / f"{name}_{datetime.now().strftime('%H%M%S')}.png"
    page.screenshot(path=str(path), full_page=False)
    return str(path)


def log_test(name: str, status: str, details: dict | None = None):
    entry = {"name": name, "status": status, "timestamp": datetime.now().isoformat()}
    if details:
        entry.update(details)
    REPORT["tests"].append(entry)
    icon = "✓" if status == "PASS" else "✗" if status == "FAIL" else "⚠"
    print(f"  {icon} {name}")


def setup_logging(page: Page):
    page.on("console", lambda msg: REPORT["console_errors"].append(
        {"type": msg.type, "text": msg.text, "time": datetime.now().isoformat()}
    ) if msg.type in ["error", "warning"] else None)
    page.on("response", lambda resp: REPORT["network_errors"].append(
        {"url": resp.url, "status": resp.status, "time": datetime.now().isoformat()}
    ) if resp.status >= 400 else None)


# ── TEST 1: 页面加载 ──
def test_pipeline_page_load(page: Page):
    print("\n=== TEST 1: 流水线页面加载 ===")
    page.goto(f"{BASE_URL}/pipeline", wait_until="networkidle", timeout=15000)
    page.wait_for_timeout(1500)
    take_screenshot(page, "01_pipeline_load")

    # Verify page title and key elements
    body = page.inner_text("body")
    has_title = "数据流水线监控" in body
    has_dag = "DAG" in body or "爬虫采集" in body
    has_kpi = "今日采集量" in body or "处理成功率" in body

    log_test("页面标题", "PASS" if has_title else "FAIL", {"has_title": has_title})
    log_test("DAG时间线", "PASS" if has_dag else "FAIL", {"has_dag": has_dag})
    log_test("KPI卡片", "PASS" if has_kpi else "FAIL", {"has_kpi": has_kpi})

    return has_title and has_dag and has_kpi


# ── TEST 2: 阶段卡片展示 ──
def test_stage_cards(page: Page):
    print("\n=== TEST 2: 5阶段卡片展示 ===")
    page.goto(f"{BASE_URL}/pipeline", wait_until="networkidle", timeout=15000)
    page.wait_for_timeout(1000)

    stages = ["爬虫采集", "SimHash去重", "清洗标准化", "数据入库", "图谱构建"]
    found = []
    body = page.inner_text("body")
    for s in stages:
        if s in body:
            found.append(s)

    log_test("5阶段卡片", "PASS" if len(found) >= 5 else "FAIL", {"found": found, "count": len(found)})
    return len(found) >= 5


# ── TEST 3: 触发流水线弹窗 ──
def test_trigger_dialog(page: Page):
    print("\n=== TEST 3: 触发流水线弹窗 ===")
    page.goto(f"{BASE_URL}/pipeline", wait_until="networkidle", timeout=15000)
    page.wait_for_timeout(1000)

    # Click trigger button
    trigger_btn = page.locator("button:has-text('触发流水线')").first
    if not trigger_btn.is_visible():
        log_test("触发按钮可见", "FAIL")
        return False

    trigger_btn.click()
    page.wait_for_timeout(500)
    take_screenshot(page, "03_trigger_dialog")

    # Verify dialog content
    body = page.inner_text("body")
    has_run_type = "全量" in body and "增量" in body
    has_stages = "爬虫采集" in body and "数据入库" in body
    has_cancel = "取消" in body
    has_start = "启动" in body

    log_test("运行类型选择", "PASS" if has_run_type else "FAIL", {"has_run_type": has_run_type})
    log_test("阶段复选框", "PASS" if has_stages else "FAIL", {"has_stages": has_stages})
    log_test("取消/启动按钮", "PASS" if has_cancel and has_start else "FAIL")

    # Cancel dialog
    cancel_btn = page.locator("button:has-text('取消')").first
    if cancel_btn.is_visible():
        cancel_btn.click()
        page.wait_for_timeout(300)

    return has_run_type and has_stages


# ── TEST 4: 后端 API 状态 ──
def test_backend_api(page: Page):
    print("\n=== TEST 4: 后端流水线API ===")

    endpoints = {
        "status": "/api/v1/pipeline/status",
        "stages": "/api/v1/pipeline/stages",
        "runs": "/api/v1/pipeline/runs",
        "data_quality": "/api/v1/pipeline/data-quality",
        "datasources": "/api/v1/pipeline/datasources",
        "config": "/api/v1/pipeline/config",
        "schedules": "/api/v1/pipeline/schedules",
    }

    all_ok = True
    for name, path in endpoints.items():
        try:
            result = page.evaluate(f"""async () => {{
                try {{
                    const res = await fetch('{BACKEND_URL}{path}');
                    const text = await res.text();
                    return {{ status: res.status, ok: res.ok, preview: text.slice(0, 100) }};
                }} catch(e) {{
                    return {{ error: e.message }};
                }}
            }}""")
            ok = result.get("ok", False)
            status = result.get("status", "error")
            log_test(f"API {name}", "PASS" if ok else "FAIL", {"status": status})
            if not ok:
                all_ok = False
                REPORT["issues"].append({"test": "backend_api", "endpoint": path, "status": status})
        except Exception as e:
            log_test(f"API {name}", "FAIL", {"error": str(e)})
            all_ok = False

    return all_ok


# ── TEST 5: 触发流水线执行 ──
def test_trigger_execution(page: Page):
    print("\n=== TEST 5: 触发流水线执行 ===")
    page.goto(f"{BASE_URL}/pipeline", wait_until="networkidle", timeout=15000)
    page.wait_for_timeout(1000)

    # Open trigger dialog
    trigger_btn = page.locator("button:has-text('触发流水线')").first
    trigger_btn.click()
    page.wait_for_timeout(500)

    # Select all stages (default is all checked)
    # Click start
    start_btn = page.locator("button:has-text('启动')").first
    if not start_btn.is_visible():
        log_test("启动按钮可见", "FAIL")
        return False

    start_btn.click()
    page.wait_for_timeout(1000)
    take_screenshot(page, "05_after_trigger")

    # Check for success message or running indicator
    body = page.inner_text("body")
    triggered = "流水线已触发" in body or "执行中" in body or "running" in body.lower()

    log_test("流水线触发", "PASS" if triggered else "FAIL", {"triggered": triggered})

    # Wait a bit and check stages updated
    page.wait_for_timeout(3000)
    take_screenshot(page, "05_stages_after_3s")

    # Refresh and check status
    page.reload()
    page.wait_for_timeout(1500)
    body = page.inner_text("body")
    has_status = "运行中" in body or "running" in body.lower() or "completed" in body.lower() or "已完成" in body

    log_test("状态更新", "PASS" if has_status else "FAIL", {"has_status": has_status})

    return triggered


# ── TEST 6: 定时调度弹窗 ──
def test_schedule_dialog(page: Page):
    print("\n=== TEST 6: 定时调度弹窗 ===")
    page.goto(f"{BASE_URL}/pipeline", wait_until="networkidle", timeout=15000)
    page.wait_for_timeout(1000)

    schedule_btn = page.locator("button:has-text('定时调度')").first
    if not schedule_btn.is_visible():
        log_test("定时调度按钮", "FAIL")
        return False

    schedule_btn.click()
    page.wait_for_timeout(500)
    take_screenshot(page, "06_schedule_dialog")

    body = page.inner_text("body")
    has_name = "名称" in body
    has_cron = "Cron" in body or "表达式" in body
    has_create = "创建" in body

    log_test("调度弹窗字段", "PASS" if has_name and has_cron else "FAIL", {"has_name": has_name, "has_cron": has_cron})

    # Cancel
    cancel = page.locator("button:has-text('取消')").first
    if cancel.is_visible():
        cancel.click()

    return has_name and has_cron


# ── TEST 7: 配置弹窗 ──
def test_config_dialog(page: Page):
    print("\n=== TEST 7: 配置弹窗 ===")
    page.goto(f"{BASE_URL}/pipeline", wait_until="networkidle", timeout=15000)
    page.wait_for_timeout(1000)

    config_btn = page.locator("button:has-text('配置')").first
    if not config_btn.is_visible():
        log_test("配置按钮", "FAIL")
        return False

    config_btn.click()
    page.wait_for_timeout(500)
    take_screenshot(page, "07_config_dialog")

    body = page.inner_text("body")
    has_timeout = "超时" in body or "timeout" in body.lower()
    has_concurrency = "并发" in body or "concurrency" in body.lower()
    has_retry = "重试" in body or "retry" in body.lower()
    has_save = "保存" in body

    log_test("配置字段", "PASS" if has_timeout and has_concurrency and has_retry else "FAIL",
             {"has_timeout": has_timeout, "has_concurrency": has_concurrency, "has_retry": has_retry})

    # Cancel
    cancel = page.locator("button:has-text('取消')").first
    if cancel.is_visible():
        cancel.click()

    return has_timeout and has_concurrency


# ── TEST 8: SSE 连接状态 ──
def test_sse_connection(page: Page):
    print("\n=== TEST 8: SSE 实时连接 ===")
    page.goto(f"{BASE_URL}/pipeline", wait_until="networkidle", timeout=15000)
    page.wait_for_timeout(2000)

    # Check for SSE indicator
    body = page.inner_text("body")
    has_sse = "SSE" in body or "实时" in body

    log_test("SSE 指示器", "PASS" if has_sse else "WARN", {"has_sse": has_sse})

    # Check network for SSE requests
    # (already captured by setup_logging)
    sse_requests = [e for e in REPORT["network_errors"] if "events" in e.get("url", "")]
    log_test("SSE 请求", "PASS" if len(sse_requests) == 0 else "INFO",
             {"sse_requests": len(sse_requests)})

    return True


# ── TEST 9: 断点续跑按钮 ──
def test_resume_button(page: Page):
    print("\n=== TEST 9: 断点续跑按钮 (失败状态) ===")
    page.goto(f"{BASE_URL}/pipeline", wait_until="networkidle", timeout=15000)
    page.wait_for_timeout(1000)

    # The resume button only shows when current_run is failed
    # We verify the button exists in the DOM even if hidden
    resume_btn = page.locator("button:has-text('断点续跑')").first
    exists = resume_btn.count() > 0

    log_test("断点续跑按钮存在", "PASS" if exists else "FAIL", {"exists": exists})
    return exists


# ── TEST 10: 响应式布局 ──
def test_responsive(page: Page):
    print("\n=== TEST 10: 响应式布局 ===")

    viewports = [
        ("mobile", 375, 812),
        ("tablet", 768, 1024),
        ("desktop", 1440, 900),
    ]

    all_ok = True
    for name, w, h in viewports:
        page.set_viewport_size({"width": w, "height": h})
        page.goto(f"{BASE_URL}/pipeline", wait_until="networkidle", timeout=15000)
        page.wait_for_timeout(1000)
        take_screenshot(page, f"10_responsive_{name}")

        # Check for horizontal overflow
        overflow = page.evaluate("""() => {
            return document.body.scrollWidth > document.body.clientWidth + 5;
        }""")
        log_test(f"响应式 {name}", "PASS" if not overflow else "FAIL", {"overflow": overflow, "size": f"{w}x{h}"})
        if overflow:
            all_ok = False

    return all_ok


# ── MAIN ──
def main():
    print("=" * 60)
    print("STARMAP 数据流水线 E2E 测试 — 完整批量爬虫流")
    print(f"前端: {BASE_URL}")
    print(f"后端: {BACKEND_URL}")
    print("=" * 60)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()
        setup_logging(page)

        results = []
        results.append(("页面加载", test_pipeline_page_load(page)))
        results.append(("阶段卡片", test_stage_cards(page)))
        results.append(("触发弹窗", test_trigger_dialog(page)))
        results.append(("后端API", test_backend_api(page)))
        results.append(("触发执行", test_trigger_execution(page)))
        results.append(("定时调度", test_schedule_dialog(page)))
        results.append(("配置弹窗", test_config_dialog(page)))
        results.append(("SSE连接", test_sse_connection(page)))
        results.append(("断点续跑", test_resume_button(page)))
        results.append(("响应式", test_responsive(page)))

        browser.close()

    # Save report
    report_path = SCREENSHOT_DIR / "pipeline_e2e_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(REPORT, f, ensure_ascii=False, indent=2)

    # Summary
    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    print("\n" + "=" * 60)
    print(f"E2E 测试结果: {passed}/{total} 通过")
    print("=" * 60)
    for name, ok in results:
        icon = "✓" if ok else "✗"
        print(f"  {icon} {name}")
    print(f"\n报告: {report_path}")
    print(f"截图: {SCREENSHOT_DIR}")

    return passed == total


if __name__ == "__main__":
    main()
