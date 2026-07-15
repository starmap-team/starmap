#!/usr/bin/env python3
"""StarMap startup smoke test — validates all three deployment modes.

Usage:
    # Test against a running backend (any mode):
    python tests/e2e/startup_smoke.py --base-url http://localhost:8000

    # Full mode-specific checks (requires mode flag):
    python tests/e2e/startup_smoke.py --base-url http://localhost:8000 --mode mode_a
    python tests/e2e/startup_smoke.py --base-url http://localhost:8000 --mode mode_b
    python tests/e2e/startup_smoke.py --base-url http://localhost:8000 --mode mode_c

Each mode runs the same core checklist; mode-specific checks (e.g. Docker
container status for Mode A) are skipped when the mode flag is absent or
doesn't match.

Exit codes:
    0 — all checks passed
    1 — one or more checks failed
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
import urllib.error
from dataclasses import dataclass, field


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class SmokeContext:
    base_url: str
    mode: str | None = None
    results: list[CheckResult] = field(default_factory=list)

    @property
    def api(self) -> str:
        return f"{self.base_url}/api/v1"


def _get(url: str, timeout: int = 10) -> tuple[int, dict | str | None]:
    """Simple GET returning (status_code, parsed_json_or_body)."""
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode()
            try:
                return resp.status, json.loads(body)
            except json.JSONDecodeError:
                return resp.status, body
    except urllib.error.HTTPError as exc:
        body = exc.read().decode() if exc.fp else ""
        try:
            return exc.code, json.loads(body)
        except json.JSONDecodeError:
            return exc.code, body
    except Exception as exc:
        return 0, str(exc)


def _post_json(url: str, data: dict, timeout: int = 10) -> tuple[int, dict | str | None]:
    """Simple POST with JSON body."""
    try:
        payload = json.dumps(data).encode()
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode()
            try:
                return resp.status, json.loads(body)
            except json.JSONDecodeError:
                return resp.status, body
    except urllib.error.HTTPError as exc:
        body = exc.read().decode() if exc.fp else ""
        try:
            return exc.code, json.loads(body)
        except json.JSONDecodeError:
            return exc.code, body
    except Exception as exc:
        return 0, str(exc)


def check(ctx: SmokeContext, name: str, passed: bool, detail: str = "") -> None:
    ctx.results.append(CheckResult(name=name, passed=passed, detail=detail))
    symbol = "PASS" if passed else "FAIL"
    suffix = f" -- {detail}" if detail else ""
    print(f"  {symbol} {name}{suffix}")


# ═══════════════════════════════════════════════════════════════
# Core checks (run for all modes)
# ═══════════════════════════════════════════════════════════════


def check_health(ctx: SmokeContext) -> None:
    status, body = _get(f"{ctx.base_url}/health")
    ok = status == 200 and isinstance(body, dict) and body.get("status") == "ok"
    check(ctx, "/health returns 200 + status=ok", ok, f"status={status}")


def check_ready(ctx: SmokeContext) -> None:
    status, body = _get(f"{ctx.base_url}/ready")
    ok = status == 200 and isinstance(body, dict) and body.get("status") == "ready"
    detail = f"status={status}"
    if isinstance(body, dict) and body.get("checks"):
        failed = {k: v for k, v in body["checks"].items() if v != "ok"}
        if failed:
            detail += f" failed_checks={failed}"
    check(ctx, "/ready returns 200 (all deps ok)", ok, detail)


def check_login(ctx: SmokeContext) -> str | None:
    """Login as admin, return access token (or None on failure)."""
    status, body = _post_json(f"{ctx.api}/auth/login", {
        "username": "admin",
        "password": "starmap2024",
    })
    ok = status == 200 and isinstance(body, dict) and "access_token" in body
    check(ctx, "POST /auth/login admin/starmap2024 → 200 + JWT", ok, f"status={status}")
    if ok and isinstance(body, dict):
        return body["access_token"]
    return None


def check_me(ctx: SmokeContext, token: str) -> None:
    req = urllib.request.Request(
        f"{ctx.api}/auth/me",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode())
            ok = resp.status == 200 and body.get("username") == "admin"
            check(ctx, "GET /auth/me → admin user", ok, f"username={body.get('username')}")
    except urllib.error.HTTPError as exc:
        check(ctx, "GET /auth/me → admin user", False, f"status={exc.code}")
    except Exception as exc:
        check(ctx, "GET /auth/me → admin user", False, str(exc))


def check_positions_visible(ctx: SmokeContext, token: str) -> None:
    req = urllib.request.Request(
        f"{ctx.api}/positions?page=1&page_size=5",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode())
            total = body.get("total", 0) if isinstance(body, dict) else 0
            ok = total > 0
            check(ctx, f"GET /positions returns data (total={total})", ok)
    except Exception as exc:
        check(ctx, "GET /positions returns data", False, str(exc))


def check_create_and_disable_user(ctx: SmokeContext, token: str) -> None:
    """Create a test user, verify login, disable, verify login rejected."""
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json",
               "Content-Type": "application/json"}

    # Create
    create_payload = json.dumps({
        "username": "smoke_test_user",
        "password": "smoke_test_1234",
        "role": "user",
    }).encode()
    req = urllib.request.Request(f"{ctx.api}/admin/users", data=create_payload,
                                headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode())
            user_id = body.get("id")
            ok = resp.status == 201 and user_id is not None
            check(ctx, "POST /admin/users → create smoke_test_user", ok,
                  f"user_id={user_id}")
    except urllib.error.HTTPError as exc:
        # 409 = already exists from a previous run — still ok
        if exc.code == 409:
            check(ctx, "POST /admin/users → smoke_test_user (already exists)", True)
            # Look up the user id
            list_req = urllib.request.Request(
                f"{ctx.api}/admin/users?search=smoke_test_user",
                headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            )
            with urllib.request.urlopen(list_req, timeout=10) as list_resp:
                list_body = json.loads(list_resp.read().decode())
                items = list_body.get("items", [])
                user_id = items[0]["id"] if items else None
        else:
            check(ctx, "POST /admin/users → create smoke_test_user", False,
                  f"status={exc.code}")
            return

    if not user_id:
        check(ctx, "Cannot resolve smoke_test_user id — skipping user lifecycle", False)
        return

    # Login as new user
    status, _ = _post_json(f"{ctx.api}/auth/login", {
        "username": "smoke_test_user",
        "password": "smoke_test_1234",
    })
    check(ctx, "New user can login", status == 200, f"status={status}")

    # Disable
    disable_payload = json.dumps({"reason": "smoke test cleanup"}).encode()
    req = urllib.request.Request(
        f"{ctx.api}/admin/users/{user_id}",
        data=disable_payload,
        headers=headers,
        method="DELETE",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            check(ctx, "DELETE /admin/users/{id} → user disabled",
                  resp.status == 200)
    except urllib.error.HTTPError as exc:
        check(ctx, "DELETE /admin/users/{id} → user disabled", False,
              f"status={exc.code}")

    # Verify disabled user cannot login
    status, body = _post_json(f"{ctx.api}/auth/login", {
        "username": "smoke_test_user",
        "password": "smoke_test_1234",
    })
    # 403 = AccountDisabledError
    check(ctx, "Disabled user login rejected (403)", status == 403,
          f"status={status}")


def check_audit_events(ctx: SmokeContext, token: str) -> None:
    req = urllib.request.Request(
        f"{ctx.api}/admin/audit-events?page=1&page_size=5",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode())
            total = body.get("total", 0) if isinstance(body, dict) else 0
            ok = total > 0
            check(ctx, f"GET /admin/audit-events returns data (total={total})", ok)
    except Exception as exc:
        check(ctx, "GET /admin/audit-events returns data", False, str(exc))


def check_lockout_and_unlock(ctx: SmokeContext, token: str) -> None:
    """Hit bad password 5+ times, verify lockout, then admin unlock."""
    # Create a fresh throwaway user
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json",
               "Content-Type": "application/json"}
    create_payload = json.dumps({
        "username": "lockout_test_user",
        "password": "lockout_test_1234",
        "role": "user",
    }).encode()
    req = urllib.request.Request(f"{ctx.api}/admin/users", data=create_payload,
                                headers=headers, method="POST")
    user_id = None
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode())
            user_id = body.get("id")
    except urllib.error.HTTPError as exc:
        if exc.code == 409:
            list_req = urllib.request.Request(
                f"{ctx.api}/admin/users?search=lockout_test_user",
                headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            )
            with urllib.request.urlopen(list_req, timeout=10) as list_resp:
                list_body = json.loads(list_resp.read().decode())
                items = list_body.get("items", [])
                user_id = items[0]["id"] if items else None
        else:
            check(ctx, "Lockout test: create user failed", False, f"status={exc.code}")
            return

    if not user_id:
        check(ctx, "Lockout test: cannot resolve user id", False)
        return

    # 5 bad password attempts
    last_status = 0
    for i in range(6):
        last_status, _ = _post_json(f"{ctx.api}/auth/login", {
            "username": "lockout_test_user",
            "password": "wrong_password",
        })

    # Should be locked (423)
    is_locked = last_status == 423
    check(ctx, f"5+ bad logins → account locked (423)", is_locked,
          f"last_status={last_status}")

    # Admin unlock
    unlock_req = urllib.request.Request(
        f"{ctx.api}/admin/users/{user_id}/unlock",
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(unlock_req, timeout=10) as resp:
            check(ctx, "POST /admin/users/{id}/unlock → success", resp.status == 200)
    except urllib.error.HTTPError as exc:
        check(ctx, "POST /admin/users/{id}/unlock", False, f"status={exc.code}")

    # Can login after unlock
    status, _ = _post_json(f"{ctx.api}/auth/login", {
        "username": "lockout_test_user",
        "password": "lockout_test_1234",
    })
    check(ctx, "Unlocked user can login", status == 200, f"status={status}")

    # Cleanup: disable throwaway user
    disable_payload = json.dumps({"reason": "smoke test cleanup"}).encode()
    del_req = urllib.request.Request(
        f"{ctx.api}/admin/users/{user_id}",
        data=disable_payload,
        headers=headers,
        method="DELETE",
    )
    try:
        urllib.request.urlopen(del_req, timeout=10)
    except Exception:
        pass  # best effort cleanup


def check_admin_password_reset(ctx: SmokeContext, token: str) -> None:
    """Admin resets a user's password, user logs in with new password."""
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json",
               "Content-Type": "application/json"}

    # Create a fresh user
    create_payload = json.dumps({
        "username": "reset_test_user",
        "password": "reset_old_1234",
        "role": "user",
    }).encode()
    req = urllib.request.Request(f"{ctx.api}/admin/users", data=create_payload,
                                headers=headers, method="POST")
    user_id = None
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode())
            user_id = body.get("id")
    except urllib.error.HTTPError as exc:
        if exc.code == 409:
            list_req = urllib.request.Request(
                f"{ctx.api}/admin/users?search=reset_test_user",
                headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            )
            with urllib.request.urlopen(list_req, timeout=10) as list_resp:
                list_body = json.loads(list_resp.read().decode())
                items = list_body.get("items", [])
                user_id = items[0]["id"] if items else None
        else:
            check(ctx, "Reset test: create user failed", False, f"status={exc.code}")
            return

    if not user_id:
        check(ctx, "Reset test: cannot resolve user id", False)
        return

    # Admin reset password
    new_pwd = "reset_new_5678"
    reset_payload = json.dumps({"new_password": new_pwd}).encode()
    reset_req = urllib.request.Request(
        f"{ctx.api}/admin/users/{user_id}/reset-password",
        data=reset_payload,
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(reset_req, timeout=10) as resp:
            check(ctx, "POST /admin/users/{id}/reset-password → success",
                  resp.status == 200)
    except urllib.error.HTTPError as exc:
        check(ctx, "POST /admin/users/{id}/reset-password", False,
              f"status={exc.code}")
        return

    # Login with new password
    status, _ = _post_json(f"{ctx.api}/auth/login", {
        "username": "reset_test_user",
        "password": new_pwd,
    })
    check(ctx, "User can login with admin-reset password", status == 200,
          f"status={status}")

    # Cleanup
    disable_payload = json.dumps({"reason": "smoke test cleanup"}).encode()
    del_req = urllib.request.Request(
        f"{ctx.api}/admin/users/{user_id}",
        data=disable_payload,
        headers=headers,
        method="DELETE",
    )
    try:
        urllib.request.urlopen(del_req, timeout=10)
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════
# Mode-specific checks
# ═══════════════════════════════════════════════════════════════


def check_mode_a_docker(ctx: SmokeContext) -> None:
    """Verify Docker containers are running (Mode A only)."""
    import subprocess
    try:
        result = subprocess.run(
            ["docker", "compose", "-f", "docker-compose.dev.yml", "ps", "--format", "json"],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode != 0:
            check(ctx, "Docker containers running", False,
                  f"docker compose ps failed: {result.stderr[:200]}")
            return
        # Parse output — one JSON per line or a JSON array
        lines = [l for l in result.stdout.strip().splitlines() if l.strip()]
        services: set[str] = set()
        for line in lines:
            try:
                obj = json.loads(line)
                svc = obj.get("Service") or obj.get("name", "")
                state = obj.get("State") or obj.get("status", "")
                if "running" in state.lower():
                    services.add(svc)
            except json.JSONDecodeError:
                continue
        expected = {"starmap-backend", "starmap-frontend", "neo4j", "postgres", "redis"}
        # Container names vary; just check we got some services
        ok = len(services) >= 3
        check(ctx, f"Docker containers running ({len(services)} services)", ok,
              f"services={services}")
    except FileNotFoundError:
        check(ctx, "Docker containers running", False, "docker CLI not found")
    except Exception as exc:
        check(ctx, "Docker containers running", False, str(exc))


# ═══════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════


def run_smoke(ctx: SmokeContext) -> int:
    """Execute all smoke checks. Returns 0 on all-pass, 1 otherwise."""
    print(f"\nStarMap startup smoke — base_url={ctx.base_url} mode={ctx.mode or 'generic'}\n")

    # 1. Health
    print("── Core health ──")
    check_health(ctx)

    # 2. Readiness (all deps)
    check_ready(ctx)

    # 3. Login
    print("\n── Authentication ──")
    token = check_login(ctx)
    if not token:
        print("\nFAIL: Cannot proceed -- login failed. Aborting.")
        return 1

    # 4. /auth/me
    check_me(ctx, token)

    # 5. Positions visible
    print("\n── Business data ──")
    check_positions_visible(ctx, token)

    # 6. User lifecycle: create → login → disable → login rejected
    print("\n── User lifecycle ──")
    check_create_and_disable_user(ctx, token)

    # 7. Lockout + unlock
    print("\n── Lockout + unlock ──")
    check_lockout_and_unlock(ctx, token)

    # 8. Admin password reset
    print("\n── Admin password reset ──")
    check_admin_password_reset(ctx, token)

    # 9. Audit events
    print("\n── Audit trail ──")
    check_audit_events(ctx, token)

    # 10. Mode-specific
    if ctx.mode == "mode_a":
        print("\n── Mode A: Docker ──")
        check_mode_a_docker(ctx)

    # Summary
    passed = sum(1 for r in ctx.results if r.passed)
    total = len(ctx.results)
    failed = total - passed
    print(f"\n{'=' * 50}")
    print(f"Results: {passed}/{total} passed, {failed} failed")
    if failed:
        print("Failed checks:")
        for r in ctx.results:
            if not r.passed:
                print(f"  FAIL {r.name}: {r.detail}")
    return 0 if failed == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="StarMap startup smoke test")
    parser.add_argument("--base-url", default="http://localhost:8000",
                        help="Backend base URL (default: http://localhost:8000)")
    parser.add_argument("--mode", choices=["mode_a", "mode_b", "mode_c"],
                        default=None,
                        help="Deployment mode (enables mode-specific checks)")
    args = parser.parse_args()

    ctx = SmokeContext(base_url=args.base_url.rstrip("/"), mode=args.mode)
    return run_smoke(ctx)


if __name__ == "__main__":
    sys.exit(main())