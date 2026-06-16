import asyncio
import os
import sys

from neo4j import AsyncGraphDatabase
from loguru import logger


async def create_constraints(driver):
    constraints = [
        "CREATE CONSTRAINT IF NOT EXISTS FOR (p:Position) REQUIRE p.name IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (s:Skill) REQUIRE s.name IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (i:Industry) REQUIRE i.name IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (k:KnowledgeArea) REQUIRE k.name IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (t:Tool) REQUIRE t.name IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Certificate) REQUIRE c.name IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (l:LearningResource) REQUIRE l.name IS UNIQUE",
    ]
    async with driver.session() as session:
        for cql in constraints:
            await session.run(cql)
            logger.info(f"Constraint ensured: {cql.split('(')[0].strip()}")
    logger.info(f"All {len(constraints)} constraints created/verified.")


async def create_indexes(driver):
    indexes = [
        "CREATE INDEX IF NOT EXISTS FOR (s:Skill) ON (s.category)",
        "CREATE INDEX IF NOT EXISTS FOR (p:Position) ON (p.industry)",
        "CREATE INDEX IF NOT EXISTS FOR (s:Skill) ON (s.source_count)",
        "CREATE INDEX IF NOT EXISTS FOR (p:Position) ON (p.created_at)",
    ]
    async with driver.session() as session:
        for cql in indexes:
            await session.run(cql)
            logger.info(f"Index ensured: {cql.split('(')[1].split(')')[0]}")
    logger.info(f"All {len(indexes)} indexes created/verified.")


async def seed_skill_categories(driver):
    categories = [
        "编程语言", "前端开发", "后端开发", "数据库",
        "云原生", "AI/机器学习", "数据工程", "DevOps",
        "安全", "移动开发", "测试", "项目管理",
    ]
    async with driver.session() as session:
        for cat in categories:
            await session.run(
                "MERGE (k:KnowledgeArea {name: $name}) RETURN k",
                name=cat,
            )
            logger.debug(f"KnowledgeArea seeded: {cat}")
    logger.info(f"Seeded {len(categories)} KnowledgeArea nodes.")


async def load_seed_positions(driver):
    positions = [
        {
            "name": "前端开发工程师",
            "industry": "互联网",
            "description": "负责Web前端架构设计与开发，构建高性能用户界面。",
            "required_skills": ["React", "TypeScript", "JavaScript", "HTML5", "CSS3"],
        },
        {
            "name": "后端开发工程师",
            "industry": "互联网",
            "description": "负责服务端架构设计与API开发，保障系统高可用。",
            "required_skills": ["Python", "Java", "Go", "PostgreSQL", "Redis"],
        },
        {
            "name": "AI算法工程师",
            "industry": "人工智能",
            "description": "负责机器学习模型研发与落地，包括NLP/CV方向。",
            "required_skills": ["Python", "PyTorch", "scikit-learn", "RAG", "LLM Deployment"],
        },
        {
            "name": "数据分析师",
            "industry": "数据服务",
            "description": "负责业务数据分析与可视化，驱动数据化决策。",
            "required_skills": ["SQL", "Python", "Pandas", "NumPy", "Tableau"],
        },
        {
            "name": "DevOps工程师",
            "industry": "云服务",
            "description": "负责CI/CD流水线、容器化与云基础设施运维。",
            "required_skills": ["Docker", "Kubernetes", "Terraform", "CI/CD", "Prometheus"],
        },
        {
            "name": "安全工程师",
            "industry": "网络安全",
            "description": "负责安全架构设计、渗透测试与安全运营。",
            "required_skills": ["Python", "Penetration Testing", "SIEM", "Kubernetes", "Cloud Security"],
        },
    ]
    async with driver.session() as session:
        for pos in positions:
            result = await session.run(
                "MERGE (p:Position {name: $name, industry: $industry, description: $description}) RETURN p",
                name=pos["name"],
                industry=pos["industry"],
                description=pos["description"],
            )
            record = await result.single()
            if record:
                logger.debug(f"Position seeded: {pos['name']}")
            for skill_name in pos["required_skills"]:
                await session.run(
                    (
                        "MATCH (p:Position {name: $pos_name}) "
                        "MERGE (s:Skill {name: $skill_name}) "
                        "MERGE (p)-[:REQUIRES]->(s)"
                    ),
                    pos_name=pos["name"],
                    skill_name=skill_name,
                )
                logger.debug(f"REQUIRES: {pos['name']} -> {skill_name}")
    logger.info(f"Seeded {len(positions)} positions with REQUIRES relationships.")


async def main():
    neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "starmap123456")

    logger.info(f"Connecting to Neo4j: {neo4j_uri}")
    async with AsyncGraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password)) as driver:
        await driver.verify_connectivity()
        logger.info("Connected to Neo4j successfully.")

        await create_constraints(driver)
        await create_indexes(driver)
        await seed_skill_categories(driver)
        await load_seed_positions(driver)

    logger.info("Neo4j schema initialization complete.")
    print("Summary:")
    print("  7 uniqueness constraints created/verified")
    print("  4 indexes created/verified")
    print("  12 KnowledgeArea nodes seeded")
    print("  6 seed positions loaded with REQUIRES relationships")


if __name__ == "__main__":
    asyncio.run(main())
