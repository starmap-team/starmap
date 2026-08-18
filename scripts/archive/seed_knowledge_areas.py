"""Phase 13 Step 3: Seed 12 KnowledgeArea + Position links (idempotent, single tx)."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from neo4j import AsyncGraphDatabase
from sqlalchemy import select

from app.config import settings
from app.db.session import get_async_engine
from app.models.extraction_models import PositionRecord

KA_DEFINITIONS: list[dict[str, str]] = [
    {"name": "人工智能", "description": "AI / 机器学习 / 深度学习 / NLP / LLM"},
    {"name": "AI/机器学习", "description": "AI / ML / 算法 / Transformer"},
    {"name": "大数据", "description": "大数据 / 数据科学 / 数据分析 / BI"},
    {"name": "数据科学", "description": "数据科学 / 数据分析 / 统计"},
    {"name": "数据工程", "description": "ETL / 数仓 / 数据仓库"},
    {"name": "前端开发", "description": "前端 / Web / React / Vue / H5"},
    {"name": "后端开发", "description": "后端 / Backend / 服务端 / 微服务"},
    {"name": "云计算/DevOps", "description": "云 / DevOps / SRE / 运维 / k8s / Docker"},
    {"name": "网络安全", "description": "网络安全 / 渗透 / Security / IAM"},
    {"name": "移动开发", "description": "iOS / Android / Flutter / React Native"},
    {"name": "测试", "description": "测试 / QA / 测开 / SDET"},
    {"name": "嵌入式与物联网", "description": "嵌入式 / IoT / 单片机"},
    {"name": "游戏开发", "description": "游戏 / Unity / Unreal"},
    {"name": "区块链与Web3", "description": "区块链 / Web3 / Solidity"},
    {"name": "数据库与存储", "description": "数据库 / DBA / MySQL / PostgreSQL / Redis"},
    {"name": "互联网/IT", "description": "互联网 / IT 通用"},
    {"name": "项目管理与协作", "description": "PM / Scrum Master / 产品经理 / 运营"},
    {"name": "其他", "description": "兜底分类"},
]


async def seed_ka() -> int:
    driver = AsyncGraphDatabase.driver(
        settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password)
    )
    try:
        async with driver.session() as session:
            for ka in KA_DEFINITIONS:
                await session.run(
                    "MERGE (n:KnowledgeArea {name: $name}) "
                    "SET n.description = $desc",
                    name=ka["name"],
                    desc=ka["description"],
                )
        return len(KA_DEFINITIONS)
    finally:
        await driver.close()


async def link_positions_by_industry() -> int:
    engine = get_async_engine()
    async with engine.begin() as conn:
        from sqlalchemy.ext.asyncio import AsyncSession
        session = AsyncSession(bind=conn)
        result = await session.execute(
            select(PositionRecord.name, PositionRecord.industry)
        )
        positions = result.all()

    if not positions:
        return 0

    from app.services.graph_overview import _classify_industry
    rows = [
        {"p_name": name, "ka_name": _classify_industry(name, industry or "")}
        for name, industry in positions
    ]

    # Single session = single transaction: KA + Position resolved atomically
    driver = AsyncGraphDatabase.driver(
        settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password)
    )
    try:
        async with driver.session() as session:
            result = await session.run(
                "UNWIND $rows AS row "
                "MATCH (p:Position {name: row.p_name}) "
                "MATCH (ka:KnowledgeArea {name: row.ka_name}) "
                "SET p.knowledge_area = row.ka_name "
                "RETURN count(*) AS linked",
                rows=rows,
            )
            record = await result.single()
            return int(record["linked"]) if record else 0
    finally:
        await driver.close()


async def main() -> None:
    n_ka = await seed_ka()
    print(f"[1/2] Upserted {n_ka} KnowledgeArea nodes")
    n_linked = await link_positions_by_industry()
    print(f"[2/2] Linked {n_linked} positions to their industry KA (via Position.knowledge_area)")


if __name__ == "__main__":
    asyncio.run(main())
