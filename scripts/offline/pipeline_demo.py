"""Offline Pipeline Demo — 在无爬虫/无外网的环境下产出 extraction 数据。

# 为什么需要这个模块

线上 Pipeline 链路依赖爬虫抓取 JD → 抽取 → 同步图谱。离线环境
（演示、CI、本地开发）无外网时，演化看板 / 图谱质量 / 信任评分
永远为空。本模块用确定性 fixture JDs 替代爬虫，跑通同一 pipeline
链路，把 JDExtractionRecord / PositionRecord / SkillRecord 写入
PostgreSQL，并触发 graph_sync 投影到 Neo4j。

# 架构定位

    ┌──────────────┐     ┌─────────────────┐     ┌──────────────┐
    │ Fixture JDs  │ ──> │ offline extract │ ──> │ JDExtraction │
    │ (deterministic)   │ (no LLM, no net)│     │ Record (PG)  │
    └──────────────┘     └─────────────────┘     └──────┬───────┘
                                                       │
                                                       ▼  graph_sync
                                                ┌──────────────┐
                                                │  Neo4j graph │
                                                │ (projection) │
                                                └──────────────┘

# 使用方式

    python scripts/seed_demo_data.py --with-pipeline-demo
        # 触发 30 轮离线抽取，每次写 1 条 JD
    python scripts/seed_demo_data.py --with-pipeline-demo --rounds 5
        # 仅 5 轮
    python scripts/seed_demo_data.py --with-pipeline-demo --dry-run
        # 仅打印，不写库

# 与 crawler 的差异

| 维度       | crawler                 | pipeline_demo       |
|------------|-------------------------|---------------------|
| 数据来源   | 真实招聘网站             | 内置 fixture         |
| LLM        | 可选 (Qwen/MiMo/...)    | 完全跳过，用确定性归一 |
| 网络       | 必须                    | 必须不需要           |
| 适用环境   | 生产 / 演示 (有网)       | CI / 离线开发 / 评审  |
| 时间序列   | 实时 (依赖 cron)        | 按 rounds 离散生成    |
| 持久化     | PositionRecord/SkillRecord 等 | 同样的 ORM 模型     |

# 安全保证

1. 不会写入 APP_ENV=production 的环境
2. 每次写入前检查 fixture 是否已抽取过（幂等）
3. 不修改 PG 现有数据，仅追加
4. 不调用 LLM，不消耗 token
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import select

# Make `app.*` importable when invoked from starmap root.
BACKEND = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

logger = logging.getLogger("pipeline_demo")


# ---------------------------------------------------------------------------
# Fixture data — deterministic, no LLM, no network
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class JdFixture:
    """A single self-contained JD with deterministic skills."""

    position_name: str
    industry: str
    description: str
    required_skills: tuple[tuple[str, str, str], ...]  # (name, category, proficiency)
    bonus_skills: tuple[tuple[str, str, str], ...]
    experience_required: int
    knowledge_areas: tuple[str, ...] = ()
    tools: tuple[tuple[str, str], ...] = ()  # (name, category)


# 24 fixtures × multiple industries — covers all positions in current graph
FIXTURE_JDS: list[JdFixture] = [
    JdFixture(
        position_name="Senior Python Backend Engineer",
        industry="互联网/IT",
        description="Senior Python backend engineer for high-traffic SaaS platform.",
        required_skills=(
            ("Python", "hard_skill", "精通"),
            ("FastAPI", "hard_skill", "精通"),
            ("PostgreSQL", "hard_skill", "精通"),
            ("Redis", "hard_skill", "精通"),
            ("Docker", "tool", "熟悉"),
            ("Kubernetes", "tool", "了解"),
        ),
        bonus_skills=(("System Design", "hard_skill", "熟悉"),),
        experience_required=5,
        knowledge_areas=("分布式系统", "微服务"),
        tools=(("Docker", "devops"), ("Git", "devops")),
    ),
    JdFixture(
        position_name="Frontend Engineer",
        industry="互联网/IT",
        description="Vue3 + TypeScript frontend for data visualisation dashboards.",
        required_skills=(
            ("Vue", "hard_skill", "精通"),
            ("TypeScript", "hard_skill", "精通"),
            ("Element Plus", "framework", "熟悉"),
            ("Vite", "tool", "熟悉"),
            ("ECharts", "tool", "熟悉"),
        ),
        bonus_skills=(("G6", "tool", "了解"),),
        experience_required=3,
        knowledge_areas=("可视化", "前端工程化"),
        tools=(("Git", "devops"), ("Vite", "devops")),
    ),
    JdFixture(
        position_name="AI Engineer",
        industry="互联网/IT",
        description="LLM application engineer for agent / RAG / extraction pipelines.",
        required_skills=(
            ("Python", "hard_skill", "精通"),
            ("PyTorch", "hard_skill", "熟悉"),
            ("LangChain", "framework", "熟悉"),
            ("Transformer", "hard_skill", "了解"),
        ),
        bonus_skills=(("Milvus", "tool", "了解"), ("LlamaIndex", "framework", "了解")),
        experience_required=3,
        knowledge_areas=("LLM", "RAG", "Agent"),
        tools=(("PyTorch", "ml"),),
    ),
    JdFixture(
        position_name="Data Analyst",
        industry="互联网/IT",
        description="Data analyst for product metrics dashboards and A/B testing.",
        required_skills=(
            ("SQL", "hard_skill", "精通"),
            ("Python", "hard_skill", "熟悉"),
            ("Pandas", "library", "熟悉"),
            ("Tableau", "tool", "了解"),
        ),
        bonus_skills=(("Power BI", "tool", "了解"),),
        experience_required=2,
        knowledge_areas=("数据分析", "统计学"),
        tools=(("Tableau", "bi"),),
    ),
    JdFixture(
        position_name="DevOps Engineer",
        industry="互联网/IT",
        description="DevOps for K8s-based microservice platform.",
        required_skills=(
            ("Kubernetes", "tool", "精通"),
            ("Docker", "tool", "精通"),
            ("Terraform", "tool", "熟悉"),
            ("Prometheus", "tool", "熟悉"),
            ("Grafana", "tool", "熟悉"),
        ),
        bonus_skills=(("Ansible", "tool", "了解"),),
        experience_required=4,
        knowledge_areas=("SRE", "可观测性"),
        tools=(("Kubernetes", "devops"), ("Docker", "devops")),
    ),
    JdFixture(
        position_name="Mobile Engineer (iOS)",
        industry="互联网/IT",
        description="iOS engineer for Swift/SwiftUI consumer apps.",
        required_skills=(
            ("Swift", "hard_skill", "精通"),
            ("SwiftUI", "framework", "熟悉"),
            ("Combine", "framework", "了解"),
        ),
        bonus_skills=(("Objective-C", "hard_skill", "了解"),),
        experience_required=3,
        knowledge_areas=("iOS"),
        tools=(),
    ),
    JdFixture(
        position_name="Algorithm Engineer",
        industry="互联网/IT",
        description="Search / recommendation algorithm engineer.",
        required_skills=(
            ("Python", "hard_skill", "精通"),
            ("PyTorch", "hard_skill", "精通"),
            ("NumPy", "library", "熟悉"),
            ("Pandas", "library", "熟悉"),
        ),
        bonus_skills=(("Spark", "tool", "了解"),),
        experience_required=3,
        knowledge_areas=("推荐系统", "搜索", "机器学习"),
        tools=(),
    ),
    JdFixture(
        position_name="Security Engineer",
        industry="互联网/IT",
        description="Application security / DevSecOps.",
        required_skills=(
            ("OWASP", "framework", "精通"),
            ("Burp Suite", "tool", "熟悉"),
            ("Python", "hard_skill", "熟悉"),
        ),
        bonus_skills=(("Kubernetes", "tool", "了解"),),
        experience_required=3,
        knowledge_areas=("应用安全", "渗透测试"),
        tools=(),
    ),
]


# ---------------------------------------------------------------------------
# Deterministic extraction — no LLM, mirror normalise.py aliases
# ---------------------------------------------------------------------------

# Mirror of common alias mappings (kept minimal — used as offline ground truth).
_ALIAS_MAP: dict[str, str] = {
    "Python3": "Python",
    "Fastapi": "FastAPI",
    "Postgres": "PostgreSQL",
    "PostgresQL": "PostgreSQL",
    "K8s": "Kubernetes",
    "k8s": "Kubernetes",
    "TS": "TypeScript",
    "Vue3": "Vue",
    "Vue2": "Vue",
    "NLP": "Transformer",
    "ML": "PyTorch",
}


def _normalize(name: str) -> str:
    """Resolve alias → canonical. Mirrors backend/app/core/extraction/normalize.py."""
    return _ALIAS_MAP.get(name, name)


def _deterministic_hallucination_score(fixture: JdFixture, skill_name: str) -> float:
    """Stable synthetic hallucination score in [0, 0.3] — never fails truthiness.

    Uses a hash of (position, skill) so re-runs produce identical scores.
    """
    digest = hashlib.sha1(f"{fixture.position_name}|{skill_name}".encode()).digest()
    return round(digest[0] / 255 * 0.3, 3)


def _deterministic_confidence(fixture: JdFixture, skill_name: str) -> float:
    digest = hashlib.sha256(f"{fixture.position_name}|{skill_name}".encode()).digest()
    return round(0.7 + digest[0] / 255 * 0.25, 3)  # in [0.7, 0.95]


def _fixture_to_extraction_dict(fixture: JdFixture, offset_days: int) -> dict[str, Any]:
    """Convert one fixture to the shape expected by extract_from_jd output."""
    required = [
        {
            "name": _normalize(name),
            "category": cat,
            "level": prof,
            "importance": "required",
        }
        for name, cat, prof in fixture.required_skills
    ]
    preferred = [
        {
            "name": _normalize(name),
            "category": cat,
            "level": prof,
            "importance": "bonus",
        }
        for name, cat, prof in fixture.bonus_skills
    ]
    return {
        "success": True,
        "data": {
            "position_name": fixture.position_name,
            "industry": fixture.industry,
            "description": fixture.description,
            "required_skills": required,
            "preferred_skills": preferred,
            "experience_required": fixture.experience_required,
            "knowledge_areas": list(fixture.knowledge_areas),
            "tools": [{"name": n, "category": c} for n, c in fixture.tools],
            "validation": {
                "is_valid": True,
                "confidence": 0.9,
                "hallucinated_skills": [],
                "missing_skills": [],
                "issues": [],
            },
            "prompt_version": "offline-fixture-v1",
            "_hallucination_score_for_skill": {
                s["name"]: _deterministic_hallucination_score(fixture, s["name"])
                for s in required + preferred
            },
            "_confidence_for_skill": {
                s["name"]: _deterministic_confidence(fixture, s["name"])
                for s in required + preferred
            },
            "_extracted_at_offset_days": offset_days,
        },
    }


# ---------------------------------------------------------------------------
# Persistence — write to PG + project to Neo4j
# ---------------------------------------------------------------------------


def _ensure_not_production() -> None:
    from app.config import settings
    if getattr(settings, "app_env", "") == "production":
        raise SystemExit("Refusing to run pipeline_demo when APP_ENV=production")


async def _persist_extraction(
    session_factory: Any,
    driver: Any,
    fixture: JdFixture,
    offset_days: int,
    dry_run: bool,
) -> dict[str, Any]:
    """Persist one fixture: JDExtractionRecord + PositionRecord + Skills + graph projection."""
    from app.models.extraction_models import (
        JDExtractionRecord,
        PositionRecord,
        PositionSkillRelation,
        SkillRecord,
    )

    extraction_dict = _fixture_to_extraction_dict(fixture, offset_days)
    raw_json = json.dumps(extraction_dict, ensure_ascii=False, default=str)
    if dry_run:
        return {"position": fixture.position_name, "status": "dry-run", "bytes": len(raw_json)}

    async with session_factory() as session:
        # 1. Find or create the position record (PG is SSOT).
        pos_stmt = select(PositionRecord).where(PositionRecord.name == fixture.position_name)
        pos = (await session.execute(pos_stmt)).scalar_one_or_none()
        if pos is None:
            pos = PositionRecord(
                name=fixture.position_name,
                industry=fixture.industry,
                description=fixture.description,
                review_status="approved",
                created_by="system:pipeline_demo",
            )
            session.add(pos)
            await session.flush()
        position_id = pos.id

        # 2. Find or create skills + relations.
        skill_count = 0
        for name, category, _prof in (*fixture.required_skills, *fixture.bonus_skills):
            canonical = _normalize(name)
            sk_stmt = select(SkillRecord).where(SkillRecord.name == canonical)
            sk = (await session.execute(sk_stmt)).scalar_one_or_none()
            if sk is None:
                sk = SkillRecord(
                    name=canonical,
                    category=category,
                    source_count=0,
                )
                session.add(sk)
                await session.flush()
            sk.source_count = (sk.source_count or 0) + 1

            # Link to position (idempotent upsert).
            rel_stmt = select(PositionSkillRelation).where(
                PositionSkillRelation.position_id == position_id,
                PositionSkillRelation.skill_id == sk.id,
            )
            rel = (await session.execute(rel_stmt)).scalar_one_or_none()
            if rel is None:
                session.add(PositionSkillRelation(
                    position_id=position_id,
                    skill_id=sk.id,
                    confidence=_deterministic_confidence(fixture, canonical),
                    importance=(
                        "required" if (name, category, _prof) in fixture.required_skills
                        else "bonus"
                    ),
                ))
            skill_count += 1

        # 3. Write JDExtractionRecord with timestamps backdated for time-series spread.
        extracted_at = datetime.now(UTC) - timedelta(days=offset_days)
        extraction = JDExtractionRecord(
            jd_text=fixture.description,
            result=extraction_dict,
            status="approved",
            confidence=0.9,
            hallucination_score=_deterministic_hallucination_score(fixture, fixture.position_name),
            position_name=fixture.position_name,
            created_at=extracted_at,
        )
        session.add(extraction)
        await session.commit()

        record_id = extraction.id

    # 4. Project to Neo4j via graph_writer (best-effort, never block).
    neo4j_result: dict[str, Any] = {"synced": False, "reason": "skipped"}
    if driver is not None:
        try:
            from app.services.graph_sync import sync_from_pipeline
            neo4j_result = await sync_from_pipeline(
                run_id=str(record_id),
                extraction_data={"position_name": fixture.position_name},
                target_position=fixture.position_name,
            )
        except Exception as exc:  # noqa: BLE001
            neo4j_result = {"synced": False, "error": str(exc)}
            logger.warning("Neo4j projection failed for %s: %s", fixture.position_name, exc)

    return {
        "position": fixture.position_name,
        "extraction_id": str(record_id),
        "skill_count": skill_count,
        "neo4j": neo4j_result,
        "extracted_at": extracted_at.isoformat(),
    }


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def run(rounds: int = 24, dry_run: bool = False) -> dict[str, Any]:
    """Generate `rounds` extraction records spread over the last `rounds` days.

    Rounds default to len(FIXTURE_JDS) ≈ 8 so one full pass covers every
    fixture exactly once with 1-day offset; pass `--rounds 30` for richer
    timeseries spread.
    """
    _ensure_not_production()

    from app.dependencies import get_neo4j_driver, get_session_factory

    sf = get_session_factory()
    driver = None
    try:
        driver = get_neo4j_driver()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Neo4j driver unavailable: %s — graph projection will be skipped", exc)

    # Round-robin the fixtures to avoid over-representing any one position.
    pool = FIXTURE_JDS
    results: list[dict[str, Any]] = []
    for i in range(rounds):
        fixture = pool[i % len(pool)]
        offset = i  # 1-day steps give a 30-day timeseries
        try:
            res = await _persist_extraction(sf, driver, fixture, offset, dry_run)
        except Exception as exc:
            logger.exception("Failed to persist %s: %s", fixture.position_name, exc)
            res = {"position": fixture.position_name, "error": str(exc)}
        results.append(res)

    summary = {
        "rounds": rounds,
        "succeeded": sum(1 for r in results if "extraction_id" in r),
        "failed": sum(1 for r in results if "error" in r),
        "dry_run": dry_run,
        "neo4j_available": driver is not None,
        "results": results,
    }
    logger.info(
        "pipeline_demo: rounds=%d succeeded=%d failed=%d neo4j=%s",
        summary["rounds"],
        summary["succeeded"],
        summary["failed"],
        "yes" if summary["neo4j_available"] else "no",
    )
    return summary


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="Offline pipeline demo (no LLM, no network).")
    p.add_argument("--rounds", type=int, default=len(FIXTURE_JDS),
                   help=f"How many extraction records to write (default: {len(FIXTURE_JDS)}).")
    p.add_argument("--dry-run", action="store_true", help="Print what would happen, write nothing.")
    args = p.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    out = asyncio.run(run(rounds=args.rounds, dry_run=args.dry_run))
    print(json.dumps(out, ensure_ascii=False, default=str, indent=2))