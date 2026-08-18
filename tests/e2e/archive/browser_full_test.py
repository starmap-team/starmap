"""
StarMap 全页面浏览器测试 — 修复后版本
=====================================
使用 Playwright 进行全页面测试，登录后访问所有页面，检查错误。
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path

from e2e_creds import ADMIN_PASSWORD

from playwright.sync_api import sync_playwright

BASE_URL = "http://localhost:5173"
API_BASE = "http://localhost:8000/api/v1"
OUTPUT_DIR = Path(__file__).parent / "browser_qa_screenshots" / "e2e_full_role"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 所有页面清单
PAGES = [
    {"name": "全景图谱", "route": "/", "has_form": False},
    {"name": "岗位列表", "route": "/positions", "has_form": False},
    {"name": "岗位详情", "route": "/position/AI产品经理", "has_form": False},
    {"name": "匹配诊断", "route": "/match", "has_form": True},
    {"name": "演化看板", "route": "/evolution", "has_form": False},
    {"name": "图谱质量", "route": "/quality", "has_form": False},
    {"name": "数据流水线", "route": "/pipeline", "has_form": False},
    {"name": "数据源管理", "route": "/datasources", "has_form": False},
    {"name": "求职者分析", "route": "/analysis", "has_form": False},
    {"name": "JD抽取", "route": "/extract", "has_form": True},
    {"name": "闭环演示", "route": "/loop", "has_form": False},
    {"name": "数据大屏", "route": "/dashboard", "has_form": False},
    {"name": "学习中心", "route": "/learning", "has_form": False},
    {"name": "管理后台", "route": "/admin", "has_form": False},
    {"name": "修改密码", "route": "/change-password", "has_form": True},
]

def test_all_pages():
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1920, "height": 1080})
        page = context.new_page()

        # 登录
        print("[LOGIN] 登录 admin...")
        page.goto(f"{BASE_URL}/login")
        page.wait_for_load_state("networkidle")
        page.fill("input[type='text'], input[name='username']", "admin")
        page.fill("input[type='password']", ADMIN_PASSWORD)
        page.click("button[type='submit']")
        time.sleep(2)

        # 获取 token
        token = page.evaluate("() => localStorage.getItem('starmap_access_token')")
        if token:
            print(f"  [OK] Token: {token[:20]}...")
        else:
            print("  [WARN] No token found")
            page.screenshot(path=str(OUTPUT_DIR / "login_no_token.png"))

        # 测试每个页面
        for p_info in PAGES:
            name = p_info["name"]
            route = p_info["route"]
            print(f"\n[TEST] {name} ({route})")

            try:
                page.goto(f"{BASE_URL}{route}", timeout=20000)
                page.wait_for_load_state("domcontentloaded", timeout=15000)
                time.sleep(2)

                # 截图
                page.screenshot(path=str(OUTPUT_DIR / f"{name}.png"), full_page=True)

                # 获取页面标题
                title = page.title()
                content = page.content()
                has_error = "error-boundary" in content and "页面出现错误" in content

                result = {
                    "name": name,
                    "route": route,
                    "title": title,
                    "has_error_boundary": has_error,
                    "url": page.url,
                }
                results.append(result)
                status = "FAIL" if has_error else "OK"
                print(f"  [{status}] title={title}")

            except Exception as e:
                print(f"  [FAIL] Error: {e}")
                page.screenshot(path=str(OUTPUT_DIR / f"{name}_error.png"))
                results.append({"name": name, "route": route, "error": str(e)})

        browser.close()

    # 保存报告
    report = {
        "timestamp": datetime.now().isoformat(),
        "total": len(results),
        "results": results,
    }
    with open(OUTPUT_DIR / "test_report_v2.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n报告已保存: {OUTPUT_DIR / 'test_report_v2.json'}")

    # 打印摘要
    print(f"\n=== 测试摘要 ===")
    for r in results:
        status = "FAIL" if r.get("has_error_boundary") or r.get("error") else "OK"
        print(f"  {status} {r['name']}")

if __name__ == "__main__":
    test_all_pages()