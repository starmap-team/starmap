"""Phase 13 / parallel-sessions' 报告 claims — multi-source audit.

不信任报告，只看真实仓库 + 真实后端响应。"""
from __future__ import annotations
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(r"C:\Users\LiShuai\Desktop\Agents\starmap")
PHASES = REPO / ".planning" / "phases"
CONFORMANCE_DIR = PHASES / "13-design-conformance"
MEMORY_FILE = REPO.parent.parent / "starmap-phase13-conformance-progress.md"  # may not exist; fallback
SPEC_FILE = REPO / "docs" / "standards" / "04-contracts" / "01-API契约规范.md"
ROADMAP = REPO / ".planning" / "ROADMAP.md"
STATE = REPO / ".planning" / "STATE.md"


def run(cmd, cwd=None, check=True):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd)


def section(title):
    print(f"\n=== {title} ===")


# --- Claim 1: 12 份 01-01-SUMMARY.md (per v5 module 1-12) ---
section("Claim 1: '12 份 01-01-SUMMARY.md' (v5.0 module summaries)")
summaries_01 = list(PHASES.glob("*/01-01-SUMMARY.md"))
summaries_any = list(PHASES.glob("**/01-01-SUMMARY.md")) + list(PHASES.glob("**/SUMMARY.md"))
print(f"  under */01-01-SUMMARY.md: {len(summaries_01)}  (claimed 12)")
for p in sorted(summaries_01):
    print(f"    - {p.relative_to(REPO)}")
print(f"  any */SUMMARY*.md (incl. non-01-01): {len(summaries_any)}")
# v5 module dirs that EXIST
v5_module_dirs = [
    "01-home-module","02-position-module","03-pipeline-monitor","04-datasources",
    "05-match-diagnosis","06-extract-jd","07-loop-demo","08-learning-center",
    "09-data-dashboard","10-evolution-dashboard","11-quality-dashboard","12-admin",
]
existing = [d for d in v5_module_dirs if (PHASES / d).exists()]
print(f"  v5 module phase dirs existing: {len(existing)}/12  → {existing}")
# Did they get a 01-01-PLAN.md (means plan was written)?
plans = [d for d in existing if (PHASES / d / "01-01-PLAN.md").exists()]
print(f"  with 01-01-PLAN.md: {len(plans)}/12")

# --- Claim 2: 12 份 CONFORMANCE-<module>.md ---
section("Claim 2: '12 份 CONFORMANCE-<module>.md'")
confs = sorted(CONFORMANCE_DIR.glob("CONFORMANCE-*.md"))
print(f"  count: {len(confs)}  (claimed 12)")
for p in confs:
    print(f"    - {p.name}")

# --- Claim 3: 1 份 Phase 13 总 SUMMARY ---
section("Claim 3: '1 份 Phase 13 总 SUMMARY' (13-SUMMARY.md)")
tot = list(CONFORMANCE_DIR.glob("13-SUMMARY*.md")) + list(CONFORMANCE_DIR.glob("PHASE13*.md")) + list(CONFORMANCE_DIR.glob("*-SUMMARY.md"))
print(f"  found: {[p.name for p in tot]}")

# --- Claim 4: M1–M7 in 04-contracts spec ---
section("Claim 4: 'M1–M7 强制规范写入 docs/standards/04-contracts/01-API契约规范.md'")
if SPEC_FILE.exists():
    text = SPEC_FILE.read_text(encoding="utf-8")
    matches = re.findall(r"^\- \*\*M(\d+)", text, re.M)
    print(f"  M-numbers found in spec: {matches}  (claimed M1–M7)")

# --- Claim 5: Memory progress file ---
section("Claim 5: '记忆 starmap-phase13-conformance-progress.md 持续更新'")
mem = Path(r"C:\Users\LiShuai\.claude\projects\C--Users-LiShuai-Desktop-Agents-starmap\memory\starmap-phase13-conformance-progress.md")
if mem.exists():
    text = mem.read_text(encoding="utf-8")
    updates = re.findall(r"^## 更新 (\d{4}-\d{2}-\d{2})", text, re.M)
    print(f"  existing file: yes  ({len(text)} chars, {len(updates)} update sections: {updates[-3:] if updates else 'none'})")
else:
    print("  MISSING")

# --- Claim 6: STATE reflects 'Wave 3 (Phase 9/10/11) + Wave 4 (Phase 12 Admin) 闭环' ---
section("Claim 6: STATE shows 12 modules closed + Phase 13 done")
if STATE.exists():
    text = STATE.read_text(encoding="utf-8")
    m = re.search(r"current_phase:\s*(\d+)\s*\n.*?completed_phases:\s*(\d+).*?percent:\s*(\d+)", text, re.S)
    if m:
        print(f"  current_phase={m.group(1)} completed_phases={m.group(2)} percent={m.group(3)}%")
    print(f"  last_activity_desc: {re.search(r'last_activity_desc:\\s*(.+)', text).group(1).strip() if re.search(r'last_activity_desc:', text) else 'n/a'}")

# --- Live multi-tier spot-checks vs claimed fixes ---
section("Live multi-tier spot checks (API tier)")
import urllib.request, urllib.error
def post(url, body, token=None):
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST",
                                 headers={"Content-Type":"application/json; charset=utf-8", **({"Authorization": f"Bearer {token}"} if token else {})})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, (e.read() or b"{}").decode("utf-8", errors="replace")
def get(url, token=None):
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"} if token else {})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, (e.read() or b"{}").decode("utf-8", errors="replace")

try:
    code, body = post("http://localhost:8000/api/v1/auth/login",
                      {"username": "admin", "password": "starmap2024"})
    if code != 200:
        print(f"  login HTTP {code}: {body[:120]}")
        sys.exit(0)
    token = body["access_token"]
    print("  [M2/M3 回归] /match/position 测试工程师 (期望 200 + note=null):")
    s, b = post("http://localhost:8000/api/v1/match/position",
                {"person_skills":[{"name":"Python","proficiency":"expert"}], "target_position":"测试工程师"}, token)
    print(f"    http={s} match_score={b.get('match_score')} note={b.get('note')!r}")
    print("  [M4 后端契约] /quality/dashboard warning_level 应为 gray (无基线):")
    s, b = get("http://localhost:8000/api/v1/quality/dashboard", token)
    rep = b.get("report", {})
    print(f"    http={s} warning_level={rep.get('warning_level')} baseline_available={b.get('baseline_available')} eval_count={b.get('evaluation_count')}")
    print("  [M5 pipeline dq] /pipeline/data-quality overall_score 应 0.0 (无数据), 不应 1.0:")
    s, b = get("http://localhost:8000/api/v1/pipeline/data-quality", token)
    m = b.get("metrics", b)
    print(f"    http={s} overall={m.get('overall_score')} consistency={m.get('consistency')} timeliness={m.get('timeliness')} baseline_available={m.get('baseline_available')}")
    print("  [M6 口径] /graph/overview?group_by=domain total_skills 应 257 (去重, not 395):")
    s, b = get("http://localhost:8000/api/v1/graph/overview?group_by=domain", token)
    print(f"    http={s} total_skills={b.get('total_skills')} independent_skills={b.get('independent_skills')} domains={len(b.get('domains',[]))} connections={len(b.get('connections',[]))}")
    print("  [Dashboard edge 口径] dashboard total_edges vs Neo4j 全部边 (报告称 1179 vs 1375):")
    s, b = get("http://localhost:8000/api/v1/dashboard/overview", token)
    print(f"    http={s} dashboard.total_edges={b.get('total_edges')}")
    print("  [Neo4j 全部边类型分布]:")
    neo = run('docker exec starmap-neo4j cypher-shell -u neo4j -p starmap123456 "MATCH ()-[r]->() RETURN type(r) AS t, count(r) AS c ORDER BY c DESC" 2>/dev/null')
    for line in neo.stdout.strip().splitlines():
        if line and not line.startswith(('t,','Empty')):
            print(f"    {line}")
    print("  [PG 端真实]:")
    pg = run('docker exec starmap-postgres psql -U starmap -d starmap -tAc "SELECT \'jd_raw=\'||count(*) FROM jd_raw; SELECT \'position_records=\'||count(*) FROM position_records; SELECT \'skill_records=\'||count(*) FROM skill_records; SELECT \'extraction_evaluation_records=\'||count(*) FROM extraction_evaluation_records; SELECT \'position_skill_relations=\'||count(*) FROM position_skill_relations;" 2>/dev/null')
    for line in pg.stdout.strip().splitlines():
        if line:
            print(f"    {line}")
except Exception as e:
    print(f"  spot-check error: {e}")
