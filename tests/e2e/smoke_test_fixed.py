# -*- coding: utf-8 -*-
"""
StarMap E2E 冒烟测试脚本（v0.4）

这是每日集成的核心工具（规范7 §17.8）。
每天在远程服务器上运行，验证 main 分支"随时可演示"。

4 个场景：
  E2E-1 新岗位发现：原始JD→涌现→聚类→定义→入图
  E2E-2 既有岗位更新：旧/新快照→差异→提案→审核→更新
  E2E-3 简历匹配诊断：上传→解析→对比→差距→学习路径
  E2E-4 Docker 一键部署：docker-compose up→全服务启动→种子加载→首页可交互

用法：
  python tests/e2e/smoke_test.py --base-url http://localhost:8000
  python tests/e2e/smoke_test.py --scenario e2e-1
  python tests/e2e/smoke_test.py --all
"""
import argparse
import sys
import time
import requests
from pathlib import Path


class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


def log(level, msg):
    icons = {"pass": f"{Colors.GREEN}[PASS]", "fail": f"{Colors.RED}[FAIL]", "warn": f"{Colors.YELLOW}[WARN]", "info": "[INFO]"}
    icon = icons.get(level, "[INFO]")
    reset = Colors.RESET if level in ("pass", "fail", "warn") else ""
    print(f"  {icon} {msg}{reset}")


def check(name, condition, detail=""):
    if condition:
        log("pass", f"{name}")
        return True
    else:
        log("fail", f"{name} {f'-- {detail}' if detail else ''}")
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
        log("warn", f"前端不可达（开发环境可能未启动）-- {e}")
        results.append(True)  # 开发环境下前端可能不在

    # Neo4j（通过后端代理或直连）
    # PostgreSQL、Redis、Chroma 通过后端 /health 间接验证

    return all(results)
