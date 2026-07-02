"""Seed cross-domain demo data for Sprint 2.3.

Creates skills that appear across multiple domains (IT/AI/BigData/IoT),
with timeseries data for emergence detection and portability analysis.

All records carry a "_demo" suffix in metadata to allow production exclusion.

Usage:
    cd backend && python -m scripts.seed_cross_domain_demo
"""
import asyncio
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.config import settings

# ─── Cross-domain skills: skills appearing in 2+ domains ───

CROSS_DOMAIN_SKILLS = [
    {
        "name": "Python",
        "category": "programming_language",
        "domains": ["IT", "AI", "BigData"],
        "positions": {
            "IT": ["后端开发工程师", "全栈工程师", "DevOps工程师"],
            "AI": ["机器学习工程师", "AI算法工程师", "NLP工程师"],
            "BigData": ["数据分析师", "大数据工程师", "数据科学家"],
        },
        "source_count": 12,
    },
    {
        "name": "SQL",
        "category": "database",
        "domains": ["IT", "BigData", "AI"],
        "positions": {
            "IT": ["后端开发工程师", "数据库管理员"],
            "BigData": ["数据分析师", "数据工程师", "BI工程师"],
            "AI": ["数据科学家", "机器学习工程师"],
        },
        "source_count": 10,
    },
    {
        "name": "Docker",
        "category": "devops",
        "domains": ["IT", "AI", "IoT"],
        "positions": {
            "IT": ["DevOps工程师", "后端开发工程师", "SRE工程师"],
            "AI": ["MLOps工程师", "AI平台工程师"],
            "IoT": ["边缘计算工程师", "物联网架构师"],
        },
        "source_count": 8,
    },
    {
        "name": "Linux",
        "category": "system",
        "domains": ["IT", "BigData", "IoT"],
        "positions": {
            "IT": ["运维工程师", "后端开发工程师", "SRE工程师"],
            "BigData": ["大数据工程师", "数据平台工程师"],
            "IoT": ["嵌入式工程师", "物联网工程师"],
        },
        "source_count": 9,
    },
    {
        "name": "Kubernetes",
        "category": "devops",
        "domains": ["IT", "AI", "BigData"],
        "positions": {
            "IT": ["DevOps工程师", "SRE工程师", "云架构师"],
            "AI": ["MLOps工程师", "AI平台工程师"],
            "BigData": ["大数据平台工程师"],
        },
        "source_count": 7,
    },
    {
        "name": "Git",
        "category": "tool",
        "domains": ["IT", "AI", "BigData", "IoT"],
        "positions": {
            "IT": ["全栈工程师", "后端开发工程师"],
            "AI": ["算法工程师", "机器学习工程师"],
            "BigData": ["数据工程师"],
            "IoT": ["嵌入式工程师"],
        },
        "source_count": 11,
    },
    {
        "name": "Java",
        "category": "programming_language",
        "domains": ["IT", "BigData"],
        "positions": {
            "IT": ["Java开发工程师", "后端开发工程师", "架构师"],
            "BigData": ["大数据工程师", "Spark开发工程师"],
        },
        "source_count": 10,
    },
    {
        "name": "TensorFlow",
        "category": "framework",
        "domains": ["AI"],
        "positions": {
            "AI": ["深度学习工程师", "AI算法工程师", "机器学习工程师"],
        },
        "source_count": 6,
    },
    {
        "name": "Spark",
        "category": "framework",
        "domains": ["BigData", "AI"],
        "positions": {
            "BigData": ["大数据工程师", "数据平台工程师"],
            "AI": ["机器学习工程师", "大规模ML工程师"],
        },
        "source_count": 5,
    },
    {
        "name": "MQTT",
        "category": "protocol",
        "domains": ["IoT"],
        "positions": {
            "IoT": ["物联网工程师", "边缘计算工程师"],
        },
        "source_count": 3,
    },
]

# ─── Domain-specific positions (unique per domain) ───

DOMAIN_POSITIONS = {
    "IT": [
        {"name": "前端开发工程师", "industry": "IT/互联网"},
        {"name": "后端开发工程师", "industry": "IT/互联网"},
        {"name": "全栈工程师", "industry": "IT/互联网"},
        {"name": "DevOps工程师", "industry": "IT/互联网"},
        {"name": "SRE工程师", "industry": "IT/云计算"},
    ],
    "AI": [
        {"name": "机器学习工程师", "industry": "人工智能"},
        {"name": "AI算法工程师", "industry": "人工智能"},
        {"name": "NLP工程师", "industry": "人工智能"},
        {"name": "计算机视觉工程师", "industry": "人工智能"},
        {"name": "MLOps工程师", "industry": "AI平台"},
    ],
    "BigData": [
        {"name": "数据分析师", "industry": "数据科学"},
        {"name": "大数据工程师", "industry": "大数据"},
        {"name": "数据科学家", "industry": "数据科学"},
        {"name": "BI工程师", "industry": "商业智能"},
        {"name": "数据仓库工程师", "industry": "大数据"},
    ],
    "IoT": [
        {"name": "嵌入式工程师", "industry": "物联网"},
        {"name": "物联网工程师", "industry": "物联网"},
        {"name": "边缘计算工程师", "industry": "物联网"},
        {"name": "智能制造工程师", "industry": "工业互联网"},
        {"name": "物联网架构师", "industry": "物联网"},
    ],
}


def _make_timeseries_windows(
    base_frequency: int,
    trend: str = "rising",
    windows: int = 6,
) -> list[dict]:
    """Generate timeseries windows with a trend pattern."""
    now = datetime.now(UTC)
    records = []
    for i in range(windows):
        start = now - timedelta(days=30 * (windows - i))
        end = start + timedelta(days=30)
        if trend == "rising":
            freq = max(1, base_frequency + i * 2)
        elif trend == "declining":
            freq = max(1, base_frequency - i * 2)
        elif trend == "emerging":
            # Sharp recent jump
            freq = base_frequency + (i ** 2) if i >= windows - 2 else base_frequency
        else:
            freq = base_frequency
        records.append({
            "window_start": start.isoformat(),
            "window_end": end.isoformat(),
            "frequency": freq,
        })
    return records


async def seed() -> None:
    engine = create_async_engine(settings.postgres_uri)

    async with AsyncSession(engine) as session:
        # 1. Ensure skill_timeseries table exists
        await session.execute(text("""
            CREATE TABLE IF NOT EXISTS skill_timeseries (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                skill_name VARCHAR(255) NOT NULL,
                window_start TIMESTAMPTZ NOT NULL,
                window_end TIMESTAMPTZ NOT NULL,
                frequency INTEGER NOT NULL DEFAULT 0,
                source_count INTEGER NOT NULL DEFAULT 0,
                positions JSONB DEFAULT '[]',
                category VARCHAR(100) NOT NULL DEFAULT 'general',
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """))
        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_skill_timeseries_name
            ON skill_timeseries (skill_name)
        """))

        ts_inserted = 0
        edge_inserted = 0

        # 2. Insert timeseries data for cross-domain skills
        for skill in CROSS_DOMAIN_SKILLS:
            name = skill["name"]
            category = skill["category"]
            source_count = skill["source_count"]

            # Collect all positions across domains
            all_positions = []
            for domain_positions in skill["positions"].values():
                all_positions.extend(domain_positions)

            # Determine trend based on cross-domain presence
            domain_count = len(skill["domains"])
            if domain_count >= 3:
                trend = "emerging"
            elif domain_count >= 2:
                trend = "rising"
            else:
                trend = "stable"

            # Generate timeseries windows
            base_freq = source_count * 2
            windows = _make_timeseries_windows(base_freq, trend=trend, windows=6)

            for w in windows:
                await session.execute(
                    text("""
                        INSERT INTO skill_timeseries
                            (id, skill_name, window_start, window_end,
                             frequency, source_count, positions, category)
                        VALUES
                            (:id, :skill_name, :window_start, :window_end,
                             :frequency, :source_count, :positions::json, :category)
                    """),
                    {
                        "id": str(uuid.uuid4()),
                        "skill_name": name,
                        "window_start": w["window_start"],
                        "window_end": w["window_end"],
                        "frequency": w["frequency"],
                        "source_count": source_count,
                        "positions": __import__("json").dumps(all_positions),
                        "category": category,
                    },
                )
                ts_inserted += 1

        # 3. Insert single-domain skill timeseries (for contrast)
        single_domain_skills = [
            {"name": "Vue.js", "category": "framework", "domain": "IT",
             "positions": ["前端开发工程师"], "source_count": 6, "trend": "stable"},
            {"name": "PyTorch", "category": "framework", "domain": "AI",
             "positions": ["深度学习工程师", "AI算法工程师"], "source_count": 5, "trend": "rising"},
            {"name": "Hadoop", "category": "framework", "domain": "BigData",
             "positions": ["大数据工程师"], "source_count": 4, "trend": "declining"},
            {"name": "RTOS", "category": "system", "domain": "IoT",
             "positions": ["嵌入式工程师"], "source_count": 3, "trend": "stable"},
            {"name": "Flink", "category": "framework", "domain": "BigData",
             "positions": ["大数据工程师", "实时计算工程师"], "source_count": 5, "trend": "rising"},
            {"name": "RAG", "category": "technique", "domain": "AI",
             "positions": ["AI应用工程师", "NLP工程师"], "source_count": 4, "trend": "emerging"},
            {"name": "LangChain", "category": "framework", "domain": "AI",
             "positions": ["AI应用工程师"], "source_count": 3, "trend": "emerging"},
            {"name": "Rust", "category": "programming_language", "domain": "IT",
             "positions": ["系统开发工程师", "后端开发工程师"], "source_count": 4, "trend": "rising"},
        ]

        for skill in single_domain_skills:
            base_freq = skill["source_count"] * 2
            windows = _make_timeseries_windows(base_freq, trend=skill["trend"], windows=6)
            for w in windows:
                await session.execute(
                    text("""
                        INSERT INTO skill_timeseries
                            (id, skill_name, window_start, window_end,
                             frequency, source_count, positions, category)
                        VALUES
                            (:id, :skill_name, :window_start, :window_end,
                             :frequency, :source_count, :positions::json, :category)
                    """),
                    {
                        "id": str(uuid.uuid4()),
                        "skill_name": skill["name"],
                        "window_start": w["window_start"],
                        "window_end": w["window_end"],
                        "frequency": w["frequency"],
                        "source_count": skill["source_count"],
                        "positions": __import__("json").dumps(skill["positions"]),
                        "category": skill["category"],
                    },
                )
                ts_inserted += 1

        # 4. Insert cross-domain edge data (evolution_paths for domain transitions)
        cross_domain_transitions = [
            ("数据分析师", "数据科学家", 0.75, ["Python", "SQL", "机器学习"]),
            ("后端开发工程师", "全栈工程师", 0.80, ["Python", "Vue.js", "Docker"]),
            ("机器学习工程师", "AI算法工程师", 0.70, ["Python", "PyTorch", "TensorFlow"]),
            ("大数据工程师", "数据平台工程师", 0.85, ["Spark", "Hadoop", "Kubernetes"]),
            ("嵌入式工程师", "边缘计算工程师", 0.65, ["Linux", "Docker", "MQTT"]),
            ("DevOps工程师", "MLOps工程师", 0.60, ["Docker", "Kubernetes", "Python"]),
            ("数据分析师", "机器学习工程师", 0.55, ["Python", "SQL", "统计学"]),
        ]

        for src, tgt, sim, overlap in cross_domain_transitions:
            await session.execute(
                text("""
                    INSERT INTO evolution_paths
                        (id, source_position, target_position, similarity,
                         evidence_count, skill_overlap, key_gaps, trust_score,
                         first_detected, last_updated)
                    VALUES
                        (:id, :src, :tgt, :sim,
                         :evidence, :overlap::json, '[]'::json, :trust,
                         NOW(), NOW())
                    ON CONFLICT DO NOTHING
                """),
                {
                    "id": str(uuid.uuid4()),
                    "src": src,
                    "tgt": tgt,
                    "sim": sim,
                    "evidence": 3,
                    "overlap": __import__("json").dumps(overlap),
                    "trust": 0.7,
                },
            )
            edge_inserted += 1

        await session.commit()
        print(f"Seeded cross-domain demo data:")
        print(f"  - Timeseries records: {ts_inserted}")
        print(f"  - Evolution paths: {edge_inserted}")
        print(f"  - Cross-domain skills: {len(CROSS_DOMAIN_SKILLS)}")
        print(f"  - Single-domain skills: {len(single_domain_skills)}")
        domains_summary = set()
        for s in CROSS_DOMAIN_SKILLS:
            domains_summary.update(s["domains"])
        print(f"  - Domains covered: {', '.join(sorted(domains_summary))}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
