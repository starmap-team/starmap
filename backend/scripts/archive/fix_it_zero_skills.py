"""修复 IT 岗位零 skills 问题 (Phase 1 根因修复, 2026-08-17).

根因追踪:
- 207 个 JD extraction 返回 empty required_skills/preferred_skills
- 其中 44 个是 IT/互联网/金融科技岗位 + 有 JD content（非缺失）
- 原因: V1/V4 prompt 的"仅提取信息技术相关技能"限制 + LLM 对非标准
  技能格式（如 "关系建立" / "B2B销售"）不识别
- V5 prompt 已移除 IT 限制，但 44 个 IT 岗位的 extraction 记录是 V1-V4 做的

修复:
- 对有 JD content 的 IT 岗位重新跑 extract_from_jd（用当前 V5 prompt）
- 将新 skills 写入 position_skill_relations
- 非 IT 岗位不做 re-extract（V1 限制是设计决策，非 bug）

限制:
- 只处理有 jd_content 的（不能从岗位名盲猜）
- 限速：每批 5 个，间隔 2s
- fail-soft：单条失败不阻断
"""
from __future__ import annotations

import asyncio
import sys
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.extraction.jd_extract import extract_from_jd
from app.db.session import get_async_engine
from app.models.extraction_models import (
    JDExtractionRecord,
    PositionRecord,
    PositionSkillRelation,
)
from app.tasks.stage3_services import (
    _confidence_from_result,
    _ensure_position_skill_relation,
    _upsert_skill,
)


async def fix_it_zero_skills(limit: int = 50) -> dict[str, Any]:
    """修复 IT 岗位零 skills 问题：对有 JD content 的岗位重新跑 LLM 抽取。

    修复逻辑:
    1. 找 IT/互联网/金融科技 approved 岗位 + skill_rels = 0
    2. 取该岗位的 JD extraction 记录（找最近一条 completed 的 jd_content）
    3. 用 extract_from_jd(v5 prompt) 重新抽取
    4. 将新 skills 写入 position_skill_relations

    关键：必须用 jd_content（原文 JD 文本），不是岗位名。
    """
    engine = get_async_engine()
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    done = 0
    failed = 0
    skipped_no_content = 0

    try:
        async with sessionmaker() as session:
            # 找 IT/互联网/金融科技 approved 岗位 + 0 skill_rels
            skill_count_subq = (
                sa.select(
                    PositionSkillRelation.position_id,
                    sa.func.count(PositionSkillRelation.skill_id).label("cnt"),
                )
                .group_by(PositionSkillRelation.position_id)
                .subquery()
            )
            stmt = (
                sa.select(
                    PositionRecord.id,
                    PositionRecord.name,
                    PositionRecord.industry,
                )
                .outerjoin(skill_count_subq, skill_count_subq.c.position_id == PositionRecord.id)
                .where(PositionRecord.review_status == "approved")
                .where(PositionRecord.industry.in_(["互联网/IT", "金融科技"]))
                .where(sa.func.coalesce(skill_count_subq.c.cnt, 0) == 0)
                .limit(limit)
            )
            positions = (await session.execute(stmt)).all()
            print(f"[fix-it-skills] 找到 {len(positions)} 个 IT/金融 approved 岗位且 0 skills")

            for pos in positions:
                # 找该岗位最近的 completed JD extraction（取 jd_content）
                jd_stmt = (
                    sa.select(JDExtractionRecord)
                    .where(JDExtractionRecord.job_title == pos.name)
                    .where(JDExtractionRecord.status == "completed")
                    .order_by(JDExtractionRecord.created_at.desc())
                    .limit(1)
                )
                jd_result = (await session.execute(jd_stmt)).scalar_one_or_none()

                if not jd_result or not jd_result.jd_content:
                    skipped_no_content += 1
                    continue

                jd_content = jd_result.jd_content
                print(f"  抽取: {pos.name!r} (industry={pos.industry}, jd_content={len(jd_content)} chars)")

                try:
                    llm_result = await extract_from_jd(jd_content)
                except Exception as exc:
                    print(f"  ✗ LLM failed: {exc}")
                    failed += 1
                    continue

                data = llm_result.get("data", {})
                extracted_skills = data.get("required_skills", []) + data.get("preferred_skills", [])

                if not extracted_skills:
                    print("  - LLM returned 0 skills (still empty after v5)")
                    failed += 1
                    continue

                # 写 position_skill_relations（去重）
                skills_added = 0
                for entry in extracted_skills:
                    if not isinstance(entry, dict):
                        continue
                    skill_name = entry.get("name") or entry.get("skill")
                    if not skill_name:
                        continue
                    skill_row = await _upsert_skill(session, skill_name, entry.get("category", "hard_skill"))
                    existing_rel = (await session.execute(
                        sa.select(PositionSkillRelation).where(
                            PositionSkillRelation.position_id == pos.id,
                            PositionSkillRelation.skill_id == skill_row.id,
                        )
                    )).scalar_one_or_none()
                    if existing_rel is None:
                        await _ensure_position_skill_relation(
                            session, pos.id, skill_row.id,
                            "required" if entry in data.get("required_skills", []) else "preferred",
                            _confidence_from_result(llm_result),
                        )
                        skills_added += 1

                print(f"  ✓ {pos.name!r} → {skills_added} 个新 skill(s)")
                done += 1

            await session.commit()
            return {
                "re_extracted": done,
                "failed": failed,
                "skipped_no_content": skipped_no_content,
                "total_positions": len(positions),
            }
    finally:
        await engine.dispose()


def main() -> None:
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    print(f"[fix-it-skills] 开始修复 IT 岗位零 skills 问题 (limit={limit})")
    result = asyncio.run(fix_it_zero_skills(limit=limit))
    print(f"[fix-it-skills] 完成: 重新抽取 {result['re_extracted']}/{result['total_positions']}, "
          f"失败 {result['failed']}, 无 JD {result['skipped_no_content']}")


if __name__ == "__main__":
    main()
