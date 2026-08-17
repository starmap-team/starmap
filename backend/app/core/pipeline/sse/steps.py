"""Pipeline 步骤实现 — 求职者业务闭环的6个处理步骤。

每个步骤通过 PipelineContext 传递数据，由 PipelineEngine 统一编排。
"""

from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger

from app.config import settings
from app.core.extraction.jd_extract import extract_from_jd
from app.core.pipeline.sse.contracts import ExtractedSkill, PipelineContext
from app.repositories.position_repository import PositionRepository
from app.services.match_service import run_match
from app.services.recommendation_service import PositionRecommender
from app.services.resume_service import extract_resume_text


class ResumeParseStep:
    """步骤1：简历解析 — PDF/DOCX → 纯文本。"""

    name = "resume_parse"
    timeout = 60

    async def execute(self, ctx: PipelineContext) -> PipelineContext:
        if ctx.resume_text:
            return ctx  # 已有文本，跳过

        content_bytes: bytes | None = None
        filename = "resume.pdf"

        if ctx.resume_file is not None:
            if hasattr(ctx.resume_file, "read"):
                # UploadFile 对象
                content_bytes = await ctx.resume_file.read()  # type: ignore[union-attr]
                filename = getattr(ctx.resume_file, "filename", "resume.pdf") or "resume.pdf"
            elif isinstance(ctx.resume_file, (bytes, bytearray)):
                # 已读取的字节内容
                content_bytes = bytes(ctx.resume_file)

        if not content_bytes:
            ctx.errors.append("resume_parse: 无文件内容")
            return ctx

        try:
            ctx.resume_text = extract_resume_text(filename, content_bytes)
            logger.info("[Pipeline] Resume parsed: {} chars", len(ctx.resume_text))
        except Exception as exc:
            ctx.errors.append(f"resume_parse: {exc}")
            logger.error("[Pipeline] Resume parse failed: {}", exc)

        return ctx


class SkillExtractStep:
    """步骤2：技能提取 — LLM 抽取 + 标准化 → ExtractedSkill 列表。"""

    name = "skill_extract"
    # P1 fix (Phase 24 求职者分析): 30s→120s —— LLM 降级链（云端秒级 / 本地
    # Ollama fallback 40-120s+）下 30s 必超时，导致后续 match/learn/recommend
    # 级联失败（实测 4 警告全空结果）。对齐 MatchStep.timeout=120。
    timeout = 120

    async def execute(self, ctx: PipelineContext) -> PipelineContext:
        if not ctx.resume_text:
            ctx.errors.append("skill_extract: 无简历文本")
            return ctx

        try:
            result = await extract_from_jd(ctx.resume_text, options={"source": "resume"})
            if not result.get("success"):
                ctx.errors.append(f"skill_extract: {result.get('error', 'unknown')}")
                return ctx

            data = result.get("data", {})
            normalization = result.get("normalization", [])

            # 构建标准化映射
            norm_map: dict[str, dict[str, Any]] = {}
            for norm in normalization:
                if norm.get("original"):
                    norm_map[norm["original"]] = norm

            skills: list[ExtractedSkill] = []
            for skill_entry in data.get("required_skills", []):
                raw_name = skill_entry.get("name", "")
                if not raw_name:
                    continue

                # 查找对应的标准化结果
                norm_info = norm_map.get(raw_name, {})
                canonical = norm_info.get("normalized") or raw_name

                skills.append(
                    ExtractedSkill(
                        name=canonical,
                        raw_name=raw_name,
                        category=skill_entry.get("category", "hard_skill"),
                        proficiency=skill_entry.get("proficiency", "熟悉"),
                        confidence=norm_info.get("confidence", 0.5),
                        source="llm_extraction",
                    )
                )

            ctx.extracted_skills = skills
            logger.info("[Pipeline] Extracted {} skills from resume", len(skills))
        except Exception as exc:
            ctx.errors.append(f"skill_extract: {exc}")
            logger.error("[Pipeline] Skill extract failed: {}", exc)

        return ctx


class MatchStep:
    """步骤3：岗位匹配 — 对目标岗位进行匹配评分。"""

    name = "match"
    timeout = 120

    def __init__(self, repo: PositionRepository, driver: Any = None, db_session: Any = None) -> None:
        self._repo = repo
        self._driver = driver
        self._db_session = db_session

    async def execute(self, ctx: PipelineContext) -> PipelineContext:
        if not ctx.extracted_skills:
            ctx.errors.append("match: 无技能数据")
            return ctx

        try:
            profiles = await self._repo.get_all_position_profiles()
            if not profiles:
                ctx.errors.append("match: 无岗位画像数据")
                return ctx

            # 确定要匹配的岗位列表
            target_positions = ctx.target_positions or list(profiles.keys())

            # 转换为 run_match 期望的格式
            person_skills = [{"skill": s.name, "proficiency": s.proficiency} for s in ctx.extracted_skills]

            # 并行匹配（限制并发数，配置项化以便运行时调优）
            sem = asyncio.Semaphore(settings.pipeline_match_concurrency)

            async def _match_one(pos_name: str) -> tuple[str, dict[str, Any] | None]:
                async with sem:
                    try:
                        result = await run_match(
                            target_position=pos_name,
                            person_skills=person_skills,
                            driver=self._driver,
                            db_session=self._db_session,
                            repo=self._repo,
                        )
                        return pos_name, result
                    except Exception as exc:
                        logger.error("[Pipeline] Match failed for '{}': {}", pos_name, exc)
                        return pos_name, None

            tasks = [_match_one(pos) for pos in target_positions]
            results = await asyncio.gather(*tasks)

            for pos_name, result in results:
                if result:
                    # P5 fix: 注入 _display_name（name_cn 优先）——分析报告 top_matches
                    # 此前显示英文 name（Senior Controller – Reporting & Insights），
                    # 岗位详情页用 name_cn || name（高级财务控制 — 报告与洞察）不一致。
                    profile = profiles.get(pos_name)
                    result["_display_name"] = (profile.name_cn if profile and profile.name_cn else "") or pos_name
                    ctx.match_results[pos_name] = result

            # 设置数据源标记
            data_stats = await self._repo.get_data_quality_stats()
            ctx.data_source = "graph" if data_stats.coverage_ratio >= 0.3 else "hardcoded_fallback"

            logger.info("[Pipeline] Matched {} positions (data_source={})", len(ctx.match_results), ctx.data_source)
        except Exception as exc:
            ctx.errors.append(f"match: {exc}")
            logger.error("[Pipeline] Match step failed: {}", exc)

        return ctx


class LearningPathStep:
    """步骤4：学习路径 — 为 top 匹配岗位填充学习路径和学习资源。"""

    name = "learning_path"
    timeout = 30

    def __init__(self, driver: Any = None) -> None:
        self._driver = driver

    async def execute(self, ctx: PipelineContext) -> PipelineContext:
        if not ctx.match_results:
            ctx.errors.append("learning_path: 无匹配结果")
            return ctx

        from app.services.match_service import enrich_learning_paths

        # 为每个岗位的差距详情附加学习资源
        for _pos_name, result in ctx.match_results.items():
            gap_details = result.get("skill_gap_detail", [])
            if gap_details:
                enriched = await enrich_learning_paths(gap_details, self._driver)
                result["skill_gap_detail"] = enriched

        logger.info("[Pipeline] Learning paths enriched for {} positions", len(ctx.match_results))
        return ctx


class RecommendStep:
    """步骤5：岗位推荐 — 根据技能画像推荐 Top-K 岗位。"""

    name = "recommend"
    timeout = 30

    def __init__(self, repo: PositionRepository, driver: Any = None, db_session: Any = None) -> None:
        self._recommender = PositionRecommender(repo)
        self._driver = driver
        self._db_session = db_session

    async def execute(self, ctx: PipelineContext) -> PipelineContext:
        if not ctx.extracted_skills:
            ctx.errors.append("recommend: 无技能数据")
            return ctx

        try:
            recs = await self._recommender.recommend(ctx.extracted_skills, top_k=10)
            # P4 fix (Phase 24 求职者分析): 推荐岗位的 match_score 复用 MatchStep
            # 的 ctx.match_results（graph repo，与 top_matches 口径一致）——此前
            # PositionRecommender 用 get_all_position_profiles（PG repo）独立计算，
            # 同岗位 graph=0.82 / PG=0.0，导致前端"匹配度"列误显示 0.0%。
            match_by_position: dict[str, float] = {
                name: float(res.get("match_score", 0.0))
                for name, res in ctx.match_results.items()
            }
            # P5 fix: 推荐岗位名同样用 name_cn（复用 MatchStep 注入的 _display_name）
            display_by_position: dict[str, str] = {
                name: (res.get("_display_name") or name)
                for name, res in ctx.match_results.items()
            }
            ctx.recommended_positions = [
                {
                    "position": display_by_position.get(r.position, r.position),
                    "score": r.score,
                    "match_score": round(match_by_position.get(r.position, r.match_score), 4),
                    "developability": r.developability,
                    "market_demand": r.market_demand,
                    "match_detail": r.match_detail,
                }
                for r in recs
            ]
            logger.info("[Pipeline] Recommended {} positions", len(ctx.recommended_positions))
        except Exception as exc:
            ctx.errors.append(f"recommend: {exc}")
            logger.error("[Pipeline] Recommend step failed: {}", exc)

        return ctx
