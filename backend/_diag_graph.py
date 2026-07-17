"""Diagnose graph API endpoints to find why frontend shows 'no data'."""
import json
import urllib.request


def post(url, body):
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def get(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read()), dict(r.headers)


# Login
auth = post("http://localhost:8000/api/v1/auth/login",
            {"username": "admin", "password": "starmap2024"})
token = auth["access_token"]
h = {"Authorization": f"Bearer {token}"}

# Hit /graph/overview
print("=== GET /api/v1/graph/overview?group_by=domain ===")
data, _ = get("http://localhost:8000/api/v1/graph/overview?group_by=domain", h)
print(json.dumps(data, indent=2, ensure_ascii=False)[:1500])

# Hit overview with other group_by modes
for mode in ["tech_stack", "level"]:
    print(f"\n=== GET /api/v1/graph/overview?group_by={mode} ===")
    try:
        data, _ = get(f"http://localhost:8000/api/v1/graph/overview?group_by={mode}", h)
        print(json.dumps(data, indent=2, ensure_ascii=False)[:1000])
    except Exception as e:
        print(f"  ERROR: {e}")

# List all graph endpoints
print("\n=== Graph API endpoints (from /openapi.json) ===")
try:
    spec, _ = get("http://localhost:8000/api/v1/openapi.json")
    paths = [p for p in spec.get("paths", {}) if "graph" in p.lower()]
    for p in sorted(paths):
        methods = list(spec["paths"][p].keys())
        print(f"  {' '.join(methods).upper():8} {p}")
except Exception as e:
    print(f"  (openapi not exposed: {e})")