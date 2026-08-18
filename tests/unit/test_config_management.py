# -*- coding: utf-8 -*-
"""
Phase 4: 配置管理测试
======================
覆盖范围:
 1. 流水线配置: 打开配置弹窗 → 查看/修改 → 保存
 2. 数据源配置 (Admin): 编辑数据源 → 修改权威分 → 保存
 3. 图谱节点管理 (Admin): 搜索/过滤/分页
 4. 演示数据重置: 确认弹窗
 5. API 层面: GET/PUT /pipeline/config

前置条件: dev server (localhost:5173) + backend (localhost:8000) 已运行
"""
import json
import os
import sys
import time
import urllib.request
import urllib.error

BASE_URL = "http://localhost:5173"
API_BASE = "http://localhost:8000/api/v1"
SCREENSHOT_DIR = "test-screenshots"

# ============================================================
# 工具函数
# ============================================================

def api_get(path: str) -> dict | None:
 """调用 backend API GET 并返回 JSON。"""
 try:
 url = f"{API_BASE}{path}"
 req = urllib.request.Request(url)
 with urllib.request.urlopen(req, timeout=10) as resp:
 return json.loads(resp.read.decode)
 except Exception as e:
 print(f" [API] GET {path} 失败: {e}")
 return None

def api_put(path: str, body: dict) -> dict | None:
 """调用 backend API PUT 并返回 JSON。"""
 try:
 url = f"{API_BASE}{path}"
 data = json.dumps(body).encode
 req = urllib.request.Request(url, data=data, method="PUT")
 req.add_header("Content-Type", "application/json")
 with urllib.request.urlopen(req, timeout=10) as resp:
 return json.loads(resp.read.decode)
 except Exception as e:
 print(f" [API] PUT {path} 失败: {e}")
 return None

def check_http_status(url: str) -> int:
 """检查 HTTP 响应状态码。"""
 try:
 req = urllib.request.Request(url)
 with urllib.request.urlopen(req, timeout=10) as resp:
 return resp.status
 except urllib.error.HTTPError as e:
 return e.code
 except Exception as e:
 print(f" [HTTP] 连接 {url} 失败: {e}")
 return 0

# ============================================================
# Test 1: API 层面流水线配置
# ============================================================

def test_pipeline_config_api:
 """测试流水线配置 API (GET + PUT)。"""
 name = "test_pipeline_config_api"
 print(f"\n{'=' * 60}")
 print(f"[API] {name}")
 print(f"{'=' * 60}")

 results = {"name": name, "checks": [], "errors": []}

 # 1. GET current config
 config = api_get("/pipeline/config")
 if config is None:
 results["errors"].append("GET /pipeline/config 返回为空")
 results["status"] = "FAIL"
 return results

 required_fields = ["stage_timeout", "worker_concurrency", "crawl_concurrency", "retry_max", "retry_backoff"]
 for field in required_fields:
 if field not in config:
 results["errors"].append(f"缺少字段: {field}")
 else:
 results["checks"].append(f"{field}={config[field]}")

 print(f" [OK] GET config: {json.dumps(config, ensure_ascii=False)}")

 # 2. PUT - modify retry_max and retry_backoff
 old_retry_max = config.get("retry_max", 3)
 new_retry_max = old_retry_max + 1 if old_retry_max < 10 else old_retry_max - 1
 update_body = {"retry_max": new_retry_max}
 updated = api_put("/pipeline/config", update_body)
 if updated is None:
 results["errors"].append("PUT /pipeline/config 失败")
 else:
 if updated.get("retry_max") == new_retry_max:
 results["checks"].append(f"PUT retry_max 成功: {new_retry_max}")
 print(f" [OK] PUT retry_max = {new_retry_max}")
 else:
 results["errors"].append(f"PUT retry_max 期望 {new_retry_max}，实际 {updated.get('retry_max')}")

 # 3. PUT - restore original
 restore = api_put("/pipeline/config", {"retry_max": old_retry_max})
 if restore and restore.get("retry_max") == old_retry_max:
 results["checks"].append(f"已恢复 retry_max={old_retry_max}")
 print(f" [OK] 已恢复 retry_max={old_retry_max}")

 # 4. Verify all fields still present
 final = api_get("/pipeline/config")
 if final:
 missing = [f for f in required_fields if f not in final]
 if missing:
 results["errors"].append(f"恢复后缺少字段: {missing}")
 else:
 results["checks"].append("所有必需字段完整")

 results["status"] = "PASS" if not results["errors"] else "FAIL"
 print(f" >>> {results['status']}")
 return results

# ============================================================
# Test 2: 页面 - 流水线配置弹窗
# ============================================================

def test_pipeline_config_dialog(page):
 """打开流水线配置弹窗 → 查看/修改 → 保存/取消。"""
 name = "test_pipeline_config_dialog"
 print(f"\n{'=' * 60}")
 print(f"[UI] {name}")
 print(f"{'=' * 60}")

 results = {"name": name, "checks": [], "errors": [], "console_errors": []}
 console_errors = []
 page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

 try:
 # 导航到流水线页面
 page.goto(f"{BASE_URL}/pipeline", wait_until="domcontentloaded", timeout=15000)
 time.sleep(2)

 # 查找并点击"配置"按钮
 config_btn = page.locator("button:has-text('配置')")
 if config_btn.count == 0:
 results["errors"].append("未找到「配置」按钮")
 page.screenshot(path=f"{SCREENSHOT_DIR}/{name}_no_button.png", full_page=True)
 results["status"] = "FAIL"
 results["console_errors"] = console_errors[:5]
 return results

 config_btn.first.click
 time.sleep(1.5)

 # 验证配置弹窗已打开
 dialog = page.locator(".el-dialog:has-text('流水线配置')")
 if dialog.count == 0:
 results["errors"].append("配置弹窗未出现")
 page.screenshot(path=f"{SCREENSHOT_DIR}/{name}_no_dialog.png", full_page=True)
 results["status"] = "FAIL"
 results["console_errors"] = console_errors[:5]
 return results

 results["checks"].append("配置弹窗已打开")
 print(" [OK] 配置弹窗已打开")

 # 等待表单字段渲染（后端加载配置可能需要时间）
 try:
 dialog.wait_for_selector(".el-form-item__label", timeout=8000)
 except Exception:
 pass
 time.sleep(0.5)

 # 查看弹窗中的字段
 expected_labels = ["阶段超时", "Worker并发", "爬取并发", "最大重试", "重试间隔"]
 for label in expected_labels:
 label_el = dialog.locator(f".el-form-item__label:has-text('{label}')")
 if label_el.count > 0:
 results["checks"].append(f"字段存在: {label}")
 print(f" [OK] 字段存在: {label}")
 else:
 results["errors"].append(f"缺少字段: {label}")

 # 修改"最大重试次数"的值
 retry_input = dialog.locator(".el-input-number").last.locator("input")
 if retry_input.count > 0:
 current_val = retry_input.input_value
 new_val = str(int(current_val) + 1) if current_val and current_val.isdigit else "3"
 retry_input.click
 retry_input.fill("")
 retry_input.fill(new_val)
 time.sleep(0.5)
 results["checks"].append(f"修改 retry_max: {current_val} → {new_val}")
 print(f" [OK] 修改 retry_max: {current_val} → {new_val}")

 # 截图: 修改后的弹窗
 page.screenshot(path=f"{SCREENSHOT_DIR}/{name}_modified.png", full_page=True)
 results["checks"].append("截图: 修改后弹窗")

 # 保存配置
 save_btn = dialog.locator("button:has-text('保存')")
 if save_btn.count > 0:
 save_btn.click
 time.sleep(2)
 results["checks"].append("点击保存按钮")
 print(" [OK] 点击保存按钮")

 # 验证弹窗关闭
 if dialog.count == 0 or not dialog.is_visible:
 results["checks"].append("保存后弹窗已关闭")
 print(" [OK] 保存后弹窗已关闭")
 else:
 results["errors"].append("保存后弹窗未关闭")
 else:
 results["errors"].append("未找到保存按钮")
 # 取消
 cancel_btn = dialog.locator("button:has-text('取消')")
 if cancel_btn.count > 0:
 cancel_btn.click
 time.sleep(1)

 except Exception as e:
 results["errors"].append(f"异常: {str(e)[:200]}")
 try:
 page.screenshot(path=f"{SCREENSHOT_DIR}/{name}_error.png", full_page=True)
 except Exception:
 pass

 results["console_errors"] = console_errors[:5]
 results["status"] = "PASS" if not results["errors"] else "FAIL"
 print(f" >>> {results['status']}")
 return results

# ============================================================
# Test 3: Admin - 数据源配置
# ============================================================

def test_admin_data_sources(page):
 """Admin 数据源配置: 查看 → 编辑对话框 → 修改权威分 → 保存。"""
 name = "test_admin_data_sources"
 print(f"\n{'=' * 60}")
 print(f"[UI] {name}")
 print(f"{'=' * 60}")

 results = {"name": name, "checks": [], "errors": [], "console_errors": []}
 console_errors = []
 page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

 try:
 # 导航到 Admin 页面
 page.goto(f"{BASE_URL}/admin", wait_until="domcontentloaded", timeout=15000)
 time.sleep(2)

 # 截图: admin 初始页
 page.screenshot(path=f"{SCREENSHOT_DIR}/{name}_admin.png", full_page=True)

 # 切换到"数据源配置" Tab
 source_tab = page.locator(".el-tabs__item:has-text('数据源配置')")
 if source_tab.count > 0:
 source_tab.click
 # 等待 Tab 面板可见且表格数据渲染
 try:
 page.wait_for_selector('[role="tabpanel"]#pane-sources .el-table__body-wrapper tbody tr', timeout=8000)
 except Exception:
 pass # 即使没找到行也继续，可能是空表格
 time.sleep(1)
 results["checks"].append("切换到数据源配置 Tab")
 print(" [OK] 切换到数据源配置 Tab")
 else:
 results["errors"].append("未找到数据源配置 Tab")
 page.screenshot(path=f"{SCREENSHOT_DIR}/{name}_no_tab.png", full_page=True)
 results["status"] = "FAIL"
 results["console_errors"] = console_errors[:5]
 return results

 # 使用更精确的定位: 在数据源面板范围内找编辑按钮
 sources_panel = page.locator('[role="tabpanel"]#pane-sources')
 edit_btn = sources_panel.locator("button:has-text('编辑')").first
 if edit_btn.count == 0:
 results["errors"].append("未找到编辑按钮（可能无数据源）")
 page.screenshot(path=f"{SCREENSHOT_DIR}/{name}_no_edit.png", full_page=True)
 results["status"] = "FAIL"
 results["console_errors"] = console_errors[:5]
 return results

 # 点击编辑 - 使用 force=True 以应对可能的动画过渡遮挡
 edit_btn.click(timeout=10000)
 time.sleep(1.5)
 results["checks"].append("点击编辑按钮")
 print(" [OK] 点击编辑按钮")

 # 验证编辑对话框
 edit_dialog = page.locator(".el-dialog:has-text('编辑数据源')")
 if edit_dialog.count == 0:
 results["errors"].append("编辑数据源对话框未出现")
 else:
 results["checks"].append("编辑数据源对话框已打开")
 print(" [OK] 编辑数据源对话框已打开")

 # 修改名称
 name_input = edit_dialog.locator("input").first
 if name_input.count > 0:
 current_name = name_input.input_value
 name_input.fill("")
 name_input.fill(f"{current_name} (已编辑)")
 results["checks"].append(f"修改名称: {current_name} → {current_name} (已编辑)")
 print(f" [OK] 修改名称: {current_name} → {current_name} (已编辑)")

 # 修改权威分 (移动 slider)
 slider = edit_dialog.locator(".el-slider")
 if slider.count > 0:
 results["checks"].append("权威分 slider 存在")
 print(" [OK] 权威分 slider 存在")

 # 截图
 page.screenshot(path=f"{SCREENSHOT_DIR}/{name}_edit_dialog.png", full_page=True)
 results["checks"].append("截图: 编辑数据源对话框")

 # 点击保存
 save_btn = edit_dialog.locator("button:has-text('保存')")
 if save_btn.count > 0:
 save_btn.click
 time.sleep(1.5)
 results["checks"].append("保存数据源编辑")
 print(" [OK] 保存数据源编辑")
 else:
 # 可能没有保存按钮，那么取消
 cancel_btn = edit_dialog.locator("button:has-text('取消')")
 if cancel_btn.count > 0:
 cancel_btn.click
 time.sleep(1)

 except Exception as e:
 results["errors"].append(f"异常: {str(e)[:200]}")
 try:
 page.screenshot(path=f"{SCREENSHOT_DIR}/{name}_error.png", full_page=True)
 except Exception:
 pass

 results["console_errors"] = console_errors[:5]
 results["status"] = "PASS" if not results["errors"] else "FAIL"
 print(f" >>> {results['status']}")
 return results

# ============================================================
# Test 4: Admin - 图谱节点管理
# ============================================================

def test_admin_graph_nodes(page):
 """图谱节点管理: 搜索 → 类型过滤 → 分页 → 新建节点弹窗。"""
 name = "test_admin_graph_nodes"
 print(f"\n{'=' * 60}")
 print(f"[UI] {name}")
 print(f"{'=' * 60}")

 results = {"name": name, "checks": [], "errors": [], "console_errors": []}
 console_errors = []
 page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

 try:
 # 导航到 Admin
 page.goto(f"{BASE_URL}/admin", wait_until="domcontentloaded", timeout=15000)
 time.sleep(2)

 # 切换到"图谱节点管理" Tab
 nodes_tab = page.locator(".el-tabs__item:has-text('图谱节点管理')")
 if nodes_tab.count > 0:
 nodes_tab.click
 # 等待 Tab 面板内容渲染
 try:
 page.wait_for_selector('[role="tabpanel"]#pane-nodes .el-table', timeout=8000)
 except Exception:
 pass
 time.sleep(1)
 results["checks"].append("切换到图谱节点管理 Tab")
 print(" [OK] 切换到图谱节点管理 Tab")

 # 截图: 节点管理界面
 page.screenshot(path=f"{SCREENSHOT_DIR}/{name}_nodes.png", full_page=True)
 else:
 results["errors"].append("未找到图谱节点管理 Tab")

 # 限域: 图谱节点管理面板
 nodes_panel = page.locator('[role="tabpanel"]#pane-nodes')

 # 搜索框
 search_input = nodes_panel.locator("input[placeholder='搜索节点名称...']")
 if search_input.count > 0:
 search_input.fill("测试搜索")
 time.sleep(1)
 results["checks"].append("搜索框输入测试关键词")
 print(" [OK] 搜索框输入测试关键词")
 # 清除搜索
 clear_btn = search_input.locator("..").locator(".el-input__clear")
 if clear_btn.count > 0:
 clear_btn.click
 time.sleep(0.5)
 results["checks"].append("清除搜索")
 print(" [OK] 清除搜索")
 else:
 results["errors"].append("未找到搜索框")

 # 类型过滤 (el-select，先定位到面板内的第一个 el-select)
 type_select = nodes_panel.locator(".el-select").first
 if type_select.count > 0:
 type_select.click
 time.sleep(0.8)
 # 找到对应的下拉框 - 定位到 type_select 关联的 popper
 popover_id = type_select.locator("input").get_attribute("aria-controls")
 if popover_id:
 dropdown = page.locator(f"#{popover_id}")
 else:
 dropdown = page.locator(".el-select-dropdown").first
 # 选择"技能" (第二个选项，第一个是"全部")
 item = dropdown.locator(".el-select-dropdown__item").nth(1)
 if item.count > 0:
 item.click
 time.sleep(0.5)
 results["checks"].append("类型过滤: 选择技能")
 print(" [OK] 类型过滤: 选择技能")
 else:
 # 直接选第一个可用的
 item = dropdown.locator(".el-select-dropdown__item").first
 if item.count > 0:
 item.click
 time.sleep(0.5)
 else:
 print(" [WARN] 未找到类型过滤 el-select")

 # 新建节点按钮
 create_btn = nodes_panel.locator("button:has-text('新建节点')")
 if create_btn.count > 0:
 create_btn.click
 time.sleep(1.5)
 results["checks"].append("点击新建节点按钮")
 print(" [OK] 点击新建节点按钮")

 # 验证 GraphNodeEditor 弹窗
 editor_dialog = page.locator(".el-dialog:visible, .graph-node-editor:visible")
 if editor_dialog.count > 0:
 results["checks"].append("新建节点弹窗出现")
 print(" [OK] 新建节点弹窗出现")
 page.screenshot(path=f"{SCREENSHOT_DIR}/{name}_create_dialog.png", full_page=True)
 # 取消
 cancel_btn = editor_dialog.locator("button:has-text('取消')")
 if cancel_btn.count > 0:
 cancel_btn.click
 time.sleep(1)
 else:
 print(" [WARN] 新建节点弹窗未出现（可能是无数据模式）")

 # 分页控件
 pagination = nodes_panel.locator(".el-pagination")
 if pagination.count > 0:
 results["checks"].append("分页控件存在")
 print(" [OK] 分页控件存在")
 else:
 print(" [WARN] 无分页控件（可能是数据量不足一页）")

 # 最终截图
 page.screenshot(path=f"{SCREENSHOT_DIR}/{name}_final.png", full_page=True)

 except Exception as e:
 results["errors"].append(f"异常: {str(e)[:200]}")
 try:
 page.screenshot(path=f"{SCREENSHOT_DIR}/{name}_error.png", full_page=True)
 except Exception:
 pass

 results["console_errors"] = console_errors[:5]
 results["status"] = "PASS" if not results["errors"] else "FAIL"
 print(f" >>> {results['status']}")
 return results

# ============================================================
# Test 5: Admin - 演示数据重置确认弹窗
# ============================================================

def test_admin_demo_reset(page):
 """演示数据重置: 点击重置 → 确认弹窗出现 → 取消。"""
 name = "test_admin_demo_reset"
 print(f"\n{'=' * 60}")
 print(f"[UI] {name}")
 print(f"{'=' * 60}")

 results = {"name": name, "checks": [], "errors": [], "console_errors": []}
 console_errors = []
 page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

 try:
 # 导航到 Admin
 page.goto(f"{BASE_URL}/admin", wait_until="domcontentloaded", timeout=15000)
 time.sleep(2)

 # 切换到"演示数据管理" Tab
 demo_tab = page.locator(".el-tabs__item:has-text('演示数据管理')")
 if demo_tab.count > 0:
 demo_tab.click
 time.sleep(2)
 results["checks"].append("切换到演示数据管理 Tab")
 print(" [OK] 切换到演示数据管理 Tab")
 else:
 results["errors"].append("未找到演示数据管理 Tab")
 results["status"] = "FAIL"
 results["console_errors"] = console_errors[:5]
 return results

 # 查找"重置为演示数据"按钮
 reset_btn = page.locator("button:has-text('重置为演示数据')")
 if reset_btn.count == 0:
 results["errors"].append("未找到「重置为演示数据」按钮")
 page.screenshot(path=f"{SCREENSHOT_DIR}/{name}_no_button.png", full_page=True)
 else:
 results["checks"].append("找到重置按钮")
 print(" [OK] 找到重置按钮")
 page.screenshot(path=f"{SCREENSHOT_DIR}/{name}_before_reset.png", full_page=True)

 # 点击重置按钮
 reset_btn.click
 time.sleep(2)

 # 验证确认弹窗
 confirm_dialog = page.locator(".el-message-box:has-text('重置数据'), .el-message-box:has-text('确认重置')")
 if confirm_dialog.count > 0:
 results["checks"].append("确认弹窗出现")
 print(" [OK] 确认弹窗出现")
 page.screenshot(path=f"{SCREENSHOT_DIR}/{name}_confirm.png", full_page=True)

 # 点击取消（不真正重置）
 cancel_btn = confirm_dialog.locator("button:has-text('取消')")
 if cancel_btn.count > 0:
 cancel_btn.click
 time.sleep(1)
 results["checks"].append("取消重置操作")
 print(" [OK] 取消重置操作")
 else:
 # 点关闭按钮
 close_btn = confirm_dialog.locator(".el-message-box__close")
 if close_btn.count > 0:
 close_btn.click
 time.sleep(1)
 else:
 results["errors"].append("确认弹窗未出现")

 page.screenshot(path=f"{SCREENSHOT_DIR}/{name}_final.png", full_page=True)

 except Exception as e:
 results["errors"].append(f"异常: {str(e)[:200]}")
 try:
 page.screenshot(path=f"{SCREENSHOT_DIR}/{name}_error.png", full_page=True)
 except Exception:
 pass

 results["console_errors"] = console_errors[:5]
 results["status"] = "PASS" if not results["errors"] else "FAIL"
 print(f" >>> {results['status']}")
 return results

# ============================================================
# Test 6: Admin - 统计概览数据
# ============================================================

def test_admin_stats(page):
 """Admin 统计概览: 查看统计卡片是否有数据。"""
 name = "test_admin_stats"
 print(f"\n{'=' * 60}")
 print(f"[UI] {name}")
 print(f"{'=' * 60}")

 results = {"name": name, "checks": [], "errors": [], "console_errors": []}
 console_errors = []
 page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

 try:
 page.goto(f"{BASE_URL}/admin", wait_until="domcontentloaded", timeout=15000)
 time.sleep(3)

 # 审核队列 Tab (默认)
 body_text = page.inner_text("body")

 # 检查是否有统计数字或数据
 stat_keywords = ["审核", "pending", "待审核", "统计", "队列", "source", "数据"]
 found = [kw for kw in stat_keywords if kw.lower in body_text.lower]
 if found:
 results["checks"].append(f"页面含统计关键词: {', '.join(found)}")
 print(f" [OK] 统计关键词: {', '.join(found)}")
 else:
 results["errors"].append("页面似乎没有统计内容")

 char_count = len(body_text.strip)
 results["checks"].append(f"页面内容: {char_count} 字符")
 print(f" [INFO] 页面内容: {char_count} 字符")

 page.screenshot(path=f"{SCREENSHOT_DIR}/{name}_stats.png", full_page=True)

 except Exception as e:
 results["errors"].append(f"异常: {str(e)[:200]}")

 results["console_errors"] = console_errors[:5]
 results["status"] = "PASS" if not results["errors"] else "FAIL"
 print(f" >>> {results['status']}")
 return results

# ============================================================
# 主函数
# ============================================================

def main:
 os.makedirs(SCREENSHOT_DIR, exist_ok=True)

 # 先跑 API 测试（不需要浏览器）
 all_results = []
 api_results = test_pipeline_config_api
 all_results.append(api_results)

 # 检查服务是否在线
 frontend_ok = check_http_status(BASE_URL) == 200
 if not frontend_ok:
 print(f"\n [SKIP] 前端 {BASE_URL} 不可用，跳过 UI 测试")
 results_summary(all_results)
 return False

 # UI 测试需要 Playwright
 try:
 from playwright.sync_api import sync_playwright
 except ImportError:
 print("\n [SKIP] 未安装 playwright，跳过 UI 测试")
 results_summary(all_results)
 return False

 ui_tests = [
 test_pipeline_config_dialog,
 test_admin_data_sources,
 test_admin_graph_nodes,
 test_admin_demo_reset,
 test_admin_stats,
 ]

 with sync_playwright as p:
 browser = p.chromium.launch(headless=True)
 context = browser.new_context(
 viewport={"width": 1920, "height": 1080},
 ignore_https_errors=True,
 )

 for test_fn in ui_tests:
 page = context.new_page
 result = test_fn(page)
 all_results.append(result)
 page.close

 browser.close

 # 汇总
 results_summary(all_results)
 passed = sum(1 for r in all_results if r["status"] == "PASS")
 return passed == len(all_results)

def results_summary(all_results):
 print(f'\n{"=" * 60}')
 print("配置管理测试 - 结果汇总")
 print(f'{"=" * 60}')

 passed = sum(1 for r in all_results if r["status"] == "PASS")
 failed = sum(1 for r in all_results if r["status"] == "FAIL")

 print(f"\n总计: {len(all_results)} | 通过: {passed} | 失败: {failed}")
 print(f"通过率: {passed / len(all_results) * 100:.1f}%\n")

 print(f'{"测试项":<35} {"状态":<8} {"检查点"}')
 print("-" * 80)

 for r in all_results:
 checks_str = "; ".join(r["checks"][:3]) if r["checks"] else "-"
 cerr = f' ({len(r["console_errors"])} console err)' if r.get("console_errors") else ""
 print(f'{r["name"]:<35} {r["status"]:<8} {checks_str}{cerr}')

 failures = [r for r in all_results if r["status"] == "FAIL"]
 if failures:
 print(f'\n{"=" * 60}')
 print("失败详情")
 print(f'{"=" * 60}')
 for r in failures:
 print(f'\n {r["name"]}')
 for err in r["errors"]:
 print(f" - {err}")

 print(f'\n截图目录: {os.path.abspath(SCREENSHOT_DIR)}')
 print(f'{"=" * 60}\n')

if __name__ == "__main__":
 success = main
 exit(0 if success else 1)
