"""End-to-end login test through vite proxy."""
import json
import sys
from urllib import request, error

# Test through vite proxy (any of the dev ports should work)
for PORT in [5173, 5183, 5188]:
    print(f"\n=== Testing through localhost:{PORT} ===")
    url = f"http://localhost:{PORT}/api/v1/auth/login"
    data = json.dumps({"username": "admin", "password": "starmap2024"}).encode("utf-8")
    req = request.Request(url, data=data, method="POST",
                         headers={"Content-Type": "application/json",
                                  "Origin": f"http://localhost:{PORT}",
                                  "Referer": f"http://localhost:{PORT}/"})
    try:
        with request.urlopen(req, timeout=10) as resp:
            print(f"  Status: {resp.status}")
            body = json.loads(resp.read())
            print(f"  Has access_token: {bool(body.get('access_token'))}")
            print(f"  Has refresh_token: {bool(body.get('refresh_token'))}")
            print(f"  User role: {body.get('user', {}).get('role')}")
            print(f"  CORS header (Access-Control-Allow-Origin): {resp.headers.get('Access-Control-Allow-Origin', 'N/A')}")
            print(f"  [PASS] login through vite:{PORT} works")
            sys.exit(0)
    except error.HTTPError as e:
        print(f"  Status: {e.code}")
        try:
            print(f"  Body: {e.read().decode()[:200]}")
        except Exception:
            pass
        print(f"  [FAIL] vite:{PORT} returned error")
    except Exception as e:
        print(f"  [SKIP] vite:{PORT} - {e}")

print("\nAll vite ports failed or unreachable.")
sys.exit(1)