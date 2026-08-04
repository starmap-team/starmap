"""M2 三端 验证 (UTF-8 安全)"""
import json, subprocess, urllib.request
REQ = {"person_skills":[{"name":"Python","proficiency":"expert"}]}
def login():
    r = urllib.request.urlopen(urllib.request.Request(
        "http://localhost:8000/api/v1/auth/login", method="POST",
        data=json.dumps({"username":"admin","password":"starmap2024"}).encode(),
        headers={"Content-Type":"application/json"}), timeout=10)
    return json.loads(r.read())["access_token"]
def post(target, tok):
    body = dict(REQ, target_position=target)
    r = urllib.request.urlopen(urllib.request.Request(
        "http://localhost:8000/api/v1/match/position", method="POST",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type":"application/json; charset=utf-8", "Authorization":f"Bearer {tok}"}),
        timeout=10)
    return r.status, json.loads(r.read())
tok = login()
for t, expected in [("Senior Python Engineer", "200 note!=null"),
                    ("测试工程师", "200 note=null"),
                    ("ZZZ_NoSuchPosition_42", "404 no-note")]:
    s, b = post(t, tok)
    note = b.get("note")
    score = b.get("match_score")
    print(f"  {t:30s}  http={s}  score={score}  note={(note or '(none)')[:55]!r}  expected={expected}")
