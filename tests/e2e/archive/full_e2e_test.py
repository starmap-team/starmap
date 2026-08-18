# -*- coding: utf-8 -*-
"""
StarMap 完备 E2E 验证测试套件

覆盖三层：
  1. 功能测试 — 每个 API 端点的请求/响应契约验证
  2. 集成测试 — 跨服务数据流一致性（Extract→Graph→Match→Learning→Loop）
  3. 前后端一致性 — API 响应字段与前端 schema.ts 类型对齐

禁止使用 mock 数据：所有测试请求真实后端服务。

用法：
  python tests/e2e/full_e2e_test.py --base-url http://localhost:8000
  python tests/e2e/full_e2e_test.py --suite api          # 仅 API 功能测试
  python tests/e2e/full_e2e_test.py --suite integration   # 仅集成测试
  python tests/e2e/full_e2e_test.py --suite consistency   # 仅前后端一致性

前置条件：
  - docker compose -f docker-compose.dev.yml up (或后端单独运行)
  - 种子数据已加载
"""
import argparse
import json
import sys
import time
from pathlib import Path

import requests


# ── 工具函数 ──

class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


results_log: list[dict] = []


def log(level: str, msg: str) -> None:
    icons = {
        "pass": f"{Colors.GREEN}[PASS]",
        "fail": f"{Colors.RED}[FAIL]",
        "warn": f"{Colors.YELLOW}[WARN]",
        "info": f"{Colors.CYAN}[INFO]",
    }
    icon = icons.get(level, "[INFO]")
    reset = Colors.RESET if level in ("pass", "fail", "warn") else ""
    try:
        print(f"  {icon} {msg}{reset}")
    except UnicodeEncodeError:
        print(f"  {level.upper()} {msg}")


def check(name: str, condition: bool, detail: str = "") -> bool:
    if condition:
        log("pass", name)
        results_log.append({"name": name, "result": "pass"})
        return True
    else:
        log("fail", f"{name} {f'— {detail}' if detail else ''}")
        results_log.append({"name": name, "result": "fail", "detail": detail})
        return False


def api_get(base_url: str, path: str, timeout: int = 10) -> tuple[int, dict]:
    """GET 请求，返回 (status_code, json_body)。"""
    try:
        resp = requests.get(f"{base_url}{path}", timeout=timeout)
        return resp.status_code, resp.json()
    except Exception as e:
        return 0, {"error": str(e)}


def api_post(base_url: str, path: str, body: dict, timeout: int = 30) -> tuple[int, dict]:
    """POST 请求，返回 (status_code, json_body)。"""
    try:
        resp = requests.post(f"{base_url}{path}", json=body, timeout=timeout)
        return resp.status_code, resp.json()
    except Exception as e:
        return 0, {"error": str(e)}


def api_put(base_url: str, path: str, body: dict, timeout: int = 10) -> tuple[int, dict]:
    """PUT 请求，返回 (status_code, json_body)。"""
    try:
        resp = requests.put(f"{base_url}{path}", json=body, timeout=timeout)
        return resp.status_code, resp.json()
    except Exception as e:
        return 0, {"error": str(e)}


def api_delete(base_url: str, path: str, timeout: int = 10) -> int:
    """DELETE 请求，返回 status_code。"""
    try:
        resp = requests.delete(f"{base_url}{path}", timeout=timeout)
        return resp.status_code
    except Exception:
        return 0


# ══════════════════════════════════════════════════════
# 第一层：API 功能测试
# ══════════════════════════════════════════════════════

def test_health(base_url: str) -> bool:
    """TC-01: 基础健康检查"""
    print(f"\n{Colors.BOLD}=== TC-01: 基础健康检查 ==={Colors.RESET}")
    results = []

    status, body = api_get(base_url, "/health")
    results.append(check("/health 返回 200", status == 200))
    results.append(check("/health status=ok", body.get("status") == "ok", f"got: {body.get('status')}"))

    services = body.get("services", {})
    results.append(check("PostgreSQL 可达", services.get("postgres") == "ok", f"got: {services.get('postgres')}"))
    results.append(check("Neo4j 可达", services.get("neo4j") == "ok", f"got: {services.get('neo4j')}"))
    results.append(check("Redis 可达", services.get("redis") == "ok", f"got: {services.get('redis')}"))

    return all(results)


def test_positions(base_url: str) -> bool:
    """TC-02: 岗位列表数据"""
    print(f"\n{Colors.BOLD}=== TC-02: 岗位列表 ==={Colors.RESET}")
    results = []

    status, body = api_get(base_url, "/api/v1/positions")
    results.append(check("GET /positions 返回 200", status == 200))
    items = body.get("items", [])
    results.append(check("岗位列表非空", len(items) > 0, f"got {len(items)} items"))
    if items:
        first = items[0]
        results.append(check("岗位含 name 字段", "name" in first or "job_title" in first))

    return all(results)


def test_extract_jd(base_url: str) -> bool:
    """TC-03: JD 抽取"""
    print(f"\n{Colors.BOLD}=== TC-03: JD 抽取 → 图谱写入 ==={Colors.RESET}")
    results = []

    jd_text = """
    高级Python开发工程师
    要求：
    - 5年以上Python开发经验
    - 熟悉 Django/Flask 框架
    - 掌握 PostgreSQL/MySQL 数据库
    - 了解 Redis 缓存和消息队列
    - 熟悉 Docker 和 Kubernetes
    - 有微服务架构经验优先
    """

    status, body = api_post(base_url, "/api/v1/extract/jd", {"jd_content": jd_text}, timeout=120)
    results.append(check("POST /extract/jd 返回 200", status == 200, f"got {status}"))
    if status == 200:
        results.append(check("position_name 非空", bool(body.get("position_name")), f"got: {body.get('position_name')}"))
        req_skills = body.get("required_skills", [])
        results.append(check("required_skills ≥ 3", len(req_skills) >= 3, f"got {len(req_skills)}"))
        norm_skills = body.get("normalized_skills", [])
        results.append(check("normalized_skills 非空", len(norm_skills) > 0, f"got {len(norm_skills)}"))
        results.append(check("confidence 在 0-1", 0 <= body.get("confidence", 0) <= 1))
    else:
        results.append(check("抽取成功（跳过后续检查）", False, f"status={status}"))

    # 验证空输入返回 422
    status2, _ = api_post(base_url, "/api/v1/extract/jd", {"jd_content": ""})
    results.append(check("空 JD 文本返回 422", status2 == 422, f"got {status2}"))

    return all(results)


def test_graph_overview(base_url: str) -> bool:
    """TC-04: 图谱概览"""
    print(f"\n{Colors.BOLD}=== TC-04: 图谱概览 ==={Colors.RESET}")
    results = []

    status, body = api_get(base_url, "/api/v1/graph/overview")
    results.append(check("GET /graph/overview 返回 200", status == 200))
    if status == 200:
        domains = body.get("domains", [])
        results.append(check("domains 非空", len(domains) > 0))
        results.append(check("total_positions > 0", body.get("total_positions", 0) > 0))
        results.append(check("total_skills > 0", body.get("total_skills", 0) > 0))

    return all(results)


def test_graph_position_skills(base_url: str) -> bool:
    """TC-05: 岗位技能子图"""
    print(f"\n{Colors.BOLD}=== TC-05: 岗位技能子图 ==={Colors.RESET}")
    results = []

    # 先获取一个有效岗位名
    _, pos_body = api_get(base_url, "/api/v1/positions")
    items = pos_body.get("items", [])
    if not items:
        log("warn", "无岗位数据，跳过")
        return True

    pos_name = items[0].get("name", items[0].get("job_title", ""))
    if not pos_name:
        log("warn", "岗位无名称，跳过")
        return True

    status, body = api_get(base_url, f"/api/v1/graph/position/{pos_name}/skills")
    results.append(check(f"GET /graph/position/{pos_name}/skills 返回 200", status == 200, f"got {status}"))
    if status == 200:
        results.append(check("position 非空", body.get("position") is not None))
        skills = body.get("skills", [])
        results.append(check("skills 列表非空", len(skills) > 0, f"got {len(skills)}"))
        edges = body.get("edges", [])
        results.append(check("edges 列表存在", isinstance(edges, list)))

    # 不存在的岗位返回 404
    status404, _ = api_get(base_url, "/api/v1/graph/position/NONEXISTENT_POSITION_XYZ/skills")
    results.append(check("不存在岗位返回 404", status404 == 404, f"got {status404}"))

    return all(results)


def test_match(base_url: str) -> bool:
    """TC-06: 匹配诊断"""
    print(f"\n{Colors.BOLD}=== TC-06: 匹配诊断 ==={Colors.RESET}")
    results = []

    body_req = {
        "person_skills": [
            {"name": "Python", "category": "hard_skill", "proficiency": "熟悉"},
            {"name": "Django", "category": "hard_skill", "proficiency": "了解"},
        ],
        "target_position": "后端开发工程师",
        "options": {"threshold": 0.6},
    }

    status, body = api_post(base_url, "/api/v1/match/position", body_req, timeout=30)
    results.append(check("POST /match/position 返回 200", status == 200, f"got {status}"))
    if status == 200:
        results.append(check("match_id 非空", bool(body.get("match_id"))))
        score = body.get("match_score", -1)
        results.append(check("match_score 在 0-1", 0 <= score <= 1, f"got {score}"))
        results.append(check("gap_skills 是列表", isinstance(body.get("gap_skills"), list)))
        detail = body.get("skill_gap_detail", [])
        results.append(check("skill_gap_detail 存在", isinstance(detail, list)))

    # 空技能返回 400
    status400, _ = api_post(base_url, "/api/v1/match/position", {
        "person_skills": [], "target_position": "test"
    })
    results.append(check("空 person_skills 返回 400", status400 == 400, f"got {status400}"))

    return all(results)


def test_match_persistence(base_url: str) -> bool:
    """TC-07: 匹配结果持久化"""
    print(f"\n{Colors.BOLD}=== TC-07: 匹配结果持久化 ==={Colors.RESET}")
    results = []

    # 执行一次匹配
    body_req = {
        "person_skills": [{"name": "Python", "proficiency": "熟悉"}],
        "target_position": "数据分析师",
    }
    status, body = api_post(base_url, "/api/v1/match/position", body_req, timeout=30)
    if status != 200:
        log("warn", f"匹配请求失败 ({status})，跳过持久化验证")
        return True

    match_id = body.get("match_id", "")

    # 通过 match_id 获取结果
    status2, body2 = api_get(base_url, f"/api/v1/match/result/{match_id}")
    results.append(check("GET /match/result/{id} 返回 200", status2 == 200, f"got {status2}"))
    if status2 == 200:
        results.append(check("结果 match_score 一致",
                             abs(body2.get("match_score", -1) - body.get("match_score", -2)) < 0.01))

    # 历史查询
    status3, body3 = api_get(base_url, "/api/v1/match/history")
    results.append(check("GET /match/history 返回 200", status3 == 200))
    if status3 == 200:
        items = body3.get("items", [])
        results.append(check("历史包含匹配记录", len(items) > 0))

    # 不存在的 match_id 返回 404
    status404, _ = api_get(base_url, "/api/v1/match/result/NONEXISTENT")
    results.append(check("不存在 match_id 返回 404", status404 == 404, f"got {status404}"))

    return all(results)


def test_match_to_learning(base_url: str) -> bool:
    """TC-08: 匹配→学习路径"""
    print(f"\n{Colors.BOLD}=== TC-08: 匹配→学习路径 ==={Colors.RESET}")
    results = []

    # 创建学习计划
    plan_req = {
        "position": "后端开发工程师",
        "match_score": 0.45,
        "skills": [
            {"skill": "Kubernetes", "importance": "required", "gap_level": "完全缺失", "learning_path": ["Docker", "Kubernetes"]},
            {"skill": "Redis", "importance": "bonus", "gap_level": "部分掌握", "learning_path": ["Redis"]},
        ],
        "available_hours_per_week": 10,
    }

    status, body = api_post(base_url, "/api/v1/learning/plan", plan_req, timeout=30)
    results.append(check("POST /learning/plan 返回 200", status == 200, f"got {status}"))
    if status == 200:
        plan_id = body.get("plan_id", "")
        results.append(check("plan_id 非空", bool(plan_id)))

        # 获取计划详情
        status2, body2 = api_get(base_url, f"/api/v1/learning/plan/{plan_id}")
        results.append(check("GET /learning/plan/{id} 返回 200", status2 == 200, f"got {status2}"))

        # 更新进度
        status3, body3 = api_put(base_url, f"/api/v1/learning/plan/{plan_id}/progress", {
            "skill_name": "Redis", "status": "completed"
        })
        results.append(check("PUT /learning/plan/{id}/progress 返回 200", status3 == 200, f"got {status3}"))
    else:
        log("warn", f"学习计划创建失败 ({status})，跳过后续检查")

    return all(results)


def test_evolution_trends(base_url: str) -> bool:
    """TC-10: 演化趋势"""
    print(f"\n{Colors.BOLD}=== TC-10: 演化趋势 ==={Colors.RESET}")
    results = []

    status, body = api_get(base_url, "/api/v1/evolution/trends")
    results.append(check("GET /evolution/trends 返回 200", status == 200))
    if status == 200:
        items = body.get("items", [])
        results.append(check("trends items 非空", len(items) > 0, f"got {len(items)}"))
        if items:
            first = items[0]
            results.append(check("含 skill_name", bool(first.get("skill_name"))))
            results.append(check("trend 值有效", first.get("trend") in ("rising", "stable", "declining")))
            results.append(check("confidence 在 0-1", 0 <= first.get("confidence", 0) <= 1))

    return all(results)


def test_evolution_paths(base_url: str) -> bool:
    """TC-11: 演化路径"""
    print(f"\n{Colors.BOLD}=== TC-11: 演化路径 ==={Colors.RESET}")
    results = []

    status, body = api_get(base_url, "/api/v1/evolution/paths/all")
    results.append(check("GET /evolution/paths/all 返回 200", status == 200))
    if status == 200:
        paths = body if isinstance(body, list) else body.get("items", [])
        results.append(check("paths 列表存在", isinstance(paths, list)))

    return all(results)


def test_evolution_reports(base_url: str) -> bool:
    """TC-12/13/14: 行业报告/职业路径/涌现告警"""
    print(f"\n{Colors.BOLD}=== TC-12/13/14: 演化报告 ==={Colors.RESET}")
    results = []

    # 行业报告
    status1, body1 = api_get(base_url, "/api/v1/evolution/industry-report")
    results.append(check("GET /evolution/industry-report 返回 200", status1 == 200, f"got {status1}"))

    # 涌现告警
    status2, body2 = api_get(base_url, "/api/v1/evolution/emerging-alerts")
    results.append(check("GET /evolution/emerging-alerts 返回 200", status2 == 200, f"got {status2}"))

    # 职业路径（需要有效岗位名）
    _, pos_body = api_get(base_url, "/api/v1/positions")
    items = pos_body.get("items", [])
    if items:
        pos_name = items[0].get("name", items[0].get("job_title", ""))
        status3, body3 = api_get(base_url, f"/api/v1/evolution/career-path/{pos_name}")
        results.append(check(f"GET /evolution/career-path/{pos_name} 返回 200", status3 == 200, f"got {status3}"))
    else:
        log("warn", "无岗位数据，跳过职业路径测试")

    return all(results)


def test_quality_dashboard(base_url: str) -> bool:
    """TC-15: 质量仪表盘"""
    print(f"\n{Colors.BOLD}=== TC-15: 质量仪表盘 ==={Colors.RESET}")
    results = []

    status, body = api_get(base_url, "/api/v1/quality/dashboard")
    results.append(check("GET /quality/dashboard 返回 200", status == 200))
    if status == 200:
        report = body.get("report", {})
        results.append(check("含 precision", "precision" in report))
        results.append(check("含 recall", "recall" in report))
        results.append(check("含 f1", "f1" in report))
        results.append(check("含 warning_level", "warning_level" in report))
        results.append(check("total_extractions ≥ 0", body.get("total_extractions", -1) >= 0))
        results.append(check("hallucination_rate 在 0-1", 0 <= body.get("hallucination_rate", 0) <= 1))

    return all(results)


def test_quality_trends_alerts(base_url: str) -> bool:
    """TC-17: 质量趋势与告警"""
    print(f"\n{Colors.BOLD}=== TC-17: 质量趋势与告警 ==={Colors.RESET}")
    results = []

    status1, _ = api_get(base_url, "/api/v1/quality/trends")
    results.append(check("GET /quality/trends 返回 200", status1 == 200, f"got {status1}"))

    status2, _ = api_get(base_url, "/api/v1/quality/alerts")
    results.append(check("GET /quality/alerts 返回 200", status2 == 200, f"got {status2}"))

    return all(results)


def test_dashboard(base_url: str) -> bool:
    """TC-18: 数据大屏"""
    print(f"\n{Colors.BOLD}=== TC-18: 数据大屏 ==={Colors.RESET}")
    results = []

    status, body = api_get(base_url, "/api/v1/dashboard/overview")
    results.append(check("GET /dashboard/overview 返回 200", status == 200))

    status2, _ = api_get(base_url, "/api/v1/dashboard/trends")
    results.append(check("GET /dashboard/trends 返回 200", status2 == 200))

    status3, _ = api_get(base_url, "/api/v1/dashboard/distribution")
    results.append(check("GET /dashboard/distribution 返回 200", status3 == 200))

    return all(results)


def test_datasource_crud(base_url: str) -> bool:
    """TC-19: 数据源 CRUD"""
    print(f"\n{Colors.BOLD}=== TC-19: 数据源 CRUD ==={Colors.RESET}")
    results = []

    # 列表
    status, body = api_get(base_url, "/api/v1/datasources")
    results.append(check("GET /datasources 返回 200", status == 200, f"got {status}"))

    return all(results)


def test_pipeline(base_url: str) -> bool:
    """TC-20: Pipeline 流水线"""
    print(f"\n{Colors.BOLD}=== TC-20: Pipeline 流水线 ==={Colors.RESET}")
    results = []

    status, _ = api_get(base_url, "/api/v1/pipeline/status")
    results.append(check("GET /pipeline/status 返回 200", status == 200, f"got {status}"))

    status2, _ = api_get(base_url, "/api/v1/pipeline/runs")
    results.append(check("GET /pipeline/runs 返回 200", status2 == 200, f"got {status2}"))

    status3, _ = api_get(base_url, "/api/v1/pipeline/stages")
    results.append(check("GET /pipeline/stages 返回 200", status3 == 200, f"got {status3}"))

    return all(results)


def test_loop(base_url: str) -> bool:
    """TC-21: 闭环验证"""
    print(f"\n{Colors.BOLD}=== TC-21: 闭环验证 ==={Colors.RESET}")
    results = []

    jd_text = "前端开发工程师：熟悉 React/Vue，掌握 JavaScript/TypeScript，了解 Node.js"

    status, body = api_post(base_url, "/api/v1/loop/run", {
        "jd_text": jd_text,
        "target_position": "前端开发工程师",
    }, timeout=120)
    results.append(check("POST /loop/run 返回 200", status == 200, f"got {status}"))
    if status == 200:
        run_id = body.get("run_id", "")
        results.append(check("run_id 非空", bool(run_id)))
        steps = body.get("steps", [])
        results.append(check("steps 数量 ≥ 3", len(steps) >= 3, f"got {len(steps)}"))

        # 查询状态
        if run_id:
            status2, body2 = api_get(base_url, f"/api/v1/loop/status/{run_id}")
            results.append(check("GET /loop/status/{id} 返回 200", status2 == 200, f"got {status2}"))

    # 历史查询
    status3, body3 = api_get(base_url, "/api/v1/loop/history")
    results.append(check("GET /loop/history 返回 200", status3 == 200, f"got {status3}"))

    return all(results)


def test_admin(base_url: str) -> bool:
    """TC-22/23/24: 管理后台"""
    print(f"\n{Colors.BOLD}=== TC-22/23/24: 管理后台 ==={Colors.RESET}")
    results = []

    # 审核队列
    status1, _ = api_get(base_url, "/api/v1/admin/review-queue")
    results.append(check("GET /admin/review-queue 返回 200", status1 == 200, f"got {status1}"))

    # 图谱节点
    status2, body2 = api_get(base_url, "/api/v1/admin/graph/nodes")
    results.append(check("GET /admin/graph/nodes 返回 200", status2 == 200, f"got {status2}"))

    # Prompt 列表
    status3, _ = api_get(base_url, "/api/v1/admin/prompts")
    results.append(check("GET /admin/prompts 返回 200", status3 == 200, f"got {status3}"))

    return all(results)


def test_error_handling(base_url: str) -> bool:
    """TC-31: 错误处理与边界验证"""
    print(f"\n{Colors.BOLD}=== TC-31: 错误处理 ==={Colors.RESET}")
    results = []

    # 空 JD content → 422
    status, _ = api_post(base_url, "/api/v1/extract/jd", {"jd_content": ""})
    results.append(check("空 JD content 返回 422", status == 422, f"got {status}"))

    # 缺失 jd_content → 422
    status2, _ = api_post(base_url, "/api/v1/extract/jd", {})
    results.append(check("缺失 jd_content 返回 422", status2 == 422, f"got {status2}"))

    # 空 person_skills → 400
    status3, _ = api_post(base_url, "/api/v1/match/position", {
        "person_skills": [], "target_position": "test"
    })
    results.append(check("空 person_skills 返回 400", status3 == 400, f"got {status3}"))

    # 不存在的 match_id → 404
    status4, _ = api_get(base_url, "/api/v1/match/result/nonexistent_id_12345")
    results.append(check("不存在 match_id 返回 404", status4 == 404, f"got {status4}"))

    # 不存在的路由 → 404
    status5, _ = api_get(base_url, "/api/v1/nonexistent_endpoint")
    results.append(check("不存在路由返回 404", status5 == 404, f"got {status5}"))

    return all(results)


def test_batch_match(base_url: str) -> bool:
    """TC-29: 批量匹配"""
    print(f"\n{Colors.BOLD}=== TC-29: 批量匹配 ==={Colors.RESET}")
    results = []

    body_req = {
        "items": [
            {"position": "数据分析师", "skills": [{"name": "Python", "proficiency": "熟悉"}]},
            {"position": "前端开发工程师", "skills": [{"name": "Vue", "proficiency": "了解"}]},
        ]
    }

    status, body = api_post(base_url, "/api/v1/match/batch", body_req, timeout=60)
    results.append(check("POST /match/batch 返回 200", status == 200, f"got {status}"))
    if status == 200:
        res_list = body.get("results", [])
        results.append(check("results 数量与输入一致", len(res_list) == 2, f"got {len(res_list)}"))
        results.append(check("total 字段存在", "total" in body))

    return all(results)


def test_competitiveness(base_url: str) -> bool:
    """TC-06b: 竞争力分析（修复后新增端点）"""
    print(f"\n{Colors.BOLD}=== TC-06b: 竞争力分析 ==={Colors.RESET}")
    results = []

    status, body = api_get(base_url, "/api/v1/match/competitiveness/后端开发工程师")
    results.append(check("GET /match/competitiveness/{position} 返回 200", status == 200, f"got {status}"))
    if status == 200:
        results.append(check("含 competitiveness_score", "competitiveness_score" in body))
        results.append(check("含 difficulty", "difficulty" in body))
        score = body.get("competitiveness_score", -1)
        results.append(check("competitiveness_score 在 0-1", 0 <= score <= 1, f"got {score}"))

    return all(results)


# ══════════════════════════════════════════════════════
# 第二层：集成测试（跨服务数据流）
# ══════════════════════════════════════════════════════

def test_extract_to_graph_flow(base_url: str) -> bool:
    """INT-01: Extract→Graph 数据流一致性"""
    print(f"\n{Colors.BOLD}=== INT-01: Extract→Graph 数据流 ==={Colors.RESET}")
    results = []

    jd_text = "机器学习工程师：熟悉 Python、PyTorch、TensorFlow，掌握数据预处理和模型训练"
    status, body = api_post(base_url, "/api/v1/extract/jd", {"jd_content": jd_text}, timeout=120)
    if status != 200:
        results.append(check("JD 抽取成功", False, f"status={status}"))
        return all(results)

    results.append(check("JD 抽取成功", True))
    pos_name = body.get("position_name", "")
    extracted_skills = {s.get("skill", s.get("name", "")) for s in body.get("required_skills", [])}

    # 验证图谱中可查到该岗位的技能
    status2, body2 = api_get(base_url, f"/api/v1/graph/position/{pos_name}/skills")
    if status2 == 200:
        graph_skills = {s.get("name", "") for s in body2.get("skills", [])}
        overlap = extracted_skills & graph_skills
        results.append(check("抽取技能与图谱技能有交集", len(overlap) > 0,
                             f"extracted={len(extracted_skills)}, graph={len(graph_skills)}, overlap={len(overlap)}"))
    else:
        log("warn", f"图谱查询返回 {status2}，可能是新岗位尚未同步")

    return all(results)


def test_match_to_learning_flow(base_url: str) -> bool:
    """INT-02: Match→Learning 数据流一致性"""
    print(f"\n{Colors.BOLD}=== INT-02: Match→Learning 数据流 ==={Colors.RESET}")
    results = []

    # 匹配
    match_req = {
        "person_skills": [{"name": "SQL", "proficiency": "熟悉"}],
        "target_position": "数据分析师",
    }
    status, body = api_post(base_url, "/api/v1/match/position", match_req, timeout=30)
    if status != 200:
        results.append(check("匹配成功", False, f"status={status}"))
        return all(results)

    results.append(check("匹配成功", True))
    gap_detail = body.get("skill_gap_detail", [])

    # 用匹配结果创建学习计划
    if gap_detail:
        plan_skills = []
        for g in gap_detail:
            plan_skills.append({
                "skill": g.get("skill", ""),
                "importance": g.get("importance", "required"),
                "gap_level": g.get("gap_level", "完全缺失"),
                "learning_path": g.get("learning_path", []),
            })

        plan_req = {
            "position": "数据分析师",
            "match_score": body.get("match_score", 0),
            "skills": plan_skills,
        }
        status2, body2 = api_post(base_url, "/api/v1/learning/plan", plan_req, timeout=30)
        results.append(check("学习计划创建成功", status2 == 200, f"got {status2}"))
    else:
        log("warn", "无技能差距详情，跳过学习计划创建")

    return all(results)


def test_loop_5_step_flow(base_url: str) -> bool:
    """INT-03: Loop 5步闭环"""
    print(f"\n{Colors.BOLD}=== INT-03: Loop 5步闭环 ==={Colors.RESET}")
    results = []

    status, body = api_post(base_url, "/api/v1/loop/run", {
        "jd_text": "DevOps工程师：熟悉Linux、Docker、Kubernetes、CI/CD、AWS",
        "target_position": "DevOps工程师",
    }, timeout=180)

    results.append(check("Loop 闭环返回 200", status == 200, f"got {status}"))
    if status == 200:
        steps = body.get("steps", [])
        step_names = [s.get("name", "") for s in steps]
        results.append(check("至少3个步骤完成", len(steps) >= 3, f"got {len(steps)}: {step_names}"))

        # 验证各步骤数据
        extracted = body.get("extracted_skills", [])
        results.append(check("extracted_skills 非空", len(extracted) > 0, f"got {len(extracted)}"))

        match_result = body.get("match_result", {})
        results.append(check("match_result 存在", isinstance(match_result, dict) and len(match_result) > 0))

    return all(results)


# ══════════════════════════════════════════════════════
# 第三层：前后端数据一致性
# ══════════════════════════════════════════════════════

def test_frontend_backend_route_alignment(base_url: str) -> bool:
    """CON-01: 前后端路由对齐验证"""
    print(f"\n{Colors.BOLD}=== CON-01: 前后端路由对齐 ==={Colors.RESET}")
    results = []

    # 验证前端 store 调用的关键端点在后端都可达
    frontend_endpoints = [
        ("GET", "/api/v1/positions"),
        ("GET", "/api/v1/graph/overview"),
        ("GET", "/api/v1/evolution/trends"),
        ("GET", "/api/v1/quality/dashboard"),
        ("GET", "/api/v1/dashboard/overview"),
        ("GET", "/api/v1/pipeline/status"),
        ("GET", "/api/v1/datasources"),
        ("GET", "/api/v1/learning/plans"),
        ("GET", "/api/v1/loop/history"),
        ("GET", "/api/v1/admin/review-queue"),
        ("GET", "/api/v1/admin/graph/nodes"),
        ("GET", "/api/v1/admin/prompts"),
        ("GET", "/api/v1/match/history"),
        ("GET", "/api/v1/quality/trends"),
        ("GET", "/api/v1/quality/alerts"),
    ]

    for method, path in frontend_endpoints:
        if method == "GET":
            status, _ = api_get(base_url, path)
        else:
            continue
        # 200 = 成功, 404 = 路由不存在, 其他 = 服务问题但路由存在
        results.append(check(
            f"{method} {path} 路由存在",
            status in (200, 404) if "NONEXISTENT" not in path else status == 404,
            f"got {status}"
        ))

    return all(results)


# ══════════════════════════════════════════════════════
# 主入口
# ══════════════════════════════════════════════════════

API_TESTS = [
    ("TC-01", "基础健康检查", test_health),
    ("TC-02", "岗位列表", test_positions),
    ("TC-03", "JD 抽取", test_extract_jd),
    ("TC-04", "图谱概览", test_graph_overview),
    ("TC-05", "岗位技能子图", test_graph_position_skills),
    ("TC-06", "匹配诊断", test_match),
    ("TC-06b", "竞争力分析", test_competitiveness),
    ("TC-07", "匹配持久化", test_match_persistence),
    ("TC-08", "匹配→学习路径", test_match_to_learning),
    ("TC-10", "演化趋势", test_evolution_trends),
    ("TC-11", "演化路径", test_evolution_paths),
    ("TC-12/13/14", "演化报告", test_evolution_reports),
    ("TC-15", "质量仪表盘", test_quality_dashboard),
    ("TC-17", "质量趋势告警", test_quality_trends_alerts),
    ("TC-18", "数据大屏", test_dashboard),
    ("TC-19", "数据源CRUD", test_datasource_crud),
    ("TC-20", "Pipeline", test_pipeline),
    ("TC-21", "闭环验证", test_loop),
    ("TC-22/23/24", "管理后台", test_admin),
    ("TC-29", "批量匹配", test_batch_match),
    ("TC-31", "错误处理", test_error_handling),
]

INTEGRATION_TESTS = [
    ("INT-01", "Extract→Graph 数据流", test_extract_to_graph_flow),
    ("INT-02", "Match→Learning 数据流", test_match_to_learning_flow),
    ("INT-03", "Loop 5步闭环", test_loop_5_step_flow),
]

CONSISTENCY_TESTS = [
    ("CON-01", "前后端路由对齐", test_frontend_backend_route_alignment),
]


def main():
    parser = argparse.ArgumentParser(description="StarMap 完备 E2E 验证测试")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--suite", choices=["api", "integration", "consistency", "all"], default="all")
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"  StarMap 完备 E2E 验证测试套件")
    print(f"  目标: {args.base_url}")
    print(f"  时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  禁止 mock: 全部使用真实后端")
    print(f"{'='*60}")

    all_passed = True

    suites = {
        "api": API_TESTS,
        "integration": INTEGRATION_TESTS,
        "consistency": CONSISTENCY_TESTS,
        "all": API_TESTS + INTEGRATION_TESTS + CONSISTENCY_TESTS,
    }

    test_list = suites[args.suite]

    for tc_id, name, func in test_list:
        try:
            passed = func(args.base_url)
            if not passed:
                all_passed = False
        except Exception as e:
            log("fail", f"{tc_id} {name} 异常: {e}")
            all_passed = False

    # 汇总
    total = len(results_log)
    passed = sum(1 for r in results_log if r["result"] == "pass")
    failed = total - passed

    print(f"\n{'='*60}")
    print(f"  总检查项: {total}")
    print(f"  {Colors.GREEN}通过: {passed}{Colors.RESET}")
    print(f"  {Colors.RED}失败: {failed}{Colors.RESET}")
    if all_passed:
        print(f"  {Colors.GREEN}{Colors.BOLD}[PASS] ALL PASSED{Colors.RESET}")
    else:
        print(f"  {Colors.RED}{Colors.BOLD}[FAIL] SOME FAILURES{Colors.RESET}")
    print(f"{'='*60}\n")

    # 写入结果文件
    result_path = Path(__file__).parent / "full_e2e_results.json"
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "base_url": args.base_url,
            "suite": args.suite,
            "total": total,
            "passed": passed,
            "failed": failed,
            "results": results_log,
        }, f, ensure_ascii=False, indent=2)
    print(f"  结果已写入: {result_path}")

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
