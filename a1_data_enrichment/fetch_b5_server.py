import json, urllib.request, ssl, base64, urllib.parse

BASE = "https://47.120.60.10"
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

def api(path, method="GET", data=None, token=None):
    url = BASE + path
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req, context=CTX, timeout=30) as r:
        return r.status, json.loads(r.read().decode("utf-8"))

# 1. login
_, login = api("/api/v1/auth/login", "POST", {"username": "admin", "password": "starmap2024"})
token = login.get("access_token")
print("LOGIN OK, token_len=", len(token) if token else 0)

# 2. discover -> find new position
_, disc = api("/api/v1/positions/discover", "POST", {}, token)
cands = disc.get("emerging_positions", [])
print("discover candidates:", len(cands))
target = None
for p in cands:
    if p.get("position") == "首席自主卡车工程师":
        target = p
        break
if target is None:
    # fallback: pick highest ratio
    cands_sorted = sorted(cands, key=lambda x: x.get("emerging_ratio", 0), reverse=True)
    target = cands_sorted[0]
    print("WARNING 首席自主卡车工程师 not found, using", target.get("position"))
json.dump(target, open("/tmp/b5_new_position.json", "w"), ensure_ascii=False, indent=2)
print("NEW POSITION:", target.get("position"), "| ratio=", target.get("emerging_ratio"),
      "| industry_scenario=", target.get("industry_scenario"))
print("  definition:", json.dumps(target.get("definition"), ensure_ascii=False)[:300])
print("  emerging_skills:", target.get("emerging_skills"))

# 3. changelog 前端开发工程师
pos_enc = urllib.parse.quote("前端开发工程师")
_, chlog = api("/api/v1/evolution/changelog/" + pos_enc + "?limit=20", "GET", None, token)
json.dump(chlog, open("/tmp/b5_changelog.json", "w"), ensure_ascii=False, indent=2)
print("CHANGELOG type:", type(chlog).__name__)
print("  ", str(chlog)[:600])

# 4. position detail 前端开发工程师
status, det = api("/api/v1/positions/" + pos_enc, "GET", None, token)
json.dump(det, open("/tmp/b5_pos_detail.json", "w"), ensure_ascii=False, indent=2)
print("POS DETAIL status", status, "keys:", list(det.keys()) if isinstance(det, dict) else type(det))
print("  ", str(det)[:600])
