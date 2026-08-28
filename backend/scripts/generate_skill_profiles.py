"""Generate skill profiles for no-skill positions via qwen-plus (2026-08-28).

背景: 615 个 quality_hint='no_skills' 岗位的 source_run_id 全为 NULL
（历史 seed/demo/手动导入），无 JD 原文可重抽取 → 重抽取路径无效。
本脚本改为「岗位名 → LLM 生成技能画像」：用 qwen-plus 基于岗位名 + 行业
推断该岗位必备技能，建 PositionSkillRelation + 清 quality_hint。

安全:
- 执行前自动快照 position_records / position_skill_relations 到备份表
- 只新增 PSR（不删任何现有数据）
- 幂等: 仅处理 quality_hint='no_skills' 且 approved 的 IT 岗位
- 分批 limit（默认 20），失败静默记日志

用法:
    cd backend
    poetry run python -m scripts.generate_skill_profiles --limit 20 [--dry-run]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.extraction.industry_gate import IT_INDUSTRY_WHITELIST
from app.db.session import get_async_engine
from app.models.extraction_models import PositionRecord, PositionSkillRelation, SkillRecord

logger = logging.getLogger(__name__)

_BACKUP_TABLES = [
    ("position_records_bak_skillgen", "position_records"),
    ("position_skill_relations_bak_skillgen", "position_skill_relations"),
]

_SKILL_PROMPT = """你是招聘领域专家。根据岗位名称推断该岗位的必备技能（用于构建能力图谱）。
岗位: {position}
行业: {industry}
请返回 JSON: {{"required_skills": [{{"name": "技能名(英文标准名)"}}]}}
只返回 4-8 个真正核心的硬技能（编程语言/框架/工具/技术），不要泛化软技能。"""


async def _ensure_backups(sessionmaker: async_sessionmaker) -> None:
    async with sessionmaker() as session:
        for bak, src in _BACKUP_TABLES:
            await session.execute(
                text(f"CREATE TABLE IF NOT EXISTS {bak} AS SELECT * FROM {src}")
            )
        await session.commit()


async def _llm_skills(position_name: str, industry: str) -> list[str]:
    """qwen-plus 生成技能列表（失败返回空）。"""
    from app.core.extraction.llm_client import call_llm_with_fallback

    prompt = _SKILL_PROMPT.format(position=position_name, industry=industry or "互联网/IT")
    resp = await call_llm_with_fallback(prompt)
    content = str(resp.get("content", ""))
    # 提取 JSON
    try:
        start = content.find("{")
        end = content.rfind("}") + 1
        data = json.loads(content[start:end])
        skills = []
        for s in data.get("required_skills", []):
            name = (s.get("name") or "").strip()
            if name and len(name) <= 60:
                skills.append(name)
        return skills
    except Exception:
        logger.warning("skill gen parse failed for '{}': {}", position_name[:50], content[:100])
        return []


async def _upsert_skill(session: object, name: str) -> SkillRecord:
    """复用 stage3 的 skill upsert 语义（幂等 + 翻译）。"""
    from app.tasks.stage3_services import _upsert_skill

    return await _upsert_skill(session, name, "general")


async def generate(limit: int, dry_run: bool) -> dict[str, int]:
    engine = get_async_engine()
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    stats = {"processed": 0, "with_skills": 0, "no_skills": 0, "errors": 0}

    async with sessionmaker() as session:
        rows = (
            await session.execute(
                select(PositionRecord)
                .where(
                    PositionRecord.quality_hint == "no_skills",
                    PositionRecord.review_status == "approved",
                    PositionRecord.industry.in_(IT_INDUSTRY_WHITELIST),
                )
                .limit(limit)
            )
        ).scalars().all()
        for pos in rows:
            stats["processed"] += 1
            skills = await _llm_skills(pos.name or "", pos.industry or "")
            if not skills:
                stats["no_skills"] += 1
                continue
            if dry_run:
                logger.info("[dry-run] {} -> {}", pos.name[:40], skills[:4])
                stats["with_skills"] += 1
                continue
            for sk_name in skills:
                try:
                    skill = await _upsert_skill(session, sk_name)
                    # 幂等: 已存在关系跳过
                    exists = (
                        await session.execute(
                            select(PositionSkillRelation.id).where(
                                PositionSkillRelation.position_id == pos.id,
                                PositionSkillRelation.skill_id == skill.id,
                            ).limit(1)
                        )
                    ).first()
                    if exists is None:
                        session.add(PositionSkillRelation(
                            position_id=pos.id,
                            skill_id=skill.id,
                            requirement_type="required",
                            confidence=0.9,
                        ))
                except Exception as exc:  # noqa: BLE001
                    logger.warning("skill upsert failed for {}: {}", sk_name, exc)
                    stats["errors"] += 1
            # 有技能则清标记（可入图）
            pos.quality_hint = None
            stats["with_skills"] += 1
        if not dry_run:
            await session.commit()
    await engine.dispose()
    return stats


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    engine = get_async_engine()
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    await _ensure_backups(sessionmaker)
    await engine.dispose()
    logger.info("backup tables ensured")

    stats = await generate(args.limit, args.dry_run)
    logger.info("skillgen done: %s", stats)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
