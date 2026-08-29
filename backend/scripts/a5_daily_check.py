"""A5 公网系统每日探活：健康检查 + 关键接口可用性 + 数据量趋势。

- 探测 https://<PUBLIC_DOMAIN>/health、/ready（nginx 反代 + 后端依赖链）
- 探测核心 API（login → discover），验证认证链路
- 采集 PG/Neo4j 关键数据量，形成日报 JSON + Markdown
- 失败时写 reports/a5/<date>.json 的 failures 字段（供后续告警扩展）

用法（服务器本机，/opt/starmap 下）:
    python3 backend/scripts/a5_daily_check.py

依赖: requests（已装）
输出: reports/a5/YYYY-MM-DD.json + .md
"""
from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE = os.environ.get("A5_BASE_URL", "https://47.120.72.196")
ADMIN = os.environ.get("STARMAP_ADMIN_USER", "admin")
ADMIN_PW = os.environ.get("STARMAP_ADMIN_PASSWORD", "starmap2024")

REPORT_DIR = Path(os.environ.get("A5_REPORT_DIR", "/opt/starmap/reports/a5"))


def _http(method: str, path: str, **kw) -> tuple[int, str]:
    try:
        r = requests.request(method, f"{BASE}{path}", timeout=20, verify=False, **kw)
        return r.status_code, r.text[:500]
    except Exception as exc:  # noqa: BLE001
        return 0, f"{type(exc).__name__}: {exc}"


def _pg(sql: str) -> str:
    try:
        out = subprocess.run(
            ["docker", "exec", "starmap-postgres-prod", "psql", "-U", "starmap",
             "-d", "starmap", "-tAc", sql],
            capture_output=True, text=True, timeout=30,
        )
        return out.stdout.strip() or out.stderr.strip()[:200]
    except Exception as exc:  # noqa: BLE001
        return f"ERR: {exc}"


def _containers_healthy() -> list[dict]:
    try:
        out = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}} {{.Status}}"],
            capture_output=True, text=True, timeout=15,
        )
        rows = []
        for line in out.stdout.strip().splitlines():
            name, status = line.split(" ", 1)
            rows.append({"name": name, "healthy": "healthy" in status, "status": status})
        return rows
    except Exception as exc:  # noqa: BLE001
        return [{"name": "docker", "healthy": False, "status": f"ERR: {exc}"}]


def main() -> int:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    today = dt.date.today().isoformat()
    report: dict = {"date": today, "timestamp": dt.datetime.now().astimezone().isoformat()}

    # 1. 健康检查
    health_code, health_body = _http("GET", "/health")
    ready_code, ready_body = _http("GET", "/ready")
    report["health"] = {"code": health_code, "body": health_body[:200]}
    report["ready"] = {"code": ready_code, "body": ready_body[:200]}

    # 2. 认证 + 模块A discover
    login_code, login_body = _http(
        "POST", "/api/v1/auth/login",
        json={"username": ADMIN, "password": ADMIN_PW},
    )
    token = ""
    if login_code == 200:
        try:
            # _http 截断 body 到 500 字符，登录 token 可能被截断 → 重新完整请求
            r_full = requests.post(
                f"{BASE}/api/v1/auth/login", json={"username": ADMIN, "password": ADMIN_PW},
                timeout=20, verify=False,
            )
            token = r_full.json().get("access_token", "")
        except Exception:  # noqa: BLE001
            token = ""
    report["auth"] = {"code": login_code}
    if token:
        d_code, d_body = _http(
            "POST", "/api/v1/positions/discover",
            headers={"Authorization": f"Bearer {token}"},
        )
        report["discover"] = {"code": d_code, "body": d_body[:300]}
    else:
        report["discover"] = {"code": 0, "body": "auth failed"}

    # 3. 数据量
    report["data"] = {
        "jd_raw": _pg("SELECT count(*) FROM jd_raw;"),
        "positions": _pg("SELECT count(*) FROM position_records;"),
        "changelog": _pg("SELECT count(*) FROM evolution_changelog;"),
        "pipeline_runs": _pg("SELECT count(*) FROM pipeline_runs WHERE status='completed';"),
    }

    # 4. 容器健康
    report["containers"] = _containers_healthy()
    report["all_ok"] = (
        report["health"]["code"] == 200
        and report["ready"]["code"] == 200
        and report["auth"]["code"] == 200
        and report["discover"]["code"] == 200
    )

    # 5. 输出 JSON + Markdown
    json_path = REPORT_DIR / f"{today}.json"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        f"# StarMap A5 每日探活报告 — {today}",
        "",
        f"- 时间: {report['timestamp']}",
        f"- 总体: {'✅ 正常' if report['all_ok'] else '❌ 异常'}",
        "",
        "## 健康检查",
        f"- /health: HTTP {report['health']['code']}",
        f"- /ready: HTTP {report['ready']['code']}",
        "",
        "## 核心接口",
        f"- 登录: HTTP {report['auth']['code']}",
        f"- 模块A discover: HTTP {report['discover']['code']}",
        "",
        "## 数据量",
        f"- jd_raw: {report['data']['jd_raw']}",
        f"- position_records: {report['data']['positions']}",
        f"- evolution_changelog: {report['data']['changelog']}",
        f"- 已完成 pipeline: {report['data']['pipeline_runs']}",
        "",
        "## 容器",
    ]
    for c in report["containers"]:
        mark = "✅" if c["healthy"] else "❌"
        lines.append(f"- {mark} {c['name']}: {c['status']}")
    md_path = REPORT_DIR / f"{today}.md"
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\nwritten: {json_path} / {md_path}")
    return 0 if report["all_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
