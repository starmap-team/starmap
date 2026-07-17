"""Comprehensive login module test suite."""
import json
import sys
from pathlib import Path
from urllib import request, error

BASE = "http://localhost:8000"
RESULTS = []


def post(path: str, body: dict, headers: dict | None = None) -> tuple[int, dict, dict]:
    """Make a POST request and return (status, json_body, raw_headers)."""
    url = f"{BASE}{path}"
    data = json.dumps(body).encode("utf-8")
    req = request.Request(
        url, data=data, method="POST",
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    try:
        with request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read()), dict(resp.headers)
    except error.HTTPError as e:
        try:
            body = json.loads(e.read())
        except Exception:
            body = {"_raw": "non-json body"}
        return e.code, body, dict(e.headers)


def get(path: str, headers: dict | None = None) -> tuple[int, dict, dict]:
    url = f"{BASE}{path}"
    req = request.Request(url, headers=headers or {})
    try:
        with request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read()), dict(resp.headers)
    except error.HTTPError as e:
        try:
            body = json.loads(e.read())
        except Exception:
            body = {"_raw": "non-json body"}
        return e.code, body, dict(e.headers)


def record(name: str, status: int, body: dict, ok: bool, note: str = "") -> None:
    RESULTS.append({"name": name, "status": status, "body": body, "ok": ok, "note": note})
    icon = "PASS" if ok else "FAIL"
    print(f"  [{icon}] {name} -> {status}  {note}")
    if not ok:
        print(f"         body={body}")


print("=" * 70)
print("LOGIN MODULE COMPREHENSIVE TEST SUITE")
print("=" * 70)

# === Test 1: Valid credentials ===
print("\n[1] Valid credentials login")
status, body, _ = post("/api/v1/auth/login", {"username": "admin", "password": "starmap2024"})
ok = status == 200 and "access_token" in body and "refresh_token" in body and body.get("user", {}).get("role") == "admin"
record("Valid login admin/starmap2024", status, body, ok,
       "got access+refresh token, user.role=admin" if ok else "missing token or wrong role")
access_token = body.get("access_token") if status == 200 else None
refresh_token = body.get("refresh_token") if status == 200 else None

# === Test 2: Wrong password ===
print("\n[2] Wrong password (should be 401 with Chinese error)")
status, body, _ = post("/api/v1/auth/login", {"username": "admin", "password": "wrong_password_123"})
ok = status == 401 and "用户名或密码错误" in (body.get("detail", "") if isinstance(body, dict) else "")
record("Wrong password → 401 + Chinese msg", status, body, ok,
       f"detail='{body.get('detail', '') if isinstance(body, dict) else body}'")

# === Test 3: Non-existent user ===
print("\n[3] Non-existent user (should NOT reveal whether user exists)")
status, body, _ = post("/api/v1/auth/login", {"username": "ghost_user_xyz", "password": "anything"})
ok = status == 401 and "用户名或密码错误" in (body.get("detail", "") if isinstance(body, dict) else "")
record("Non-existent user → 401 + same Chinese msg", status, body, ok,
       f"detail='{body.get('detail', '') if isinstance(body, dict) else body}'")

# === Test 4: Empty username ===
print("\n[4] Empty username (Pydantic validation: min_length=1)")
status, body, _ = post("/api/v1/auth/login", {"username": "", "password": "x"})
ok = status == 422
record("Empty username → 422 validation", status, body, ok)

# === Test 5: Empty password ===
print("\n[5] Empty password (Pydantic validation: min_length=1)")
status, body, _ = post("/api/v1/auth/login", {"username": "admin", "password": ""})
ok = status == 422
record("Empty password → 422 validation", status, body, ok)

# === Test 6: Missing fields ===
print("\n[6] Missing fields")
status, body, _ = post("/api/v1/auth/login", {})
ok = status == 422
record("Missing both → 422 validation", status, body, ok)

# === Test 7: Malformed JSON ===
print("\n[7] Malformed JSON")
url = f"{BASE}/api/v1/auth/login"
req = request.Request(url, data=b"not-valid-json", method="POST",
                      headers={"Content-Type": "application/json"})
try:
    with request.urlopen(req, timeout=10) as resp:
        status, body = resp.status, json.loads(resp.read())
except error.HTTPError as e:
    status, body = e.code, json.loads(e.read())
ok = status == 422
record("Malformed JSON → 422", status, body, ok)

# === Test 8: /me with valid token ===
print("\n[8] /auth/me with valid Bearer token")
status, body, _ = get("/api/v1/auth/me", {"Authorization": f"Bearer {access_token}"})
ok = status == 200 and body.get("username") == "admin"
record("/me with Bearer → 200", status, body, ok)

# === Test 9: /me without token ===
print("\n[9] /auth/me without token")
status, body, _ = get("/api/v1/auth/me")
ok = status == 401
record("/me without token → 401", status, body, ok)

# === Test 10: /me with garbage token ===
print("\n[10] /auth/me with garbage token")
status, body, _ = get("/api/v1/auth/me", {"Authorization": "Bearer garbage.token.here"})
ok = status == 401
record("/me with garbage → 401", status, body, ok)

# === Test 11: Token refresh ===
print("\n[11] Token refresh with valid refresh_token")
if refresh_token:
    status, body, _ = post("/api/v1/auth/refresh", {"refresh_token": refresh_token})
    ok = status == 200 and "access_token" in body
    new_access = body.get("access_token") if status == 200 else None
    record("Refresh valid token → 200", status, body, ok)
else:
    record("Refresh test", 0, {}, False, "no refresh_token from previous test")

# === Test 12: Refresh with invalid token ===
print("\n[12] Token refresh with invalid refresh_token")
status, body, _ = post("/api/v1/auth/refresh", {"refresh_token": "garbage"})
ok = status == 401
record("Refresh invalid → 401", status, body, ok)

# === Test 13: Logout ===
print("\n[13] Logout revokes refresh token")
if refresh_token:
    status, body, _ = post("/api/v1/auth/logout", {"refresh_token": refresh_token})
    ok = status == 200 and body.get("revoked") == 1
    record("Logout → 200 + revoked=1", status, body, ok)

    # After logout, refresh should fail
    status2, body2, _ = post("/api/v1/auth/refresh", {"refresh_token": refresh_token})
    ok2 = status2 == 401
    record("Refresh after logout → 401", status2, body2, ok2)
else:
    record("Logout test", 0, {}, False, "no refresh_token")

# === Test 14: Re-login after lockout simulation ===
print("\n[14] Multiple wrong passwords to trigger lockout (5 fails → lock)")
# Re-login first to reset state if not locked
post("/api/v1/auth/login", {"username": "admin", "password": "starmap2024"})  # best-effort reset

fail_count = 0
for i in range(7):
    s, b, _ = post("/api/v1/auth/login", {"username": "admin", "password": f"wrong_{i}"})
    if s == 401 and "锁定" in str(b.get("detail", "")):
        # Lockout triggered
        fail_count = i + 1
        print(f"    Lockout triggered after {fail_count} attempts")
        record(f"Lockout triggered", s, b, True,
               f"after {fail_count} failed attempts, detail='{b.get('detail')}'")
        break
    elif s == 401:
        continue
    else:
        record(f"Unexpected status {s}", s, b, False)
        break
else:
    record("Lockout after 7 wrong attempts", 0, {}, False, "no lockout triggered")

# === Test 15: Even correct password should be blocked when locked ===
print("\n[15] Correct password after lockout should still 423")
status, body, _ = post("/api/v1/auth/login", {"username": "admin", "password": "starmap2024"})
ok = status == 423 or "锁定" in str(body.get("detail", ""))
record("Correct password while locked → 423", status, body, ok,
       f"detail='{body.get('detail')}'")

# === Summary ===
print("\n" + "=" * 70)
total = len(RESULTS)
passed = sum(1 for r in RESULTS if r["ok"])
print(f"SUMMARY: {passed}/{total} tests passed")
print("=" * 70)

# Print failed tests
failed = [r for r in RESULTS if not r["ok"]]
if failed:
    print("\nFAILED TESTS:")
    for r in failed:
        print(f"  - {r['name']}: status={r['status']} body={r['body']}")
        if r["note"]:
            print(f"    note: {r['note']}")
else:
    print("\nAll tests passed!")

sys.exit(0 if passed == total else 1)