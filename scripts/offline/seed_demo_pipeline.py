"""Offline pipeline data producer — Stage 4 (Phase C).

Purpose
=======
The StarMap pipeline historically depends on external crawlers (BOSS / 拉勾 /
51Job / GitHub) to feed JDExtractionRecord into PG. When those crawlers cannot
reach the internet (offline envs, CI, demos), the entire pipeline goes silent
and downstream modules (EvolutionDashboard, QualityDashboard, PipelineMonitor)
stay empty.

This script reproduces the pipeline contract *offline*:

  1. Take a curated list of sample JD texts (SAMPLE_JDS below).
  2. For each, run a deterministic extraction that mirrors what
     `extract_from_jd` would produce (position_name, required_skills,
     preferred_skills, confidence, hallucination_score, etc.).
  3. Persist the result as a `JDExtractionRecord` in PG with status='completed'.
  4. Push the corresponding nodes/edges into Neo4j via the `GraphProjector`
     so downstream reads see a consistent picture.
  5. Backfill `EvolutionSnapshot` rows so the EvolutionDashboard stops being
     a flat zero-state.
  6. Refresh the `quality/dashboard` derived metrics by writing one
     `JDExtractionRecord.confidence` per row, which feeds trust/hallucination.

The result: a single `python scripts/seed_demo_pipeline.py --apply` produces
enough data for every page that previously read as empty.

Usage
=====
    python scripts/seed_demo_pipeline.py --dry-run
    python scripts/seed_demo_pipeline.py --apply

Exit codes
==========
    0  success
    1  PG / Neo4j driver unavailable
    2  unexpected error
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

BACKEND = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("seed_demo_pipeline")


# ---------------------------------------------------------------------------
# Sample JD corpus — hand-tuned to populate each page with plausible content.
# ---------------------------------------------------------------------------

SAMPLE_JDS: list[dict] = [
    {
        "title": "大模型应用工程师",
        "industry": "AI/互联网",
        "jd": (
            "岗位：大模型应用工程师\n"
            "要求：精通 Python、LangChain、RAG、Prompt Engineering、Fine-tuning、LLM；\n"
            "熟悉 LlamaIndex、ChromaDB、OpenAI API、PyTorch；3年经验；硕士。\n"
        ),
        "skills": {
            "required": ["Python", "LangChain", "RAG", "Prompt Engineering", "Fine-tuning", "LLM"],
            "preferred": ["LlamaIndex", "ChromaDB", "OpenAI API", "PyTorch"],
        },
        "exp": 3, "edu": "硕士",
        "confidence": 0.92, "hallucination_score": 0.08,
    },
    {
        "title": "高级 Python 后端工程师",
        "industry": "互联网/IT",
        "jd": (
            "岗位：高级 Python 后端工程师\n"
            "要求：精通 Python、FastAPI、PostgreSQL、Docker、Kubernetes；\n"
            "熟悉 Redis、Celery、SQLAlchemy；5年以上经验；本科及以上。\n"
        ),
        "skills": {
            "required": ["Python", "FastAPI", "PostgreSQL", "Docker", "Kubernetes"],
            "preferred": ["Redis", "Celery", "SQLAlchemy", "Nginx"],
        },
        "exp": 5, "edu": "本科",
        "confidence": 0.95, "hallucination_score": 0.04,
    },
    {
        "title": "前端开发工程师",
        "industry": "互联网/IT",
        "jd": (
            "岗位：前端开发工程师\n"
            "要求：精通 JavaScript、TypeScript、Vue.js、HTML5、CSS3；\n"
            "熟悉 React、Vite、Webpack；3年以上经验；本科。\n"
        ),
        "skills": {
            "required": ["JavaScript", "TypeScript", "Vue.js", "HTML5", "CSS3"],
            "preferred": ["React", "Vite", "Webpack", "Tailwind CSS"],
        },
        "exp": 3, "edu": "本科",
        "confidence": 0.90, "hallucination_score": 0.06,
    },
    {
        "title": "数据分析师",
        "industry": "金融/互联网",
        "jd": (
            "岗位：数据分析师\n"
            "要求：精通 SQL、Python、Tableau、Pandas、NumPy；\n"
            "熟悉机器学习基本算法（回归、分类、聚类）；本科及以上。\n"
        ),
        "skills": {
            "required": ["SQL", "Python", "Tableau", "Pandas", "NumPy"],
            "preferred": ["Scikit-learn", "Power BI", "Spark"],
        },
        "exp": 3, "edu": "本科",
        "confidence": 0.88, "hallucination_score": 0.10,
    },
    {
        "title": "DevOps 工程师",
        "industry": "互联网/IT",
        "jd": (
            "岗位：DevOps 工程师\n"
            "要求：精通 Docker、Kubernetes、Linux、Jenkins、CI/CD、AWS；\n"
            "熟悉 Terraform、Ansible、Prometheus。\n"
        ),
        "skills": {
            "required": ["Docker", "Kubernetes", "Linux", "Jenkins", "CI/CD", "AWS"],
            "preferred": ["Terraform", "Ansible", "Prometheus"],
        },
        "exp": 4, "edu": "本科",
        "confidence": 0.87, "hallucination_score": 0.09,
    },
    {
        "title": "AI 算法工程师",
        "industry": "AI/互联网",
        "jd": (
            "岗位：AI 算法工程师\n"
            "要求：精通 Python、PyTorch、TensorFlow、Transformer、NLP；\n"
            "熟悉 BERT、GPT、强化学习；硕士及以上。\n"
        ),
        "skills": {
            "required": ["Python", "PyTorch", "TensorFlow", "Transformer", "NLP"],
            "preferred": ["BERT", "GPT", "强化学习", "CUDA"],
        },
        "exp": 3, "edu": "硕士",
        "confidence": 0.91, "hallucination_score": 0.05,
    },
    {
        "title": "测试工程师 (QA)",
        "industry": "互联网/IT",
        "jd": (
            "岗位：测试工程师\n"
            "要求：精通 Python、Selenium、Pytest、Postman、Jira；\n"
            "熟悉 JMeter、CI/CD、性能测试。\n"
        ),
        "skills": {
            "required": ["Python", "Selenium", "Pytest", "Postman", "Jira"],
            "preferred": ["JMeter", "CI/CD", "性能测试"],
        },
        "exp": 3, "edu": "本科",
        "confidence": 0.84, "hallucination_score": 0.12,
    },
    {
        "title": "数据工程师",
        "industry": "互联网/IT",
        "jd": (
            "岗位：数据工程师\n"
            "要求：精通 SQL、Python、Spark、Hive、Airflow；\n"
            "熟悉 Kafka、Flink、ClickHouse。\n"
        ),
        "skills": {
            "required": ["SQL", "Python", "Spark", "Hive", "Airflow"],
            "preferred": ["Kafka", "Flink", "ClickHouse"],
        },
        "exp": 4, "edu": "本科",
        "confidence": 0.86, "hallucination_score": 0.08,
    },
]


# ---------------------------------------------------------------------------
# Main routine
# ---------------------------------------------------------------------------


async def _run(apply: bool) -> dict:
    from sqlalchemy import select

    from app.dependencies import get_session_factory, get_neo4j_driver
    from app.models.extraction_models import JDExtractionRecord, PositionRecord, SkillRecord
    from app.services.graph_projector import GraphProjector

    sf = get_session_factory()
    try:
        driver = get_neo4j_driver()
    except Exception as exc:
        logger.error("Neo4j driver unavailable: %s", exc)
        return {"status": "neo4j_unavailable", "error": str(exc)}

    if driver is None:
        return {"status": "neo4j_unavailable"}

    report = {
        "status": "ok",
        "extractions_written": 0,
        "positions_upserted": 0,
        "skills_upserted": 0,
        "edges_upserted": 0,
        "evolution_snapshots_written": 0,
        "dry_run": not apply,
    }

    async with sf() as session:
        # 1. Walk through SAMPLE_JDS, ensure PG Position + Skill + JDExtractionRecord
        projector = GraphProjector(driver)
        all_skills: set[str] = set()
        for sample in SAMPLE_JDS:
            title = sample["title"]
            industry = sample["industry"]
            jd_text = sample["jd"]
            confidence = sample["confidence"]
            hallucination = sample["hallucination_score"]
            required = sample["skills"]["required"]
            preferred = sample["skills"]["preferred"]
            for s in required + preferred:
                all_skills.add(s)

            # Upsert Position (find or create)
            pos_stmt = select(PositionRecord).where(PositionRecord.name == title)
            pos = (await session.execute(pos_stmt)).scalar_one_or_none()
            if pos is None:
                pos = PositionRecord(
                    id=uuid4(),
                    name=title,
                    name_cn=title,
                    industry=industry,
                    description=jd_text[:500],
                    review_status="approved",
                )
                session.add(pos)
                await session.flush()
                logger.info("  + Position: %s (%s)", title, industry)

            # Upsert Skills
            skill_id_map: dict[str, str] = {}
            for skill_name in set(required + preferred):
                sk_stmt = select(SkillRecord).where(SkillRecord.name == skill_name)
                sk = (await session.execute(sk_stmt)).scalar_one_or_none()
                if sk is None:
                    sk = SkillRecord(
                        id=uuid4(),
                        name=skill_name,
                        category="hard_skill",
                        source_count=0,
                        confidence=float(confidence),
                    )
                    session.add(sk)
                    await session.flush()
                    logger.info("    + Skill: %s", skill_name)
                skill_id_map[skill_name] = str(sk.id)

            # Persist JDExtractionRecord
            payload = {
                "id": uuid4(),
                "raw_jd_text": jd_text,
                "cleaned_jd_text": jd_text,
                "extracted_data": {
                    "position_name": title,
                    "industry": industry,
                    "description": jd_text,
                    "required_skills": [{"name": s, "category": "hard_skill", "proficiency": "精通"} for s in required],
                    "preferred_skills": [{"name": s, "category": "hard_skill", "proficiency": "熟悉"} for s in preferred],
                },
                "position_id": pos.id,
                "position_name": title,
                "industry": industry,
                "experience_required": sample["exp"],
                "education_required": sample["edu"],
                "required_skills": required,
                "preferred_skills": preferred,
                "confidence": float(confidence),
                "hallucination_score": float(hallucination),
                "status": "completed",
                "source": "offline_seed",
                "created_at": datetime.now(UTC),
                "updated_at": datetime.now(UTC),
            }
            record = JDExtractionRecord(**payload)
            session.add(record)
            report["extractions_written"] += 1
            logger.info("  + ExtractionRecord: %s (conf=%.2f, hallu=%.2f)",
                        title, confidence, hallucination)

            # Backfill skills source_count (for trust proxy)
            for s in set(required + preferred):
                sk = (await session.execute(
                    select(SkillRecord).where(SkillRecord.name == s)
                )).scalar_one()
                sk.source_count = (sk.source_count or 0) + 1

        if apply:
            await session.commit()
            logger.info("PG committed: %d extraction records", report["extractions_written"])
        else:
            await session.rollback()

        # 2. Push positions + skills to Neo4j via projector (best-effort)
        if apply and driver is not None:
            try:
                # Build projector inputs from PG after the commit
                pos_rows = (await session.execute(select(PositionRecord))).scalars().all()
                sk_rows = (await session.execute(select(SkillRecord))).scalars().all()
                positions_payload = [
                    {
                        "canonical_id": str(p.id),
                        "name": p.name,
                        "name_cn": p.name_cn or "",
                        "industry": p.industry or "",
                        "description": (p.description or "")[:500],
                    }
                    for p in pos_rows
                ]
                skills_payload = [
                    {
                        "canonical_id": str(s.id),
                        "name": s.name,
                        "category": s.category,
                        "source_count": s.source_count or 0,
                    }
                    for s in sk_rows
                ]
                result = await projector.apply_batch(
                    positions=positions_payload, skills=skills_payload
                )
                report["positions_upserted"] = result.nodes_upserted
                report["skills_upserted"] = result.nodes_upserted  # combined count
                logger.info(
                    "projector upsert: nodes=%d edges=%d errors=%s",
                    result.nodes_upserted, result.edges_upserted, result.errors,
                )

                # 3. Build the BELONGS_TO + REQUIRES edges
                edges_payload: list[dict] = []
                for sample in SAMPLE_JDS:
                    # Look up the canonical position id
                    pos = next((p for p in pos_rows if p.name == sample["title"]), None)
                    if pos is None:
                        continue
                    for s in set(sample["skills"]["required"] + sample["skills"]["preferred"]):
                        sk = next((x for x in sk_rows if x.name == s), None)
                        if sk is None:
                            continue
                        edges_payload.append({
                            "position_id": str(pos.id),
                            "skill_id": str(sk.id),
                            "level": "精通" if s in sample["skills"]["required"] else "熟悉",
                            "required": s in sample["skills"]["required"],
                        })
                if edges_payload:
                    await projector.apply_relations(edges_payload, rel_type="REQUIRES")
                    report["edges_upserted"] = len(edges_payload)
                    logger.info("REQUIRES edges written: %d", len(edges_payload))
            except Exception as exc:
                logger.warning("Neo4j projection skipped: %s", exc)

        # 4. Backfill EvolutionSnapshot rows spanning the last 14 days
        if apply:
            try:
                from app.models.evolution_models import EvolutionSnapshot  # type: ignore

                base = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
                for offset in range(14):
                    day = base - timedelta(days=offset)
                    existing = (await session.execute(
                        select(EvolutionSnapshot).where(EvolutionSnapshot.snapshot_date == day.date())
                    )).scalar_one_or_none()
                    if existing:
                        continue
                    snap = EvolutionSnapshot(
                        snapshot_date=day.date(),
                        scope="global",
                        total_skills=len(all_skills) + offset,  # monotonically growing
                        new_skills=1 + (offset % 3),
                        cii_index=100 + offset * 1.5,
                        created_at=day,
                    )
                    session.add(snap)
                    report["evolution_snapshots_written"] += 1
                await session.commit()
                logger.info("Evolution snapshots written: %d", report["evolution_snapshots_written"])
            except (ImportError, AttributeError) as exc:
                logger.warning("EvolutionSnapshot model unavailable: %s", exc)
                report["evolution_snapshots_written"] = "skipped: model unavailable"

    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Offline pipeline data producer (writes PG + Neo4j + Evolution)"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes. Without this flag the script runs as a dry-run.",
    )
    args = parser.parse_args()

    try:
        report = asyncio.run(_run(apply=args.apply))
    except Exception as exc:  # noqa: BLE001
        logger.error("seed_demo_pipeline failed: %s", exc, exc_info=True)
        return 2

    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report.get("status") == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())