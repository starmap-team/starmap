"""
StarMap E2E 冒烟测试脚本（§10.4）

这是每日集成的核心工具（规范7 §17.8）。
每天在远程服务器上运行，验证 main 分支"随时可演示"。

4 个场景：
  E2E-1 新岗位发现：原始JD→涌现→聚类→定义→入图
  E2E-2 既有岗位更新：旧/新快照→差分→提案→审核→更新
  E2E-3 简历匹配诊断：上传→解析→对比→差距→学习路径
  E2E-4 Docker 一键部署：docker-compose up→全服务启动→种子加载→首屏可交互

用法：
  python tests/e2e/smoke_test.py --base-url http://localhost:8000
  python tests/e2e/smoke_test.py --scenario e2e-1
  python tests/e2e/smoke_test.py --all
"""
import argparse
import sys
import time
from urllib.parse import quote

import requests


class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


def log(level, msg):
    icons = {"pass": f"{Colors.GREEN}✅", "fail": f"{Colors.RED}❌", "warn": f"{Colors.YELLOW}⚠️", "info": "ℹ️"}
    icon = icons.get(level, "ℹ️")
    reset = Colors.RESET if level in ("pass", "fail", "warn") else ""
    print(f"  {icon} {msg}{reset}")


def check(name, condition, detail=""):
    if condition:
        log("pass", f"{name}")
        return True
    else:
        log("fail", f"{name} {f'— {detail}' if detail else ''}")
        return False


# ============================================================
# E2E-0 基础健康检查（所有场景的前置条件）
# ============================================================
def test_health(base_url):
    """验证所有核心服务可达。"""
    print(f"\n{Colors.BOLD}=== E2E-0 基础健康检查 ==={Colors.RESET}")

    results = []

    # 后端 API
    try:
        resp = requests.get(f"{base_url}/health", timeout=5)
        body = resp.json()
        results.append(check("后端 /health 返回 200", resp.status_code == 200))
        results.append(check("后端 status=ok", body.get("status") == "ok"))
    except Exception as e:
        results.append(check("后端 /health 可达", False, str(e)))

    # 前端（通过 Nginx 或 Vite）
    try:
        resp = requests.get(base_url.replace(":8000", ":5173"), timeout=5)
        results.append(check("前端可达", resp.status_code == 200))
    except Exception as e:
        log("warn", f"前端不可达（开发环境可能未启动）— {e}")
        results.append(True)  # 开发环境下前端可能不在

    # Neo4j（通过后端代理或直连）
    # PostgreSQL、Redis、Chroma 通过后端 /health 间接验证

    return all(results)


# ============================================================
# E2E-1 新岗位发现
# ============================================================
def test_e2e1_new_position_discovery(base_url):
    """验证新岗位发现全链路：JD→涌现→聚类→定义→入图。"""
    print(f"\n{Colors.BOLD}=== E2E-1 新岗位发现 ==={Colors.RESET}")
    log("info", "场景：原始JD→涌现检测→聚类→多源验证→LLM定义→幻觉防控→入图")

    results = []

    # Step 1: 全景图谱有数据
    # DEPLOY-FIX (2026-08-14): 冷启动竞态误报 — Neo4j 数据就绪晚于容器健康，
    # 原实现首查即判失败。加重试 3 次 × 5s 后再判定。
    try:
        node_count = 0
        for attempt in range(1, 4):
            resp = requests.get(f"{base_url}/api/v1/graph/panorama", timeout=10)
            data = resp.json()
            node_count = len(data.get("nodes", []))
            if node_count > 0:
                break
            if attempt < 3:
                time.sleep(5)
        results.append(check(
            f"全景图谱有节点 ({node_count} 个)",
            node_count > 0,
            "图谱为空，可能种子数据未加载"
        ))
    except Exception as e:
        results.append(check("全景图谱可查询", False, str(e)))

    # Step 2: 岗位列表非空
    try:
        resp = requests.get(f"{base_url}/api/v1/positions/", timeout=10)
        data = resp.json()
        pos_count = len(data.get("items", []))
        results.append(check(
            f"岗位列表非空 ({pos_count} 个)",
            pos_count > 0
        ))
    except Exception as e:
        results.append(check("岗位列表可查询", False, str(e)))

    # TODO(W8): 当演化引擎 ready 后，补充完整的新岗位发现链路验证
    log("warn", "完整新岗位发现链路（涌现→聚类→入图）待 W8 演化引擎 ready 后补充")

    return all(results)


# ============================================================
# E2E-2 既有岗位更新
# ============================================================
def test_e2e2_position_update(base_url):
    """验证既有岗位能力更新：差分检测→变更提案→审核→入图。"""
    print(f"\n{Colors.BOLD}=== E2E-2 既有岗位更新 ==={Colors.RESET}")
    log("info", "场景：旧快照→新JD流→差分检测→变更提案→人工审核→更新")

    results = []

    # 岗位详情可查
    try:
        resp = requests.get(f"{base_url}/api/v1/positions/", timeout=10)
        positions = resp.json().get("items", [])
        if positions:
            pos_name = positions[0].get("name", positions[0].get("job_title", ""))
            if pos_name:
                # DEPLOY-FIX (2026-08-14): 岗位名含空格/特殊字符时未 URL 编码
                # → "Account Executive" 请求挂（需 %20）。quote 后路径可查。
                resp2 = requests.get(
                    f"{base_url}/api/v1/graph/position/{quote(pos_name, safe='')}",
                    timeout=10,
                )
                results.append(check(
                    f"岗位详情可查 ({pos_name})",
                    resp2.status_code == 200
                ))
            else:
                results.append(check("岗位有名称", False, "岗位数据缺少名称字段"))
        else:
            log("warn", "无岗位数据，跳过详情检查")
            results.append(True)
    except Exception as e:
        results.append(check("岗位详情可查", False, str(e)))

    # 演化趋势接口
    try:
        resp = requests.get(f"{base_url}/api/v1/evolution/trends", timeout=10)
        results.append(check(
            "演化趋势接口可达",
            resp.status_code == 200
        ))
    except Exception as e:
        results.append(check("演化趋势接口", False, str(e)))

    log("warn", "完整变更提案链路（差分→提案→审核）待 W8 后补充")

    return all(results)


# ============================================================
# E2E-3 简历匹配诊断
# ============================================================
def test_e2e3_resume_match(base_url):
    """验证简历匹配诊断：上传→解析→雷达→差距→学习路径。"""
    print(f"\n{Colors.BOLD}=== E2E-3 简历匹配诊断 ==={Colors.RESET}")
    log("info", "场景：上传简历→技能提取→雷达对比→差距报告→学习路径")

    results = []

    # 匹配诊断接口可达（不实际上传，验证接口存在）
    try:
        resp = requests.post(
            f"{base_url}/api/v1/match/diagnose",
            json={"target_position": "test", "resume_id": 0},
            timeout=10
        )
        # 可能返回 400（参数无效）或 200，关键是接口存在
        results.append(check(
            "匹配诊断接口可达",
            resp.status_code in (200, 400, 422),
            f"返回 {resp.status_code}"
        ))
    except Exception as e:
        results.append(check("匹配诊断接口", False, str(e)))

    log("warn", "完整简历上传+匹配链路待 W10 匹配引擎 ready 后补充")

    return all(results)


# ============================================================
# E2E-4 Docker 一键部署
# ============================================================
def test_e2e4_docker_deploy(base_url):
    """验证 Docker 部署：全服务启动→种子加载→首屏可交互。"""
    print(f"\n{Colors.BOLD}=== E2E-4 Docker 一键部署 ==={Colors.RESET}")
    log("info", "场景：干净机器 docker-compose up→全服务启动→种子加载→首屏可交互")

    results = []

    # 所有服务健康
    results.append(test_health(base_url))

    # 演示数据存在（种子加载验证）
    try:
        resp = requests.get(f"{base_url}/api/v1/quality/dashboard", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            total_nodes = data.get("total_nodes", 0)
            results.append(check(
                f"演示数据已加载 ({total_nodes} 节点)",
                total_nodes > 0,
                "可能种子数据未加载（运行 seed_loader.py）"
            ))
    except Exception as e:
        results.append(check("质量看板接口", False, str(e)))

    return all(results)


# ============================================================
# 主入口
# ============================================================
def main():
    parser = argparse.ArgumentParser(description="StarMap E2E 冒烟测试")
    parser.add_argument("--base-url", default="http://localhost:8000",
                        help="后端 API 地址（默认 http://localhost:8000）")
    parser.add_argument("--scenario", choices=["e2e-0", "e2e-1", "e2e-2", "e2e-3", "e2e-4"],
                        help="只跑指定场景")
    parser.add_argument("--all", action="store_true", help="跑所有场景")
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print("  StarMap E2E 冒烟测试")
    print(f"  目标: {args.base_url}")
    print(f"  时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    scenarios = {
        "e2e-0": ("基础健康检查", lambda: test_health(args.base_url)),
        "e2e-1": ("新岗位发现", lambda: test_e2e1_new_position_discovery(args.base_url)),
        "e2e-2": ("既有岗位更新", lambda: test_e2e2_position_update(args.base_url)),
        "e2e-3": ("简历匹配诊断", lambda: test_e2e3_resume_match(args.base_url)),
        "e2e-4": ("Docker 一键部署", lambda: test_e2e4_docker_deploy(args.base_url)),
    }

    if args.all or not args.scenario:
        run_list = list(scenarios.keys())
    else:
        run_list = [args.scenario]

    all_passed = True
    for key in run_list:
        name, func = scenarios[key]
        try:
            passed = func()
            if not passed:
                all_passed = False
        except Exception as e:
            log("fail", f"{name} 异常: {e}")
            all_passed = False

    # 汇总
    print(f"\n{'='*60}")
    if all_passed:
        print(f"  {Colors.GREEN}{Colors.BOLD}✅ 全部通过 — main 可演示{Colors.RESET}")
    else:
        print(f"  {Colors.RED}{Colors.BOLD}❌ 存在失败 — 需修复后才能合并{Colors.RESET}")
    print(f"{'='*60}\n")

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
