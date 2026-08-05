#!/usr/bin/env python3
"""Comprehensive API integration tests for all Starmap business scenarios."""
import json, sys, os, time
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

BASE = "http://localhost:8000/api/v1"
LOGIN_URL = f"{BASE}/auth/login"
# PLAN-007 / NEW-20: 凭据单一来源=环境变量（默认 dev 引导账号）
ADMIN_USER = os.environ.get("STARMAP_TEST_ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("STARMAP_TEST_ADMIN_PASSWORD", "starmap2024")
CREDS = json.dumps({"username": ADMIN_USER, "password": ADMIN_PASSWORD}).encode()

def api(method, path, body=None, headers=None):
    h = {"Content-Type": "application/json"}
    if headers: h.update(headers)
    data = json.dumps(body).encode() if body else None
    req = Request(f"{BASE}{path}", data=data, headers=h, method=method)
    try:
        with urlopen(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read())
    except HTTPError as e:
        body = e.read().decode()
        try: detail = json.loads(body)
        except: detail = body
        return e.code, detail
    except URLError as e:
        return 0, str(e)

def login():
    code, data = api("POST", "/auth/login", {"username": ADMIN_USER, "password": ADMIN_PASSWORD})
    return data.get("access_token","") if code==200 else ""

def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}

results = []
def test(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    results.append((status, name, detail))
    print(f"  [{status}] {name} {detail if not condition else ''}")

def _items(d):
    """Extract items count from API response (handles both list and dict)."""
    if isinstance(d, list): return len(d)
    return len(d.get("items", d.get("results", [])))

token = login()
admin_h = auth_headers(token) if token else {}

# ━━━━━ 1. AUTH ━━━━━
print("\n=== 1. Auth ===")
code, _ = api("POST", "/auth/login", {"username": ADMIN_USER, "password": ADMIN_PASSWORD})
test("1.1 Normal login", code == 200, f"HTTP {code}")

code, data = api("POST", "/auth/login", {"username":"","password":""})
test("1.2 Empty credentials → 422", code == 422, f"HTTP {code}")

code, data = api("POST", "/auth/login", {"username":"admin","password":"wrong"})
test("1.3 Wrong password → 401", code == 401, f"HTTP {code} detail={data.get('detail','?')}")

code, data = api("POST", "/auth/refresh", {"refresh_token":"invalid"})
test("1.4 Invalid refresh → error", code in (401, 422), f"HTTP {code}")

if token:
    code, data = api("GET", "/auth/me", headers=admin_h)
    test("1.5 Auth me returns user", code == 200 and "username" in data, f"user={data.get('username','?')}")

# ━━━━━ 2. POSITIONS ━━━━━
print("\n=== 2. Positions ===")
code, data = api("GET", "/positions", headers=admin_h)
test("2.1 List positions", code == 200 and data["total"] > 0, f"total={data.get('total',0)}")

code, data = api("GET", "/positions?search=Python", headers=admin_h)
test("2.2 Search positions", code == 200, f"total={data.get('total',0)}")

code, data = api("GET", "/positions?page=1&page_size=5", headers=admin_h)
test("2.3 Pagination", code == 200 and len(data["items"]) <= 5, f"items={len(data['items'])}")

code, data = api("GET", "/positions?page=99999", headers=admin_h)
test("2.4 Beyond total pages", code == 200, f"items={len(data['items'])} (expect 0)")

# ━━━━━ 3. DASHBOARD ━━━━━
print("\n=== 3. Dashboard ===")
code, data = api("GET", "/dashboard/overview", headers=admin_h)
test("3.1 Overview returns metrics", code == 200 and "total_nodes" in data, f"nodes={data.get('total_nodes',0)} edges={data.get('total_edges',0)}")

code, data = api("GET", "/dashboard/realtime-poll", headers=admin_h)
test("3.2 Realtime poll", code == 200, f"events={len(data) if isinstance(data,list) else 'N/A'}")

# ━━━━━ 4. GRAPH ━━━━━
print("\n=== 4. Graph ===")
code, data = api("GET", "/graph/overview?group_by=domain", headers=admin_h)
test("4.1 Domain overview", code == 200 and "domains" in data, f"domains={len(data.get('domains',[]))} positions={data.get('independent_positions',0)}")

code, data = api("GET", "/graph/overview?group_by=tech_stack", headers=admin_h)
test("4.2 Tech stack overview", code == 200, f"domains={len(data.get('domains',[]))}")

code, data = api("GET", "/graph/overview?group_by=level", headers=admin_h)
test("4.3 Level overview", code == 200, f"domains={len(data.get('domains',[]))}")

# ━━━━━ 5. QUALITY ━━━━━
print("\n=== 5. Quality ===")
code, data = api("GET", "/quality/dashboard", headers=admin_h)
test("5.1 Dashboard", code == 200 and "report" in data, f"nodes={data.get('total_nodes',0)} edges={data.get('total_edges',0)}")

code, data = api("GET", "/quality/report", headers=admin_h)
test("5.2 Report", code == 200 and "f1" in data, f"f1={data.get('f1',0):.2f}")

code, data = api("GET", "/quality/trends?period=7d", headers=admin_h)
test("5.3 Trends", code == 200, f"items={len(data.get('items',[]))}")

code, data = api("GET", "/quality/alerts", headers=admin_h)
test("5.4 Alerts", code == 200, f"items={_items(data)}")

# ━━━━━ 6. EVOLUTION ━━━━━
print("\n=== 6. Evolution ===")
code, data = api("GET", "/evolution/trends", headers=admin_h)
test("6.1 Trends", code == 200, f"items={_items(data)}")

code, data = api("GET", "/evolution/review-queue", headers=admin_h)
test("6.2 Review queue", code == 200, f"items={_items(data)}")

code, data = api("GET", "/evolution/snapshots", headers=admin_h)
test("6.3 Snapshots", code == 200, f"items={_items(data)}")

code, data = api("GET", "/evolution/emerging-skills", headers=admin_h)
test("6.4 Emerging skills", code == 200, f"count={_items(data)}")

# ━━━━━ 7. PIPELINE ━━━━━
print("\n=== 7. Pipeline ===")
code, data = api("GET", "/pipeline/status", headers=admin_h)
test("7.1 Status", code == 200 and "is_running" in data, f"running={data.get('is_running')} sources={data.get('active_data_sources')}")

code, data = api("GET", "/pipeline/runs?limit=3", headers=admin_h)
test("7.2 Run history", code == 200 and len(data) > 0, f"runs={len(data)}")

code, data = api("GET", "/admin/pipeline/status", headers=admin_h)
test("7.3 Admin pipeline status", code == 200, f"active={data.get('active_data_sources',0)}")

# ━━━━━ 8. DATA SOURCES ━━━━━
print("\n=== 8. Data Sources ===")
code, data = api("GET", "/datasources", headers=admin_h)
test("8.1 List sources", code == 200 and len(data) > 0, f"count={len(data)}")

code, data = api("GET", "/datasources?page=1&page_size=2", headers=admin_h)
test("8.2 Pagination", code == 200, f"items={_items(data)}")

# ━━━━━ 9. ADMIN ━━━━━
print("\n=== 9. Admin ===")
code, data = api("GET", "/admin/stats", headers=admin_h)
test("9.1 Stats", code == 200 and "total_nodes" in data, f"nodes={data.get('total_nodes',0)} edges={data.get('total_edges',0)}")

code, data = api("GET", "/admin/review-items?status=approved&limit=5", headers=admin_h)
test("9.2 Review items", code == 200, f"items={_items(data)}")

code, data = api("GET", "/admin/review-stats", headers=admin_h)
test("9.3 Review stats", code == 200, f"pending={data.get('pending',0)}")

code, data = api("GET", "/admin/users?page=1&page_size=10", headers=admin_h)
test("9.4 Users list", code == 200, f"users={_items(data)}")

code, data = api("GET", "/admin/audit-events?page=1&page_size=10", headers=admin_h)
test("9.5 Audit events", code == 200, f"events={_items(data)}")

code, data = api("GET", "/admin/graph/nodes", headers=admin_h)
test("9.6 Graph nodes", code == 200, f"nodes={_items(data)}")

code, data = api("GET", "/admin/prompts", headers=admin_h)
test("9.7 Prompts list", code == 200, f"prompts={_items(data)}")

# ━━━━━ 10. MATCH ━━━━━
print("\n=== 10. Match ===")
code, data = api("POST", "/match/diagnose", 
    {"target_position":"Python","person_skills":[{"skill":"Python","proficiency":"expert"}],"options":{"threshold":0.5}},
    headers=admin_h)
test("10.1 Diagnose match", code == 200 and "gap_analysis" in data or "score" in data, f"HTTP {code}")

code, data = api("GET", "/match/results?limit=5", headers=admin_h)
test("10.2 Results", code == 200, f"items={_items(data)}")

code, data = api("GET", "/match/history", headers=admin_h)
test("10.3 History", code == 200, f"items={_items(data)}")

# ━━━━━ 11. LEARNING ━━━━━
print("\n=== 11. Learning ===")
code, data = api("GET", "/learning/paths", headers=admin_h)
test("11.1 Paths", code == 200, f"items={_items(data)}")

code, data = api("GET", "/learning/resources", headers=admin_h)
test("11.2 Resources", code == 200, f"items={_items(data)}")

code, data = api("GET", "/learning/progress", headers=admin_h)
test("11.3 Progress", code == 200, f"items={_items(data)}")

# ━━━━━ 12. HEALTH ━━━━━
print("\n=== 12. Health ===")
code, data = api("GET", "/health", headers=admin_h)
test("12.1 Health check", code == 200 and data.get("status") == "ok", f"status={data.get('status','?')}")

# ━━━━━ 13. ERROR CASES ━━━━━
print("\n=== 13. Error Cases ===")
code, data = api("GET", "/positions", headers={})  # no auth
msg = data.get("detail","") if isinstance(data, dict) else str(data)
test("13.1 No auth → 401/403", code in (401, 403), f"HTTP {code}")

code, data = api("GET", "/nonexistent", headers=admin_h)
test("13.2 404 on unknown path", code == 404, f"HTTP {code}")

code, data = api("POST", "/auth/login", {"malformed": True})
test("13.3 Malformed login body → 422", code == 422, f"HTTP {code}")

code, data = api("GET", "/admin/stats", headers={"Authorization": "Bearer invalid_token_xyz"})
test("13.4 Invalid token → 401", code in (401, 403), f"HTTP {code}")

# ━━━━━ SUMMARY ━━━━━
print("\n" + "="*60)
passed = sum(1 for r in results if r[0]=="PASS")
failed = sum(1 for r in results if r[0]=="FAIL")
print(f"RESULTS: {passed} passed, {failed} failed, {len(results)} total")

if failed:
    print("\nFAILURES:")
    for s, n, d in results:
        if s == "FAIL":
            print(f"  ✗ {n}: {d}")
