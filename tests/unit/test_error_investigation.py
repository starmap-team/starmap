# -*- coding: utf-8 -*-
"""
Phase 6: 排查报错及非预期功能
======================
覆盖范围:
 1. 所有页面加载时的控制台错误收集
 2. API 错误率扫描
 3. 页面空白 / 渲染异常检测
 4. 响应式布局检查
 5. 组件交互异常检测
 6. 后端 4xx/5xx 状态码扫描

前置条件: dev server (localhost:5173) + backend (localhost:8001) 已运行
"""
import json
import os
import time
import urllib.request
import urllib.error

BASE_URL = "http://localhost:5173"
API_BASE = "http://localhost:8000/api/v1"
SCREENSHOT_DIR = "test-screenshots"

# ── 页面清单 ──
ALL_PAGES = [
 {"name": "home", "path": "/"},
 {"name": "dashboard", "path": "/dashboard"},
 {"name": "positions", "path": "/positions"},
 {"name": "match", "path": "/match"},
 {"name": "extract", "path": "/extract"},
 {"name": "evolution", "path": "/evolution"},
 {"name": "quality", "path": "/quality"},
 {"name": "pipeline", "path": "/pipeline"},
 {"name": "datasources", "path": "/datasources"},
 {"name": "admin", "path": "/admin"},
 {"name": "loop-demo", "path": "/loop"},
 {"name": "learning", "path": "/learning"},
 # 可能不存在的页面
 {"name": "login", "path": "/login", "optional": True},
 {"name": "settings", "path": "/settings", "optional": True},
]

# ── API 端点清单 ──
API_ENDPOINTS = [
 "/pipeline/config",
 "/pipeline/status",
 "/pipeline/stages",
 "/pipeline/datasources",
 "/pipeline/schedules",
 "/pipeline/data-quality",
 "/admin/sources",
 "/admin/graph/nodes",
 "/admin/review-queue",
 "/admin/stats",
 "/graph/nodes",
 "/position/list",
 "/extract/jd",
 "/match/analyze",
]

# ── 404 / 异常页面检查 ──
URI_PATTERNS = [
 "/nonexistent-page",
 "/api/v1/nonexistent-endpoint",
]

def api_get(path: str) -> tuple[int, str | None]:
 """调用 API 并返回 (status_code, error_message)。"""
 try:
 url = f"{API_BASE}{path}"
 req = urllib.request.Request(url)
 with urllib.request.urlopen(req, timeout=10) as resp:
 return resp.status, None
 except urllib.error.HTTPError as e:
 body = e.read.decode("utf-8", errors="replace")[:200]
 return e.code, body
 except Exception as e:
 return 0, str(e)

def check_page(page, page_info):
 """检查页面加载情况：状态码、控制台错误、内容空白检测。"""
 name = page_info["name"]
 path = page_info["path"]
 optional = page_info.get("optional", False)

 result = {
 "name": name,
 "path": path,
 "status": "PASS",
 "http_status": 0,
 "console_errors": [],
 "content_length": 0,
 "warnings": [],
 }

 console_errors = []
 page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
 page.on("pageerror", lambda err: console_errors.append(f"PAGE_CRASH: {err}"))

 try:
 response = page.goto(f"{BASE_URL}{path}", wait_until="domcontentloaded", timeout=20000)
 time.sleep(2)

 http_status = response.status if response else 0
 result["http_status"] = http_status

 if http_status >= 400:
 result["warnings"].append(f"HTTP {http_status}")
 result["status"] = "WARN" if optional else "FAIL"
 elif optional and http_status == 0:
 result["warnings"].append("页面不可达 (可选)")
 result["status"] = "SKIP"

 # 检查页面内容
 try:
 body = page.inner_text("body")
 result["content_length"] = len(body.strip)
 except Exception:
 result["content_length"] = 0

 if result["content_length"] < 30 and http_status < 400:
 result["warnings"].append(f"页面内容过短: {result['content_length']} 字符")
 result["status"] = "WARN"

 # 收集控制台错误
 result["console_errors"] = console_errors[:10]

 except Exception as e:
 result["warnings"].append(f"加载异常: {str(e)[:100]}")
 result["status"] = "WARN" if optional else "FAIL"

 return result

def test_all_pages_console_errors(page):
 """测试 1: 扫描所有页面的控制台错误。"""
 name = "test_console_errors"
 print(f"\n{'=' * 60}")
 print(f"[SCAN] {name}: 扫描 {len(ALL_PAGES)} 个页面的控制台错误")
 print(f"{'=' * 60}")

 results = {"name": name, "checks": [], "errors": [], "pages": [], "total_errors": 0}

 for page_info in ALL_PAGES:
 pr = check_page(page, page_info)
 results["pages"].append(pr)

 err_count = len(pr["console_errors"])
 if err_count > 0:
 results["total_errors"] += err_count
 print(f" [{pr['status']}] {pr['name']}: {err_count} console errors")
 for err in pr["console_errors"][:3]:
 print(f" - {err[:120]}")
 results["errors"].append(f"[{pr['name']}] {err[:200]}")
 else:
 print(f" [OK] {pr['name']}: clean (status={pr['http_status']})")
 results["checks"].append(f"{pr['name']}: 无错误")

 print(f"\n 总计错误: {results['total_errors']}")
 results["status"] = "PASS" if results["total_errors"] == 0 else "FAIL"
 print(f" >>> {results['status']}")
 return results

def test_api_error_scan:
 """测试 2: 扫描 API 端点错误率。"""
 name = "test_api_errors"
 print(f"\n{'=' * 60}")
 print(f"[SCAN] {name}: 扫描 {len(API_ENDPOINTS)} 个 API 端点")
 print(f"{'=' * 60}")

 results = {"name": name, "checks": [], "errors": [], "endpoints": []}

 for endpoint in API_ENDPOINTS:
 status, err_body = api_get(endpoint)
 entry = {"path": endpoint, "status": status}
 results["endpoints"].append(entry)

 if status == 0:
 results["errors"].append(f"[ERR] {endpoint}: 连接失败")
 print(f" [ERR] {endpoint}: 连接失败")
 elif status >= 500:
 results["errors"].append(f"[{status}] {endpoint}: 服务器错误")
 print(f" [{status}] {endpoint}: 服务器错误")
 if err_body:
 print(f" -> {err_body[:150]}")
 elif status == 404:
 results["errors"].append(f"[404] {endpoint}: 端点不存在")
 print(f" [404] {endpoint}: 端点不存在")
 elif status == 422:
 results["checks"].append(f"[422] {endpoint}: 参数错误 (可能是需要额外参数)")
 print(f" [422] {endpoint}: 参数错误 (预期)")
 elif status == 200 or status == 204:
 results["checks"].append(f"[{status}] {endpoint}: OK")
 print(f" [OK] {endpoint}: {status}")
 else:
 results["checks"].append(f"[{status}] {endpoint}: 其他")
 print(f" [{status}] {endpoint}: {status}")

 ok_count = sum(1 for e in results["endpoints"] if e["status"] in (200, 204, 422))
 err_count = sum(1 for e in results["endpoints"] if e["status"] >= 500 or e["status"] == 0)
 print(f"\n 正常: {ok_count}, 错误: {err_count}")

 if err_count > 0:
 print(" [WARN] 存在后端 API 错误 (可能是数据库未启动)")
 results["status"] = "PASS" if err_count == 0 else "DEGRADED"
 print(f" >>> {results['status']}")
 return results

def test_404_handling(page):
 """测试 3: 页面 404 错误处理和路由守卫。"""
 name = "test_404_handling"
 print(f"\n{'=' * 60}")
 print(f"[SCAN] {name}: 路由守卫和 404 处理")
 print(f"{'=' * 60}")

 results = {"name": name, "checks": [], "errors": [], "console_errors": []}
 console_errors = []
 page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

 try:
 for uri in URI_PATTERNS:
 response = page.goto(f"{BASE_URL}{uri}", wait_until="domcontentloaded", timeout=15000)
 time.sleep(2)

 http_status = response.status if response else 0
 page_text = page.inner_text("body")

 if http_status < 400:
 # 前端 SPA 不会有真正的 404，检查是否有自定义 404 页面
 if "404" in page_text or "不存在" in page_text or "未找到" in page_text or "not found" in page_text.lower:
 results["checks"].append(f"[{uri}] 自定义 404 页面: '{page_text[:60].strip}'")
 print(f" [OK] [{uri}] 自定义 404 页面")
 else:
 results["checks"].append(f"[{uri}] 无 404 页面（SPA 回退到根路由）")
 print(f" [OK] [{uri}] SPA 路由回退")
 else:
 results["checks"].append(f"[{uri}] HTTP {http_status}")
 print(f" [OK] [{uri}] HTTP {http_status}")

 page.screenshot(path=f"{SCREENSHOT_DIR}/{name}_{uri.replace('/', '_')}.png", full_page=True)

 # 检查 SPA 路由是否处理了所有路径
 page.goto(f"{BASE_URL}/admin", wait_until="domcontentloaded", timeout=15000)
 time.sleep(2)
 admin_title = page.locator("h2:has-text('管理后台')")
 if admin_title.count > 0:
 results["checks"].append("SPA 路由正常: /admin")
 print(" [OK] SPA 路由正常: /admin")

 except Exception as e:
 results["errors"].append(f"异常: {str(e)[:200]}")

 results["console_errors"] = console_errors[:10]
 results["status"] = "PASS" if not results["errors"] else "FAIL"
 print(f" >>> {results['status']}")
 return results

def test_visual_anomalies(page):
 """测试 4: 视觉异常检测 - 空容器、重叠元素、加载态卡死。"""
 name = "test_visual_anomalies"
 print(f"\n{'=' * 60}")
 print(f"[SCAN] {name}: 视觉异常检测")
 print(f"{'=' * 60}")

 results = {"name": name, "checks": [], "errors": [], "console_errors": []}

 pages_to_check = [
 {"name": "home", "path": "/", "min_content": 50},
 {"name": "pipeline", "path": "/pipeline", "min_content": 200},
 {"name": "admin", "path": "/admin", "min_content": 100},
 {"name": "datasources", "path": "/datasources", "min_content": 50},
 {"name": "positions", "path": "/positions", "min_content": 50},
 ]

 console_errors_all = []
 page.on("console", lambda msg: console_errors_all.append(msg.text) if msg.type == "error" else None)
 page.on("pageerror", lambda err: console_errors_all.append(f"PAGE_CRASH: {err}"))

 for p in pages_to_check:
 try:
 response = page.goto(f"{BASE_URL}{p['path']}", wait_until="domcontentloaded", timeout=15000)
 time.sleep(2)

 # 页面内容检测
 body = page.inner_text("body")
 content_len = len(body.strip)
 http_status = response.status if response else 0

 if http_status >= 400:
 results["errors"].append(f"[{p['name']}] HTTP {http_status}")
 print(f" [ERR] {p['name']}: HTTP {http_status}")
 continue

 if content_len < p["min_content"]:
 results["errors"].append(f"[{p['name']}] 内容过少: {content_len} < {p['min_content']}")
 print(f" [WARN] {p['name']}: 内容过少 {content_len} 字符")
 else:
 results["checks"].append(f"{p['name']}: {content_len} 字符")
 print(f" [OK] {p['name']}: {content_len} 字符")

 # 检测 v-loading 卡死
 loading = page.locator(".el-loading-mask")
 if loading.count > 0:
 results["warn"] = f"[{p['name']}] 存在加载遮罩 (可能卡死)"
 print(f" [WARN] {p['name']}: 存在加载遮罩")

 except Exception as e:
 results["errors"].append(f"[{p['name']}] 异常: {str(e)[:100]}")
 print(f" [ERR] {p['name']}: {str(e)[:100]}")

 results["console_errors"] = console_errors_all[:15]
 if console_errors_all:
 print(f"\n 总控制台错误: {len(console_errors_all)}")
 for err in console_errors_all[:5]:
 print(f" - {err[:150]}")

 results["status"] = "PASS" if not results["errors"] else "FAIL"
 print(f" >>> {results['status']}")
 return results

def api_get_data(path: str) -> dict | list | None:
 """调用 backend API 返回 JSON 数据。"""
 try:
 url = f"{API_BASE}{path}"
 req = urllib.request.Request(url)
 with urllib.request.urlopen(req, timeout=10) as resp:
 return json.loads(resp.read.decode)
 except Exception as e:
 print(f" [API] GET {path} 失败: {e}")
 return None

def test_api_data_consistency:
 """测试 5: API 数据一致性和字段完整性。"""
 name = "test_api_data_consistency"
 print(f"\n{'=' * 60}")
 print(f"[SCAN] {name}: API 数据一致性检查")
 print(f"{'=' * 60}")

 results = {"name": name, "checks": [], "errors": []}

 # 检查 get_pipeline_config 的必填字段
 config = api_get_data("/pipeline/config")
 if config and isinstance(config, dict):
 required = ["stage_timeout", "worker_concurrency", "crawl_concurrency", "retry_max", "retry_backoff"]
 missing = [f for f in required if f not in config]
 if missing:
 results["errors"].append(f"config 缺少字段: {missing}")
 else:
 # 检查字段类型和范围
 if not isinstance(config.get("stage_timeout"), (int, float)) or config["stage_timeout"] <= 0:
 results["errors"].append("stage_timeout 不是正整数")
 if not isinstance(config.get("worker_concurrency"), (int, float)) or config["worker_concurrency"] < 1:
 results["errors"].append("worker_concurrency 无效")
 results["checks"].append("config 字段完整且类型正确")
 print(" [OK] config 字段完整且类型正确")
 elif config is None:
 results["errors"].append("config API 不可用")
 else:
 results["errors"].append("config 返回格式异常")

 # 检查 datasource list
 sources = api_get_data("/admin/sources")
 if sources and isinstance(sources, dict):
 items = sources.get("items", [])
 if items:
 required_source_fields = ["name", "source_type", "authority_score"]
 for item in items[:3]:
 missing = [f for f in required_source_fields if f not in item]
 if missing:
 results["errors"].append(f"数据源缺少字段: {missing}")
 results["checks"].append(f"数据源列表: {len(items)} 条")
 print(f" [OK] 数据源列表: {len(items)} 条")

 # 检查 pipeline stages 结构
 stages = api_get_data("/pipeline/stages")
 if stages:
 if isinstance(stages, dict) and "stages" in stages:
 stages_list = stages["stages"]
 elif isinstance(stages, list):
 stages_list = stages
 else:
 stages_list = []
 
 if stages_list:
 required_stage_fields = ["name", "status", "progress"]
 for stage in stages_list[:3]:
 missing = [f for f in required_stage_fields if f not in stage]
 if missing:
 results["errors"].append(f"阶段缺少字段: {missing}")
 results["checks"].append(f"阶段列表: {len(stages_list)} 条")
 print(f" [OK] 阶段列表: {len(stages_list)} 条")

 result_count = len(results["checks"])
 error_count = len(results["errors"])
 print(f" 检查: {result_count}, 错误: {error_count}")
 results["status"] = "PASS" if error_count == 0 else "FAIL"
 print(f" >>> {results['status']}")
 return results

def test_responsive_layout(page):
 """测试 6: 响应式布局检查 - 小屏幕下页面是否正常。"""
 name = "test_responsive_layout"
 print(f"\n{'=' * 60}")
 print(f"[SCAN] {name}: 响应式布局检查")
 print(f"{'=' * 60}")

 results = {"name": name, "checks": [], "errors": [], "console_errors": []}
 console_errors = []
 page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

 viewports = [
 {"name": "desktop", "width": 1920, "height": 1080},
 {"name": "laptop", "width": 1366, "height": 768},
 {"name": "tablet", "width": 768, "height": 1024},
 {"name": "mobile", "width": 375, "height": 667},
 ]

 pages_to_test = ["/", "/pipeline", "/admin"]

 for vp in viewports:
 page.set_viewport_size({"width": vp["width"], "height": vp["height"]})
 for path in pages_to_test:
 try:
 page.goto(f"{BASE_URL}{path}", wait_until="domcontentloaded", timeout=15000)
 time.sleep(2)

 # 检查页面是否可见
 body = page.inner_text("body")
 if len(body.strip) < 30:
 results["errors"].append(f"[{vp['name']}] {path}: 页面空白")
 print(f" [ERR] {vp['name']} {path}: 页面空白")
 else:
 results["checks"].append(f"[{vp['name']}] {path}: {len(body.strip)} 字符")
 print(f" [OK] {vp['name']} {path}: {len(body.strip)} 字符")

 page.screenshot(path=f"{SCREENSHOT_DIR}/{name}_{vp['name']}_{path.replace('/', '_')}.png", full_page=True)

 except Exception as e:
 results["errors"].append(f"[{vp['name']}] {path}: {str(e)[:80]}")
 print(f" [ERR] {vp['name']} {path}: {str(e)[:80]}")

 results["console_errors"] = console_errors[:10]
 results["status"] = "PASS" if not results["errors"] else "FAIL"
 print(f" >>> {results['status']}")
 return results

# ============================================================
# 主函数
# ============================================================

def main:
 os.makedirs(SCREENSHOT_DIR, exist_ok=True)

 print(f'\n{"=" * 60}')
 print("StarMap 错误排查 & 非预期功能测试")
 print(f"Base URL: {BASE_URL}")
 print(f"API Base: {API_BASE}")
 print(f'{"=" * 60}')

 all_results = []

 # API 测试（无浏览器）
 all_results.append(test_api_error_scan)
 all_results.append(test_api_data_consistency)

 # 检查前端状态
 try:
 req = urllib.request.Request(BASE_URL)
 with urllib.request.urlopen(req, timeout=5) as resp:
 pass
 frontend_ok = True
 except Exception:
 frontend_ok = False

 if not frontend_ok:
 print(f"\n [SKIP] 前端 {BASE_URL} 不可用")
 else:
 try:
 from playwright.sync_api import sync_playwright
 except ImportError:
 print("\n [SKIP] 未安装 playwright")
 print_result(all_results)
 return False

 ui_tests = [
 ("控制台错误扫描", test_all_pages_console_errors),
 ("404路由处理", test_404_handling),
 ("视觉异常检测", test_visual_anomalies),
 ("响应式布局", test_responsive_layout),
 ]

 with sync_playwright as p:
 browser = p.chromium.launch(headless=True)
 context = browser.new_context(
 viewport={"width": 1920, "height": 1080},
 ignore_https_errors=True,
 )

 for test_name, test_fn in ui_tests:
 page = context.new_page
 result = test_fn(page)
 all_results.append(result)
 page.close

 browser.close

 print_result(all_results)
 passed = sum(1 for r in all_results if r["status"] == "PASS")
 return passed == len(all_results)

def print_result(all_results):
 print(f'\n{"=" * 60}')
 print("错误排查 - 测试结果汇总")
 print(f'{"=" * 60}')

 passed = sum(1 for r in all_results if r["status"] == "PASS")
 degraded = sum(1 for r in all_results if r["status"] == "DEGRADED")
 failed = sum(1 for r in all_results if r["status"] == "FAIL")

 print(f"\n总计: {len(all_results)} | 通过: {passed} | 降级: {degraded} | 失败: {failed}")
 print(f"通过率: {passed / len(all_results) * 100:.1f}%\n")

 print(f'{"测试项":<35} {"状态":<10} {"信息"}')
 print("-" * 80)

 for r in all_results:
 checks_count = len(r.get("checks", []))
 errors_count = len(r.get("errors", []))
 cerr = f' ({len(r.get("console_errors", []))} console err)' if r.get("console_errors") else ""
 info = f"{checks_count} checks, {errors_count} errors{cerr}"
 print(f'{r["name"]:<35} {r["status"]:<10} {info}')

 failures = [r for r in all_results if r["status"] == "FAIL"]
 if failures:
 print(f'\n{"=" * 60}')
 print("失败详情")
 print(f'{"=" * 60}')
 for r in failures:
 print(f'\n {r["name"]}')
 for err in r.get("errors", [])[:5]:
 print(f" - {err}")

 print(f'\n截图目录: {os.path.abspath(SCREENSHOT_DIR)}')
 print(f'{"=" * 60}\n')

if __name__ == "__main__":
 success = main
 exit(0 if success else 1)
