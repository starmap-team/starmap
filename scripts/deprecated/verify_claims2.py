"""Live multi-tier spot checks + CONFORMANCE content audit (independent of crashed script)."""
from __future__ import annotations
import json
import re
import subprocess
import urllib.request
import urllib.error
from pathlib import Path

REPO = Path(r"C:\Users\LiShuai\Desktop\Agents\starmap")
CONF = REPO / ".planning" / "phases" / "13-design-conformance"


def get(url, token=None):
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"} if token else {})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, (e.read() or b"{}").decode("utf-8", errors="replace")


def post(url, body, token=None):
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST",
                                 headers={"Content-Type": "application/json; charset=utf-8",
                                          **({"Authorization": f"Bearer {token}"} if token else {})})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, (e.read() or b"{}").decode("utf-8", errors="replace")


# --- A. CONFORMANCE content audit (real evidence vs template) ---
print("=== A. CONFORMANCE content audit (look for real verification markers) ===")
for p in sorted(CONF.glob("CONFORMANCE-*.md")):
    text = p.read_text(encoding="utf-8")
    has_fix = "FIXED" in text
    has_verify = bool(re.search(r"\*\*验证\*\*|verified|curl ", text))
    has_screenshot = "screenshot" in text.lower() or ".png" in text
    has_cursor_cmd = bool(re.search(r"curl |SELECT |MATCH \(", text))
    n_chars = len(text)
    print(f"  {p.name:42s}  chars={n_chars:4d}  FIXED={has_fix}  verify_marker={has_verify}  curl/cypher={has_cursor_cmd}  shot={has_screenshot}")

# --- B. live multi-tier spot checks (real API vs claim) ---
print("\n=== B. live multi-tier spot checks ===")
code, body = post("http://localhost:8000/api/v1/auth/login",
                  {"username": "admin", "password": "starmap2024"})
token = body["access_token"]

print("  [M2/M3 回归] /match/position 测试工程师 (report: 200 + note=null):")
s, b = post("http://localhost:8000/api/v1/match/position",
            {"person_skills":[{"name":"Python","proficiency":"expert"}], "target_position":"测试工程师"}, token)
print(f"    http={s}  match_score={b.get('match_score')}  note={b.get('note')!r}")

print("  [M4] /quality/dashboard warning_level (report: gray, no baseline):")
s, b = get("http://localhost:8000/api/v1/quality/dashboard", token)
rep = b.get("report", {})
print(f"    http={s}  warning_level={rep.get('warning_level')}  baseline_available={b.get('baseline_available')}  eval_count={b.get('evaluation_count')}")

print("  [M5 pipeline dq] /pipeline/data-quality overall_score (report: 0.0, not 1.0):")
s, b = get("http://localhost:8000/api/v1/pipeline/data-quality", token)
m = b.get("metrics", b)
print(f"    http={s}  overall={m.get('overall_score')}  consistency={m.get('consistency')}  timeliness={m.get('timeliness')}  baseline_available={m.get('baseline_available')}")

print("  [M6] /graph/overview?group_by=domain total_skills (report: 257, M6 conform):")
s, b = get("http://localhost:8000/api/v1/graph/overview?group_by=domain", token)
print(f"    http={s}  total_skills={b.get('total_skills')}  independent_skills={b.get('independent_skills')}  domains={len(b.get('domains',[]))}  connections={len(b.get('connections',[]))}")

print("  [Dashboard edge 口径] /dashboard/overview total_edges (claim 1179 vs Neo4j 1375 OPEN):")
s, b = get("http://localhost:8000/api/v1/dashboard/overview", token)
print(f"    http={s}  dashboard.total_edges={b.get('total_edges')}")

print("  [Neo4j 全部边 (按类型)]:")
neo = subprocess.run(
    'docker exec starmap-neo4j cypher-shell -u neo4j -p starmap123456 "MATCH ()-[r]->() RETURN type(r) AS t, count(r) AS c ORDER BY c DESC" 2>/dev/null',
    shell=True, capture_output=True, text=True)
for line in neo.stdout.strip().splitlines():
    if line and not line.startswith(("t,", "Empty")):
        print(f"    {line}")

print("  [PG 端真实]:")
pg = subprocess.run(
    'docker exec starmap-postgres psql -U starmap -d starmap -tAc '
    '"SELECT \'jd_raw=\'||count(*) FROM jd_raw; '
    'SELECT \'position_records=\'||count(*) FROM position_records; '
    'SELECT \'skill_records=\'||count(*) FROM skill_records; '
    'SELECT \'extraction_evaluation_records=\'||count(*) FROM extraction_evaluation_records; '
    'SELECT \'position_skill_relations=\'||count(*) FROM position_skill_relations" 2>/dev/null',
    shell=True, capture_output=True, text=True)
for line in pg.stdout.strip().splitlines():
    if line:
        print(f"    {line}")
