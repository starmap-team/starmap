"""auto_expand_match_golden.py — 新岗位审批通过后自动扩展 match golden set。

G1: golden set 静态快照 → 新岗位匹配准确率盲区。
本脚本扫描 PG 中已 approved 但不在 golden_set_match.jsonl 中的岗位，
为其生成 high-match / low-match 变体并追加到 golden set。

用法:
    python scripts/auto_expand_match_golden.py            # dry-run（只报告不写入）
    python scripts/auto_expand_match_golden.py --apply    # 实际追加
    python scripts/auto_expand_match_golden.py --coverage # 只输出覆盖率

设计: 由 celery accuracy-gate-weekly 每周一 02:30 调用，也可手动运行。
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GOLDEN_FILE = ROOT / "evaluation" / "golden_set_match.jsonl"

# 确保 backend/ 在 Python 路径上（app.* 模块导入）
_backend_dir = str(ROOT / "backend")
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)


def _load_golden() -> list[dict]:
    if not GOLDEN_FILE.exists():
        return []
    entries = []
    for line in GOLDEN_FILE.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


def _save_golden(entries: list[dict]) -> None:
    GOLDEN_FILE.write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in entries) + "\n",
        encoding="utf-8",
    )


def _get_approved_positions_from_pg() -> list[dict]:
    """从 PG 读取所有 approved 岗位及其 required 技能。"""
    import asyncio

    async def _fetch() -> list[dict]:
        from app.db.session import get_session_factory
        from sqlalchemy import text

        session_factory = get_session_factory()
        async with session_factory() as session:
            # 读取 approved 岗位 + 它们的 required 技能
            result = await session.execute(
                text("""
                    SELECT p.id, p.name, p.name_cn,
                           array_agg(DISTINCT s.name) AS required_skills
                    FROM position_records p
                    LEFT JOIN position_skill_relations psr
                        ON psr.position_id = p.id AND psr.requirement_type = 'required'
                    LEFT JOIN skill_records s ON s.id = psr.skill_id
                    WHERE p.review_status = 'approved'
                    GROUP BY p.id, p.name, p.name_cn
                """)
            )
            rows = result.fetchall()
            return [
                {
                    "id": str(row[0]),
                    "name": row[1],
                    "name_cn": row[2],
                    "required_skills": [r for r in (row[3] or []) if r],
                }
                for row in rows
            ]

    return asyncio.run(_fetch())


def _get_existing_position_names(golden: list[dict]) -> set[str]:
    """从 golden set 中提取已覆盖的岗位名集合。"""
    names: set[str] = set()
    for entry in golden:
        pos = entry.get("position") or entry.get("expected", {}).get("job_title", "")
        if pos:
            names.add(pos)
    return names


def _generate_high_matchVariant(
    position_name: str,
    required_skills: list[str],
    row_id: int,
) -> dict:
    """生成高匹配变体: person 有70-90% 的 required 技能，proficiency=精通。"""
    n = len(required_skills)
    if n == 0:
        return {}
    take = max(1, int(n * random.uniform(0.7, 0.9)))
    selected = random.sample(required_skills, min(take, n))
    return {
        "id": f"match-auto-{row_id:04d}",
        "position": position_name,
        "person_skills": [{"name": s, "proficiency": "精通"} for s in selected],
        "expected": {
            "match_score_min": 0.5,
            "match_score_max": 1.0,
            "should_match": True,
        },
    }


def _generate_low_match_variant(
    position_name: str,
    required_skills: list[str],
    row_id: int,
) -> dict:
    """生成低匹配变体: person 有 <25% overlap，用不相关技能填充。"""
    distractor_pool = [
        "市场营销", "财务管理", "人力资源", "法律咨询", "平面设计",
        "视频剪辑", "日语", "西班牙语", "会计", "物流管理",
    ]
    n = len(required_skills)
    take = max(0, int(n * random.uniform(0.0, 0.25)))
    overlap = random.sample(required_skills, min(take, n))
    distractors = random.sample(distractor_pool, min(3, len(distractor_pool)))
    person_skills = overlap + distractors
    return {
        "id": f"match-auto-{row_id:04d}-low",
        "position": position_name,
        "person_skills": [{"name": s, "proficiency": "了解"} for s in person_skills],
        "expected": {
            "match_score_min": 0.0,
            "match_score_max": 0.45,
            "should_match": False,
        },
    }


def compute_coverage(golden: list[dict], approved: list[dict]) -> dict:
    """计算 golden set 对 approved 岗位的覆盖率。"""
    golden_names = _get_existing_position_names(golden)
    approved_names = {p["name"] for p in approved if p.get("name")}
    covered = golden_names & approved_names
    uncovered = approved_names - golden_names
    total = len(approved_names)
    return {
        "total_approved": total,
        "covered": len(covered),
        "uncovered": len(uncovered),
        "coverage_ratio": len(covered) / total if total > 0 else 1.0,
        "uncovered_names": sorted(uncovered),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="自动扩展 match golden set (G1)")
    parser.add_argument("--apply", action="store_true", help="实际追加到 golden set（默认 dry-run）")
    parser.add_argument("--coverage", action="store_true", help="只输出覆盖率报告")
    args = parser.parse_args()

    golden = _load_golden()
    approved = _get_approved_positions_from_pg()

    coverage = compute_coverage(golden, approved)
    print(f"# Golden Set 覆盖率报告")
    print(f"- approved 岗位: {coverage['total_approved']}")
    print(f"- golden 覆盖: {coverage['covered']}")
    print(f"- 未覆盖: {coverage['uncovered']}")
    print(f"- 覆盖率: {coverage['coverage_ratio']:.1%}")
    if coverage["uncovered_names"]:
        print(f"- 未覆盖岗位: {', '.join(coverage['uncovered_names'][:10])}")
        if len(coverage["uncovered_names"]) > 10:
            print(f"  ...等 {len(coverage['uncovered_names'])} 个")

    if args.coverage:
        return 0

    # 找出未覆盖的岗位
    golden_names = _get_existing_position_names(golden)
    missing = [p for p in approved if p.get("name") and p["name"] not in golden_names]

    if not missing:
        print("\n✅ 所有 approved 岗位已在 golden set 中，无需扩展。")
        return 0

    print(f"\n将为 {len(missing)} 个新岗位生成 golden 变体...")

    next_id = len(golden) + 1
    new_entries = []
    for pos in missing:
        if not pos.get("required_skills"):
            print(f"  ⚠️ {pos['name']}: 无 required 技能，跳过")
            continue
        high = _generate_high_matchVariant(pos["name"], pos["required_skills"], next_id)
        low = _generate_low_match_variant(pos["name"], pos["required_skills"], next_id + 1)
        if high:
            new_entries.append(high)
        if low:
            new_entries.append(low)
        next_id += 2
        print(f"  ✅ {pos['name']}: +2 变体 (high-match + low-match)")

    if not new_entries:
        print("\n⚠️ 无法生成有效变体（所有缺失岗位无 required 技能）。")
        return 0

    if args.apply:
        golden.extend(new_entries)
        _save_golden(golden)
        print(f"\n✅ 已追加 {len(new_entries)} 条到 {GOLDEN_FILE}")
        print(f"   golden set 现有 {len(golden)} 条")
    else:
        print(f"\n📋 Dry-run: 将追加 {len(new_entries)} 条（使用 --apply 实际写入）")

    return 0


if __name__ == "__main__":
    sys.exit(main())
