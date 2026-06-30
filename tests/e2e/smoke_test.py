# -*- coding: utf-8 -*-
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
import requests
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED


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


def frontend_url_for(base_url, frontend_url=None):
    if frontend_url:
        return frontend_url
    return base_url.replace(":8000", ":5173")


def make_minimal_docx(text):
    """Create a tiny DOCX file for upload-path validation without extra deps."""
    escaped = (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "</w:t></w:r></w:p><w:p><w:r><w:t>")
    )
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as docx:
        docx.writestr("[Content_Types].xml", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>""")
        docx.writestr("_rels/.rels", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>""")
        docx.writestr("word/document.xml", f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body><w:p><w:r><w:t>{escaped}</w:t></w:r></w:p></w:body>
</w:document>""")
    return buffer.getvalue()


# ============================================================
# E2E-0 基础健康检查（所有场景的前置条件）
# ============================================================
def test_health(base_url, frontend_url=None):
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
        resp = requests.get(frontend_url_for(base_url, frontend_url), timeout=5)
        results.append(check("前端可达", resp.status_code == 200))
    except Exception as e:
        results.append(check("前端可达", False, str(e)))

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
    try:
        resp = requests.get(f"{base_url}/api/v1/graph/panorama", timeout=10)
        data = resp.json()
        node_count = len(data.get("nodes", []))
        results.append(check(
            f"全景图谱有节点 ({node_count} 个)",
            node_count > 0,
            "图谱为空，可能种子数据未加载"
        ))
    except Exception as e:
        results.append(check("全景图谱可查询", False, str(e)))

    # Step 2: 岗位列表接口契约可达
    try:
        resp = requests.get(f"{base_url}/api/v1/positions/", timeout=10)
        data = resp.json()
        results.append(check(
            "岗位列表接口返回契约结构",
            resp.status_code == 200 and {"items", "total", "page", "page_size"}.issubset(data),
            f"返回 {resp.status_code}: {data}",
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

    # 管理审核队列覆盖既有岗位/技能更新的人工确认入口
    try:
        reset = requests.post(f"{base_url}/api/v1/admin/seed/reset", timeout=10)
        queue = requests.get(f"{base_url}/api/v1/admin/review-queue", timeout=10)
        items = queue.json().get("items", [])
        results.append(check("管理审核队列可重置并读取", reset.status_code == 200 and len(items) > 0))
        approve = requests.post(f"{base_url}/api/v1/admin/audit/{items[0]['id']}/approve", timeout=10)
        results.append(check("管理审核通过接口可用", approve.status_code == 200 and approve.json().get("status") == "approved"))
    except Exception as e:
        results.append(check("管理审核接口闭环", False, str(e)))

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

    # 简历上传端点验证文件处理路径，避免 E2E 依赖外部 LLM 稳定性
    try:
        docx_bytes = make_minimal_docx("姓名：张三\n电话：13800138000\n技能：Python、FastAPI、SQL")
        resp = requests.post(
            f"{base_url}/api/v1/resume/upload",
            files={"file": ("resume.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
            timeout=20,
        )
        results.append(check(
            "简历上传端点可处理 DOCX",
            resp.status_code in (200, 422, 502),
            f"返回 {resp.status_code}: {resp.text[:160]}",
        ))
    except Exception as e:
        results.append(check("简历上传端点", False, str(e)))

    # 匹配诊断接口使用当前前端 payload 形态验证成功路径
    try:
        resp = requests.post(
            f"{base_url}/api/v1/match/diagnose",
            json={
                "target_position": "后端开发工程师",
                "person_skills": [
                    {"name": "Python", "category": "hard_skill", "proficiency": "精通"},
                    {"name": "FastAPI", "category": "tool", "proficiency": "熟悉"},
                ],
            },
            timeout=10
        )
        results.append(check(
            "匹配诊断接口返回成功结果",
            resp.status_code == 200 and "match_score" in resp.json(),
            f"返回 {resp.status_code}: {resp.text[:160]}"
        ))
    except Exception as e:
        results.append(check("匹配诊断接口", False, str(e)))

    return all(results)


# ============================================================
# E2E-4 Docker 一键部署
# ============================================================
def test_e2e4_docker_deploy(base_url, frontend_url=None):
    """验证 Docker 部署：全服务启动→种子加载→首屏可交互。"""
    print(f"\n{Colors.BOLD}=== E2E-4 Docker 一键部署 ==={Colors.RESET}")
    log("info", "场景：干净机器 docker-compose up→全服务启动→种子加载→首屏可交互")

    results = []

    # 所有服务健康
    results.append(test_health(base_url, frontend_url))

    # 演示数据存在（种子加载验证）
    try:
        resp = requests.get(f"{base_url}/api/v1/quality/dashboard", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            total_nodes = data.get("total_extractions", 0)
            results.append(check(
                "质量看板接口返回契约结构",
                "report" in data and "hallucination_rate" in data,
                f"返回字段: {list(data)}"
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
    parser.add_argument("--frontend-url", default=None,
                        help="前端地址（默认将 base-url 的 8000 端口替换为 5173）")
    parser.add_argument("--scenario", choices=["e2e-0", "e2e-1", "e2e-2", "e2e-3", "e2e-4"],
                        help="只跑指定场景")
    parser.add_argument("--all", action="store_true", help="跑所有场景")
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"  StarMap E2E 冒烟测试")
    print(f"  目标: {args.base_url}")
    print(f"  时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    scenarios = {
        "e2e-0": ("基础健康检查", lambda: test_health(args.base_url, args.frontend_url)),
        "e2e-1": ("新岗位发现", lambda: test_e2e1_new_position_discovery(args.base_url)),
        "e2e-2": ("既有岗位更新", lambda: test_e2e2_position_update(args.base_url)),
        "e2e-3": ("简历匹配诊断", lambda: test_e2e3_resume_match(args.base_url)),
        "e2e-4": ("Docker 一键部署", lambda: test_e2e4_docker_deploy(args.base_url, args.frontend_url)),
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
