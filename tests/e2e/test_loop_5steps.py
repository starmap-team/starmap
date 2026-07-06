"""
StarMap E2E 闭环 5 步验证测试 (LOOP-FLOW-02)

验证从 POST /loop/run 触发的闭环 5 步全真执行：
  1. JD input validation
  2. Skill extraction (LLM)
  3. Graph update (Neo4j)
  4. Match diagnosis
  5. Learning path generation

严苛闭环策略（D-01）：任意一步失败立即标 FAILED，不静默降级。
Neo4j/LLM 不可用时 FAILED 冒泡（D-04），不允许假成功。

用法：
  python tests/e2e/test_loop_5steps.py --base-url http://localhost:8000
"""

import argparse
import sys
import time
import requests


class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


def log(level, msg):
    icons = {
        "pass": f"{Colors.GREEN}[PASS]",
        "fail": f"{Colors.RED}[FAIL]",
        "warn": f"{Colors.YELLOW}[WARN]",
        "info": "[INFO]",
    }
    icon = icons.get(level, "[INFO]")
    reset = Colors.RESET if level in ("pass", "fail", "warn") else ""
    try:
        print(f"  {icon} {msg}{reset}")
    except UnicodeEncodeError:
        safe = f"  {icon} {msg}{reset}".encode("ascii", errors="replace").decode("ascii", errors="replace")
        print(safe)


def check(name, condition, detail=""):
    if condition:
        log("pass", f"{name}")
        return True
    else:
        log("fail", f"{name} {f'— {detail}' if detail else ''}")
        return False


# Sample JD text for testing
SAMPLE_JD = """高级后端工程师 岗位职责：负责核心API设计与系统架构 任职要求：3年以上Python开发经验 熟悉FastAPI 熟悉PostgreSQL和Redis"""
SAMPLE_TARGET = "高级后端工程师"


def test_loop_5steps(base_url):
    """验证闭环 5 步全真执行。"""
    print(f"\n{Colors.BOLD}=== 闭环 5 步验证 (LOOP-FLOW-02) ==={Colors.RESET}")
    log("info", "策略: 严苛闭环 — 任意步骤失败即 FAILED (D-01/D-04)")

    results = []

    # Step 1: Trigger closed-loop run
    print(f"\n{Colors.BOLD}[Step 1] 触发闭环运行{Colors.RESET}")
    try:
        resp = requests.post(
            f"{base_url}/api/v1/loop/run",
            json={
                "jd_text": SAMPLE_JD,
                "target_position": SAMPLE_TARGET,
            },
            timeout=120,
        )
        results.append(check(
            "POST /loop/run 返回 200",
            resp.status_code == 200,
            f"返回 {resp.status_code}: {resp.text[:200] if resp.status_code != 200 else ''}",
        ))
        if resp.status_code != 200:
            log("fail", f"闭环触发失败，无法继续验证: {resp.text[:300]}")
            return False

        loop_data = resp.json()
        run_id = loop_data.get("run_id", "")
        status = loop_data.get("status", "")
        steps = loop_data.get("steps", [])

        results.append(check("闭环返回 run_id", bool(run_id), "run_id 为空"))
        results.append(check(
            "闭环状态为 completed",
            status == "completed",
            f"状态为 {status}（D-01: 非 completed 即 failed）",
        ))
    except requests.exceptions.Timeout:
        results.append(check("POST /loop/run 在 120s 内完成", False, "请求超时"))
        return False
    except Exception as e:
        results.append(check("POST /loop/run 可达", False, str(e)))
        return False

    if not run_id:
        log("fail", "无 run_id，无法继续验证后续 API")
        return False

    # Step 2: Verify each of the 5 steps
    print(f"\n{Colors.BOLD}[Step 2] 验证 5 步执行结果{Colors.RESET}")
    step_names = [
        "JD input validation",
        "Skill extraction (LLM)",
        "Graph update (Neo4j)",
        "Match diagnosis",
        "Learning path generation",
    ]

    if not steps:
        results.append(check("闭环返回步骤列表", False, "steps 为空"))
    else:
        for i, step in enumerate(steps):
            step_num = step.get("step", i + 1)
            step_name = step.get("name", step_names[i] if i < len(step_names) else f"Step {step_num}")
            step_status = step.get("status", "")
            step_error = step.get("error", "")

            if step_status.upper() == "SUCCESS":
                results.append(check(
                    f"Step {step_num}: {step_name}",
                    True,
                ))
            else:
                results.append(check(
                    f"Step {step_num}: {step_name}",
                    False,
                    f"status={step_status}, error={step_error or 'N/A'} (D-04: FAILED 必须冒泡)",
                ))

    # Extract IDs for downstream verification
    match_result = loop_data.get("match_result", {})
    learning_path = loop_data.get("learning_path", {})
    match_id = match_result.get("match_id", "")
    plan_id = learning_path.get("plan_id", "")

    # Step 3: Verify API reachability (D-14: 5 API calls)
    print(f"\n{Colors.BOLD}[Step 3] 验证 API 贯通性 (D-14){Colors.RESET}")

    # 3a. GET /loop/status/{run_id}
    try:
        resp = requests.get(
            f"{base_url}/api/v1/loop/status/{run_id}",
            timeout=10,
        )
        results.append(check(
            "GET /loop/status/{run_id} 返回 200",
            resp.status_code == 200,
            f"返回 {resp.status_code}",
        ))
    except Exception as e:
        results.append(check("GET /loop/status/{run_id}", False, str(e)))

    # 3b. GET /match/result/{match_id} (if match_id exists)
    if match_id:
        try:
            resp = requests.get(
                f"{base_url}/api/v1/match/result/{match_id}",
                timeout=10,
            )
            results.append(check(
                "GET /match/result/{match_id} 返回 200",
                resp.status_code == 200,
                f"返回 {resp.status_code}",
            ))
        except Exception as e:
            results.append(check("GET /match/result/{match_id}", False, str(e)))
    else:
        log("warn", "无 match_id，跳过匹配结果验证")

    # 3c. GET /learning/plan/{plan_id} (MATCH-LEARN-01/02)
    if plan_id:
        try:
            resp = requests.get(
                f"{base_url}/api/v1/learning/plan/{plan_id}",
                timeout=10,
            )
            results.append(check(
                "GET /learning/plan/{plan_id} 返回 200 (MATCH-LEARN-01/02)",
                resp.status_code == 200,
                f"返回 {resp.status_code}",
            ))
        except Exception as e:
            results.append(check("GET /learning/plan/{plan_id}", False, str(e)))
    else:
        log("warn", "无 plan_id，跳过学习计划验证")

    # 3d. GET /quality/dashboard — returns non-empty metrics
    try:
        resp = requests.get(
            f"{base_url}/api/v1/quality/dashboard",
            timeout=10,
        )
        results.append(check(
            "GET /quality/dashboard 返回 200",
            resp.status_code == 200,
            f"返回 {resp.status_code}",
        ))
    except Exception as e:
        results.append(check("GET /quality/dashboard", False, str(e)))

    # 3e. GET /evolution/trends — no 500 error
    try:
        resp = requests.get(
            f"{base_url}/api/v1/evolution/trends",
            timeout=10,
        )
        results.append(check(
            "GET /evolution/trends 不返回 500",
            resp.status_code != 500,
            f"返回 {resp.status_code}",
        ))
    except Exception as e:
        results.append(check("GET /evolution/trends", False, str(e)))

    return all(results)


def main():
    parser = argparse.ArgumentParser(description="StarMap E2E 闭环 5 步验证")
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="后端 API 地址（默认 http://localhost:8000）",
    )
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"  StarMap E2E 闭环 5 步验证")
    print(f"  目标: {args.base_url}")
    print(f"  时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    # Pre-check: backend must be reachable
    try:
        resp = requests.get(f"{args.base_url}/health", timeout=5)
        if resp.status_code != 200:
            print(f"\n{Colors.RED}后端不可达（/health 返回 {resp.status_code}）{Colors.RESET}")
            print("请确保后端服务已启动: cd backend && poetry run uvicorn app.main:app --reload")
            sys.exit(1)
    except Exception as e:
        print(f"\n{Colors.RED}后端不可达: {e}{Colors.RESET}")
        print("请确保后端服务已启动: cd backend && poetry run uvicorn app.main:app --reload")
        sys.exit(1)

    all_passed = test_loop_5steps(args.base_url)

    print(f"\n{'='*60}")
    if all_passed:
        print(f"  {Colors.GREEN}{Colors.BOLD}[PASS] 闭环 5 步验证通过{Colors.RESET}")
    else:
        print(f"  {Colors.RED}{Colors.BOLD}[FAIL] 闭环 5 步验证失败{Colors.RESET}")
    print(f"{'='*60}\n")

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
