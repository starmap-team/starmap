"""
StarMap UX 巡检 — 用 Playwright 逐页截图 + 收集 console errors/network failures。
输出 tests/e2e/investigations/ux/ux_audit.json + 截图。
"""
from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE_URL = "http://localhost:5173"
OUTPUT_DIR = Path(__file__).parent / "investigations" / "ux"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 主页面巡检（按用户实际使用顺序）
PAGES = [
    ("home", "/", "全景图谱"),
    ("positions", "/positions", "岗位列表"),
    ("position_detail", "/position/AI产品经理", "岗位详情"),
    ("match", "/match", "匹配诊断"),
    ("extract", "/extract", "JD抽取"),
    ("loop", "/loop", "闭环演示"),
    ("evolution", "/evolution", "演化看板"),
    ("quality", "/quality", "图谱质量"),
    ("pipeline", "/pipeline", "数据流水线"),
    ("datasources", "/datasources", "数据源管理"),
    ("dashboard", "/dashboard", "数据大屏"),
    ("learning", "/learning", "学习中心"),
    ("admin_overview", "/admin", "管理后台"),
    ("admin_review", "/admin", "管理后台·内容审核"),  # 单独 tab
]


def audit():
    issues = []
    pages_visited = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1920, "height": 1080})

        # 收集所有 console errors 和 network failures
        all_console_errors = []
        all_failed_requests = []

        def on_console(msg):
            if msg.type in ("error", "warning"):
                all_console_errors.append({
                    "page": "current",
                    "type": msg.type,
                    "text": msg.text[:300],
                })

        def on_requestfailed(request):
            all_failed_requests.append({
                "page": "current",
                "url": request.url[:200],
                "failure": (request.failure or "unknown")[:200],
                "method": request.method,
            })

        page = context.new_page()
        page.on("console", on_console)
        page.on("requestfailed", on_requestfailed)

        # 登录
        print("[LOGIN]")
        page.goto(f"{BASE_URL}/login")
        page.wait_for_load_state("domcontentloaded", timeout=15000)
        page.fill("input[type='text'], input[name='username']", "admin")
        page.fill("input[type='password']", "starmap2024")
        page.click("button[type='submit']")
        time.sleep(3)

        if "/login" in page.url:
            issues.append({"severity": "critical", "page": "login", "issue": "登录失败"})
            print("[FATAL] 登录失败")
            browser.close()
            return issues

        for slug, route, display_name in PAGES:
            print(f"[VISIT] {display_name} ({route})")
            all_console_errors.clear()
            all_failed_requests.clear()

            try:
                page.goto(f"{BASE_URL}{route}", timeout=20000)
                page.wait_for_load_state("domcontentloaded", timeout=15000)
                time.sleep(2)

                # 截图
                page.screenshot(path=str(OUTPUT_DIR / f"{slug}.png"), full_page=True)

                # 检测错误边界
                content = page.content()
                has_error_boundary = "error-boundary" in content and "页面出现错误" in content

                # 检测骨架卡住（超过 5 个 skeleton 表示加载失败）
                skeletons = page.locator(".el-skeleton, .skeleton, .loading-pulse").all()
                visible_skeletons = [s for s in skeletons if s.is_visible()]

                # 检测空状态
                empty_states = page.locator(".el-empty, .empty-state").all()
                visible_empty = [e for e in empty_states if e.is_visible()]

                # 检测加载失败提示
                error_messages = page.locator(".el-message--error").all()
                visible_errors = [e for e in error_messages if e.is_visible()]

                page_info = {
                    "slug": slug,
                    "route": route,
                    "name": display_name,
                    "url": page.url,
                    "title": page.title(),
                    "has_error_boundary": has_error_boundary,
                    "stuck_skeletons": len(visible_skeletons),
                    "empty_states": len(visible_empty),
                    "visible_error_messages": len(visible_errors),
                    "console_errors": list(all_console_errors),
                    "failed_requests": list(all_failed_requests),
                }
                pages_visited.append(page_info)

                if has_error_boundary:
                    issues.append({"severity": "critical", "page": display_name, "issue": "ErrorBoundary 触发"})
                if len(visible_skeletons) > 3:
                    issues.append({"severity": "warning", "page": display_name, "issue": f"数据加载失败 ({len(visible_skeletons)} skeleton 未消失)"})
                if all_console_errors:
                    issues.append({"severity": "warning", "page": display_name, "issue": f"Console {len(all_console_errors)} 条错误", "details": all_console_errors[:3]})
                if all_failed_requests:
                    issues.append({"severity": "warning", "page": display_name, "issue": f"网络 {len(all_failed_requests)} 个失败请求", "details": all_failed_requests[:3]})

            except Exception as e:
                issues.append({"severity": "critical", "page": display_name, "issue": f"页面加载异常: {e}"})
                try:
                    page.screenshot(path=str(OUTPUT_DIR / f"{slug}_ERROR.png"))
                except Exception:
                    pass

        browser.close()

    # 保存报告
    report = {
        "timestamp": datetime.now().isoformat(),
        "total_pages": len(PAGES),
        "pages_visited": len(pages_visited),
        "issues_count": len(issues),
        "issues": issues,
        "page_details": pages_visited,
    }
    with open(OUTPUT_DIR / "ux_audit.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n=== UX 巡检报告 ===")
    print(f"页面: {len(pages_visited)}/{len(PAGES)}")
    print(f"问题: {len(issues)}")
    for issue in issues[:20]:
        print(f"  [{issue['severity'].upper()}] {issue['page']}: {issue['issue']}")

    return issues


if __name__ == "__main__":
    audit()