"""Comprehensive verification suite for the login module fixes.

Tests run against the running stack (localhost:8000 backend) to verify:
  FIX-1: config.py sslmode → ssl fix (no migration crash)
  FIX-2: migrations ran in starmap-postgres-prod
  FIX-3: admin user seeded
  Integration: login + me + refresh + logout end-to-end
  Edge cases: validation, lockout, enumeration resistance
"""
import json
import sys
import time
from urllib import request, error

BACKEND = "http://localhost:8000"
PROXY_PORTS = [5173, 5183, 5188]  # any of the vite dev servers
PASS = []
FAIL = []


def call(method: str, path: str, body: dict | None = None,
         headers: dict | None = None, base: str = BACKEND) -> tuple[int, dict, dict]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = request.Request(
        f"{base}{path}", data=data, method=method,
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    try:
        with request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read()), dict(resp.headers)
    except error.HTTPError as e:
        try:
            payload = json.loads(e.read())
        except Exception:
            payload = {"_raw": "non-json"}
        return e.code, payload, dict(e.headers)


def check(name: str, ok: bool, detail: str = "") -> None:
    (PASS if ok else FAIL).append((name, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}  {detail}")


# ── Phase 1: Schema verification (FIX-1 + FIX-2) ──────────────────────
print("\n" + "=" * 72)
print("PHASE 1 — Schema verification (FIX-1 ssl, FIX-2 migrations)")
print("=" * 72)

s, b, _ = call("GET", "/api/v1/ready")
check("/ready returns 200 (or 503)", s in (200, 503), f"status={s}")
check("postgres=ok", b.get("checks", {}).get("postgres") == "ok",
      f"checks.postgres={b.get('checks', {}).get('postgres')}")
check("alembic=ok (FIX-2 effective)", b.get("checks", {}).get("alembic") == "ok",
      f"checks.alembic={b.get('checks', {}).get('alembic')}")
check("users_seeded=ok (FIX-3 effective)", b.get("checks", {}).get("users_seeded") == "ok",
      f"checks.users_seeded={b.get('checks', {}).get('users_seeded')}")
check("redis=ok", b.get("checks", {}).get("redis") == "ok",
      f"checks.redis={b.get('checks', {}).get('redis')}")

# ── Phase 2: Login core (FIX-3) ────────────────────────────────────────
print("\n" + "=" * 72)
print("PHASE 2 — Login core")
print("=" * 72)

# Unlock admin first (in case earlier tests locked it)
print("  (unlock admin pre-test)")
try:
    import subprocess
    subprocess.run(
        ["docker", "exec", "starmap-postgres-prod", "psql", "-U", "starmap", "-d", "starmap",
         "-c", "UPDATE users SET failed_login_attempts=0, locked_until=NULL WHERE username='admin';"],
        check=False, capture_output=True, timeout=10,
    )
except Exception as e:
    print(f"    (unlock skipped: {e})")

s, b, _ = call("POST", "/api/v1/auth/login",
               {"username": "admin", "password": "starmap2024"})
check("Valid login → 200", s == 200, f"status={s}")
check("Returns access_token", bool(b.get("access_token")), "")
check("Returns refresh_token", bool(b.get("refresh_token")), "")
check("User role=admin", b.get("user", {}).get("role") == "admin", "")
check("expires_in=900 (15 min)", b.get("expires_in") == 900,
      f"got {b.get('expires_in')}")
check("must_change_password=false", b.get("user", {}).get("must_change_password") is False, "")

access = b.get("access_token") if s == 200 else None
refresh = b.get("refresh_token") if s == 200 else None

# Wrong password
s, b, _ = call("POST", "/api/v1/auth/login",
               {"username": "admin", "password": "wrong_pw_123"})
check("Wrong password → 401", s == 401, f"status={s}")
check("Wrong password Chinese msg", "用户名或密码错误" in str(b.get("detail", "")), f"detail={b.get('detail')}")

# Non-existent user
s, b, _ = call("POST", "/api/v1/auth/login",
               {"username": "ghost_user_xyz_999", "password": "anything"})
check("Non-existent user → 401", s == 401, f"status={s}")
check("Non-existent user same Chinese msg (no enumeration)",
      "用户名或密码错误" in str(b.get("detail", "")), f"detail={b.get('detail')}")

# Pydantic validation
s, b, _ = call("POST", "/api/v1/auth/login", {"username": "", "password": "x"})
check("Empty username → 422", s == 422, f"status={s}")
s, b, _ = call("POST", "/api/v1/auth/login", {"username": "admin", "password": ""})
check("Empty password → 422", s == 422, f"status={s}")
s, b, _ = call("POST", "/api/v1/auth/login", {})
check("Missing fields → 422", s == 422, f"status={s}")

# ── Phase 3: Token lifecycle ──────────────────────────────────────────
print("\n" + "=" * 72)
print("PHASE 3 — Token lifecycle")
print("=" * 72)

# /me with valid token
s, b, _ = call("GET", "/api/v1/auth/me", headers={"Authorization": f"Bearer {access}"})
check("/me with Bearer → 200", s == 200, f"status={s}")
check("/me returns username=admin", b.get("username") == "admin", f"got {b.get('username')}")

# /me without token
s, b, _ = call("GET", "/api/v1/auth/me")
check("/me without token → 401", s == 401, f"status={s}")

# /me with garbage token
s, b, _ = call("GET", "/api/v1/auth/me", headers={"Authorization": "Bearer garbage.token.here"})
check("/me with garbage → 401", s == 401, f"status={s}")

# Refresh with valid token
s, b, _ = call("POST", "/api/v1/auth/refresh", {"refresh_token": refresh})
check("Refresh valid token → 200", s == 200, f"status={s}")
check("Refresh returns new access_token", bool(b.get("access_token")), "")

# Refresh with invalid
s, b, _ = call("POST", "/api/v1/auth/refresh", {"refresh_token": "garbage"})
check("Refresh invalid → 401", s == 401, f"status={s}")

# Logout
s, b, _ = call("POST", "/api/v1/auth/logout", {"refresh_token": refresh})
check("Logout → 200", s == 200, f"status={s}")
check("Logout revoked=1", b.get("revoked") == 1, f"got {b.get('revoked')}")

# Refresh after logout should fail
s, b, _ = call("POST", "/api/v1/auth/refresh", {"refresh_token": refresh})
check("Refresh after logout → 401", s == 401, f"status={s}")

# ── Phase 4: Lockout policy ───────────────────────────────────────────
print("\n" + "=" * 72)
print("PHASE 4 — Lockout policy")
print("=" * 72)

# Unlock before testing
import subprocess
subprocess.run(
    ["docker", "exec", "starmap-postgres-prod", "psql", "-U", "starmap", "-d", "starmap",
     "-c", "UPDATE users SET failed_login_attempts=0, locked_until=NULL WHERE username='admin';"],
    check=False, capture_output=True, timeout=10,
)
time.sleep(0.5)

locked_at_attempt = None
for i in range(7):
    s, b, _ = call("POST", "/api/v1/auth/login",
                   {"username": "admin", "password": f"locktest_{i}"})
    if s == 423 or "锁定" in str(b.get("detail", "")):
        locked_at_attempt = i + 1
        check(f"Lockout triggered after {locked_at_attempt} wrong attempts",
              "锁定" in str(b.get("detail", "")),
              f"detail='{b.get('detail')}'")
        break
check("Lockout within 5 attempts", locked_at_attempt is not None and locked_at_attempt <= 5,
      f"triggered at attempt {locked_at_attempt}")

# Correct password while locked → still 423
s, b, _ = call("POST", "/api/v1/auth/login",
               {"username": "admin", "password": "starmap2024"})
check("Correct password while locked → 423", s == 423,
      f"status={s}, detail='{b.get('detail')}'")

# Unlock for cleanup
subprocess.run(
    ["docker", "exec", "starmap-postgres-prod", "psql", "-U", "starmap", "-d", "starmap",
     "-c", "UPDATE users SET failed_login_attempts=0, locked_until=NULL WHERE username='admin';"],
    check=False, capture_output=True, timeout=10,
)

# ── Phase 5: Frontend through vite proxy ──────────────────────────────
print("\n" + "=" * 72)
print("PHASE 5 — Frontend through vite proxy (zombie 5173 + dev 5188)")
print("=" * 72)

# Pick the first reachable vite port
working_proxy = None
for port in PROXY_PORTS:
    try:
        s, b, h = call("POST", "/api/v1/auth/login",
                       {"username": "admin", "password": "starmap2024"},
                       headers={"Origin": f"http://localhost:{port}"},
                       base=f"http://localhost:{port}")
        if s == 200:
            working_proxy = port
            check(f"vite:{port} login works", True,
                  f"got 200, CORS={h.get('Access-Control-Allow-Origin', 'N/A')}")
            break
        else:
            check(f"vite:{port} login", False, f"status={s}")
    except Exception as e:
        check(f"vite:{port} login", False, f"connection error: {e}")

check("At least one vite proxy works", working_proxy is not None,
      f"working={working_proxy}")

# ── Phase 6: FIX-1 regression check (ssl) ─────────────────────────────
print("\n" + "=" * 72)
print("PHASE 6 — FIX-1 regression: alembic can run against prod DB")
print("=" * 72)

import subprocess
result = subprocess.run(
    ["docker", "exec", "starmap-backend-prod", "alembic", "current"],
    capture_output=True, text=True, timeout=30,
)
combined = (result.stdout or "") + (result.stderr or "")
check("alembic current runs without sslmode error",
      "sslmode" not in combined and result.returncode == 0,
      f"returncode={result.returncode}")
check("alembic shows current head (no pending migrations)",
      "014_extend_users_for_lifecycle" in combined or "(head)" in combined,
      f"output:\n{combined.strip()[:300]}")

# Verify URI in current code uses ssl= (not sslmode=)
config_path = "C:/Users/LiShuai/Desktop/Agents/starmap/backend/app/config.py"
with open(config_path, encoding="utf-8") as f:
    src_lines = f.readlines()
# Strip comments (lines starting with whitespace + #) so we only test executable code
src_code = "".join(
    line for line in src_lines
    if not line.lstrip().startswith("#")
)
check("config.py uses `?ssl=` (not sslmode=) for postgres_uri",
      "?ssl=" in src_code and "?sslmode=" not in src_code,
      f"FIX-1 verified in executable code (comments excluded). "
      f"?ssl={src_code.count('?ssl=')}, ?sslmode={src_code.count('?sslmode=')}")

# ── Summary ───────────────────────────────────────────────────────────
print("\n" + "=" * 72)
print(f"SUMMARY: {len(PASS)} passed, {len(FAIL)} failed (total {len(PASS)+len(FAIL)})")
print("=" * 72)

if FAIL:
    print("\nFAILED:")
    for name, detail in FAIL:
        print(f"  - {name}  {detail}")
    sys.exit(1)
else:
    print("\nAll verification tests PASSED.")
    sys.exit(0)