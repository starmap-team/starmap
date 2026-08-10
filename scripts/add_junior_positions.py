"""Add junior-level positions to Neo4j to ensure the level view shows all 3 tiers.

Adds synthetic junior positions covering common entry-level roles that map to
existing skills. Run after fix_graph_data.py if the level view lacks 初级.
"""
import asyncio
import os

from loguru import logger
from neo4j import AsyncGraphDatabase

# Junior positions to ensure - mapped to common entry-level skills
JUNIOR_POSITIONS = [
    {
        "name": "Junior Frontend Developer",
        "industry": "信息技术/互联网",
        "description": "入门级前端开发岗位，在资深工程师指导下完成页面开发。",
        "skills": ["HTML5", "CSS3", "JavaScript", "React", "Git"],
    },
    {
        "name": "Junior Backend Developer",
        "industry": "信息技术/互联网",
        "description": "入门级后端开发岗位，参与 API 设计与实现。",
        "skills": ["Python", "SQL", "REST API", "Git", "Linux"],
    },
    {
        "name": "Junior Data Analyst",
        "industry": "信息技术/互联网",
        "description": "入门级数据分析师，协助完成数据整理与可视化。",
        "skills": ["SQL", "Excel", "Python", "Pandas", "Tableau"],
    },
    {
        "name": "Junior QA Engineer",
        "industry": "信息技术/互联网",
        "description": "入门级 QA 工程师，执行测试用例并报告缺陷。",
        "skills": ["Test Cases", "Bug Tracking", "Selenium", "Jira", "Git"],
    },
    {
        "name": "Junior DevOps Engineer",
        "industry": "信息技术/互联网",
        "description": "入门级 DevOps 工程师，协助维护 CI/CD 流水线。",
        "skills": ["Linux", "Docker", "Bash", "Git", "Jenkins"],
    },
    {
        "name": "Intern Software Engineer",
        "industry": "信息技术/互联网",
        "description": "实习级软件工程师，参与项目开发与学习。",
        "skills": ["Git", "JavaScript", "Python", "HTML5", "CSS3"],
    },
]


async def main():
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    pw = os.getenv("NEO4J_PASSWORD", "")

    logger.info(f"Connecting to {uri}...")
    driver = AsyncGraphDatabase.driver(uri, auth=(user, pw))
    try:
        await driver.verify_connectivity()
        async with driver.session() as session:
            created = 0
            for pos in JUNIOR_POSITIONS:
                await session.run(
                    """
                    MERGE (p:Position {name: $name})
                    SET p.industry = $industry,
                        p.description = $description,
                        p.level = '初级',
                        p.source = 'junior_seed'
                    """,
                    name=pos["name"],
                    industry=pos["industry"],
                    description=pos["description"],
                )
                for skill_name in pos["skills"]:
                    await session.run(
                        """
                        MATCH (p:Position {name: $pos_name})
                        MERGE (s:Skill {name: $skill_name})
                        MERGE (p)-[r:REQUIRES]->(s)
                        SET r.required = true, r.weight = 0.7
                        """,
                        pos_name=pos["name"],
                        skill_name=skill_name,
                    )
                created += 1
                logger.info(f"  + Junior: {pos['name']}")
            logger.info(f"Created/updated {created} junior positions")
    finally:
        await driver.close()


if __name__ == "__main__":
    asyncio.run(main())
