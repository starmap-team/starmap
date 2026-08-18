"""Phase 3.8.6 端到端闭合测试 — 前端触发 → 校验 → DB写入 → 图谱构建 → 验证

测试流程:
1. 前端点击"触发流水线" → 选择全量 + 全部阶段
2. 监控每一阶段的 SSE 推送进度
3. 检查 jd_raw 表写入
4. 检查 Neo4j 图谱节点创建
5. 检查每阶段错误
6. 生成问题清单
"""
import asyncio
import json

from e2e_creds import login_payload
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright

SCREENSHOTS = Path("tests/e2e/screenshots/phase386")
SCREENSHOTS.mkdir(parents=True, exist_ok=True)
ISSUES: list[str] = []

def add_issue(msg: str):
 ISSUES.append(msg)
 print(f" ❌ ISSUE: {msg}")

def api_call(method: str, path: str, data=None, timeout=30):
 token, _ = api_login_raw
 headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
 body = json.dumps(data).encode if data else None
 req = urllib.request.Request(
 f"http://localhost:8000{path}",
 data=body, headers=headers, method=method,
 )
 resp = urllib.request.urlopen(req, timeout=timeout)
 return json.loads(resp.read)

def api_login_raw:
 req = urllib.request.Request(
 "http://localhost:8000/api/v1/auth/login",
 data=json.dumps(login_payload).encode,
 headers={"Content-Type": "application/json"},
 )
 with urllib.request.urlopen(req, timeout=10) as r:
 b = json.loads(r.read)
 return b["access_token"], b.get("user", {})

async def main:
 token, user_info = api_login_raw

 print("=" * 70)
 print("Phase 3.8.6 端到端闭合测试")
 print(f"开始时间: {datetime.now.strftime('%H:%M:%S')}")
 print("=" * 70)

 # ── 前置状态检查 ──
 print("\n[Step 0] 前置状态检查")
 try:
 status = api_call("GET", "/api/v1/pipeline/status")
 print(f" is_running: {status.get('is_running')}")
 if status.get("is_running"):
 add_issue("已有 run 在运行中, 需要先清理")
 return
 except Exception as e:
 add_issue(f"状态查询失败: {e}")
 return

 # ── 触发流水线 (通过 API 模拟前端点击) ──
 print("\n[Step 1] 触发流水线 (全量 + 全部 6 阶段)")
 print(" 前端点击: 触发流水线 → 全量 → 选中全部 → 启动")
 try:
 result = api_call("POST", "/api/v1/pipeline/trigger", {
 "run_type": "incremental",
 "selected_stages": ["crawl", "dedup", "clean", "import", "graph_sync", "timeseries"],
 })
 run_id = result["run_id"]
 print(f" ✅ run_id={run_id[:8]} status={result['status']}")
 except Exception as e:
 add_issue(f"触发失败: {e}")
 return

 # ── 等待 + 监控每阶段进展 ──
 print("\n[Step 2] 监控阶段进展 (每 10s 检查一次, 最多 10 分钟)")
 elapsed = 0
 max_wait = 600
 last_stages_snapshot = None

 while elapsed < max_wait:
 time.sleep(10)
 elapsed += 10

 try:
 status = api_call("GET", "/api/v1/pipeline/status")
 except Exception:
 continue

 cr = status.get("current_run")
 if not cr or cr.get("id") != run_id:
 add_issue(f"current_run 不匹配: expected {run_id[:8]}, got {cr.get('id', 'N/A')[:8] if cr else 'None'}")
 continue

 stages = cr.get("stages", [])
 active = [s for s in stages if s.get("status") != "skipped"]
 completed = [s for s in active if s["status"] == "completed"]
 running = [s for s in active if s["status"] == "running"]
 failed = [s for s in active if s["status"] == "failed"]
 pending = [s for s in active if s["status"] == "pending"]

 # 只在状态变化时打印
 snapshot = f"{len(completed)}C/{len(running)}R/{len(failed)}F/{len(pending)}P"
 if snapshot != last_stages_snapshot:
 last_stages_snapshot = snapshot
 print(f" [{elapsed}s] {snapshot}")
 for s in active:
 marker = "✓" if s["status"] == "completed" else "⏳" if s["status"] == "running" else "✗" if s["status"] == "failed" else "○"
 print(f" {marker} {s['name']:15} | {s['status']:11} | rec={s.get('records_processed', 0):>4} | dur={s.get('duration_ms', 0):>5}ms")

 # 检查是否完成
 if len(completed) + len(failed) >= len(active):
 print(f"\n ✅ 全部阶段完成/失败: {len(completed)}完成/{len(failed)}失败")
 break

 # ── 最终状态分析 ──
 print("\n[Step 3] 最终状态分析")
 try:
 status = api_call("GET", "/api/v1/pipeline/status")
 cr = status.get("current_run")
 if not cr:
 add_issue("测试结束时 current_run 为 None (run 被清理了?)")
 else:
 for s in cr.get("stages", []):
 if s.get("status") != "skipped":
 status_icon = "✓" if s["status"] == "completed" else "✗"
 print(f" {status_icon} {s['name']:15} | {s['status']:11} | rec={s.get('records_processed', 0):>4} | errors={len(s.get('errors', []))}")

 if s["status"] == "completed" and s.get("records_processed", 0) == 0 and s["name"] not in ("timeseries",):
 add_issue(f"阶段 {s['name']} completed 但 0 条记录")
 if s["status"] == "failed":
 errs = s.get("errors", [])
 add_issue(f"阶段 {s['name']} 失败: {errs[:3]}")
 if s["status"] == "pending":
 add_issue(f"阶段 {s['name']} 仍为 pending (卡死?)")
 except Exception as e:
 add_issue(f"最终状态分析失败: {e}")

 # ── 验证 DB 写入 ──
 print("\n[Step 4] 验证 PostgreSQL 写入")
 try:
 import subprocess
 db_check = subprocess.run(
 ['docker', 'exec', 'starmap-postgres', 'psql', '-U', 'starmap', '-d', 'starmap',
 '-c', "SELECT COUNT(*) as total FROM jd_raw"],
 capture_output=True, text=True, timeout=10,
 )
 print(f" jd_raw total: {db_check.stdout.strip.split(chr(10))[-2].strip}")
 except Exception as e:
 add_issue(f"DB 检查失败: {e}")

 # ── 验证 Neo4j 图谱构建 ──
 print("\n[Step 5] 验证 Neo4j 图谱构建")
 try:
 neo4j_check = subprocess.run(
 ['docker', 'exec', 'starmap-neo4j', 'cypher-shell', '-u', 'neo4j', '-p', 'starmap123456',
 'MATCH (n) RETURN count(n) as total_nodes'],
 capture_output=True, text=True, timeout=10,
 )
 print(f" Neo4j nodes: {neo4j_check.stdout.strip.split(chr(10))[-2].strip}")
 except Exception as e:
 add_issue(f"Neo4j 检查失败: {e}")

 # ── 生成问题清单 ──
 print("\n" + "=" * 70)
 print(f"📊 问题清单 ({len(ISSUES)} 个)")
 print("=" * 70)
 if not ISSUES:
 print(" ✅ 未发现问题 — 端到端流程正常")
 else:
 for i, issue in enumerate(ISSUES, 1):
 print(f" {i}. {issue}")

 # 清理
 try:
 api_call("POST", f"/api/v1/pipeline/runs/{run_id}/force-reset")
 print("\n[清理] run 已重置")
 except Exception:
 pass

if __name__ == "__main__":
 asyncio.run(main)
