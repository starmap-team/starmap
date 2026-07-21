"""Add Chinese display names (name_cn) to all Position nodes in Neo4j.

Maps English position names → Chinese equivalents for frontend display.
Run this once after positions are imported to enable Chinese-name rendering.
"""
import asyncio
import os

from neo4j import AsyncGraphDatabase
from loguru import logger

# English → Chinese position name mapping
POSITION_NAME_CN: dict[str, str] = {
    "AI Application Developer": "AI 应用开发工程师",
    "AI Research Scientist": "AI 研究科学家",
    "API Developer": "API 开发工程师",
    "Analytics Engineer": "分析工程师",
    "Android Developer": "Android 开发工程师",
    "Application Security Engineer": "应用安全工程师",
    "BI Developer": "BI 开发工程师",
    "Backend Architect": "后端架构师",
    "Backend Engineer": "后端工程师",
    "Blockchain Developer": "区块链开发工程师",
    "CTO": "首席技术官 (CTO)",
    "Cloud Engineer": "云平台工程师",
    "Cloud Security Engineer": "云安全工程师",
    "Computer Vision Engineer": "计算机视觉工程师",
    "Data Analyst": "数据分析师",
    "Data Engineer": "数据工程师",
    "Data Platform Engineer": "数据平台工程师",
    "Data Scientist": "数据科学家",
    "DevOps Engineer": "DevOps 工程师",
    "DevSecOps Engineer": "DevSecOps 工程师",
    "Embedded Software Engineer": "嵌入式软件工程师",
    "Engineering Manager": "工程经理",
    "Flutter Developer": "Flutter 开发工程师",
    "Frontend Architect": "前端架构师",
    "Frontend Engineer": "前端工程师",
    "Full Stack Engineer": "全栈工程师",
    "Game Developer": "游戏开发工程师",
    "Go Backend Developer": "Go 后端开发工程师",
    "Intern Software Engineer": "软件工程师实习生",
    "IoT Engineer": "物联网工程师",
    "Java Backend Developer": "Java 后端开发工程师",
    "Junior Backend Developer": "初级后端开发工程师",
    "Junior Data Analyst": "初级数据分析师",
    "Junior DevOps Engineer": "初级 DevOps 工程师",
    "Junior Frontend Developer": "初级前端开发工程师",
    "Junior QA Engineer": "初级测试工程师",
    "LLM Engineer": "大模型工程师",
    "MLOps Engineer": "MLOps 工程师",
    "Machine Learning Engineer": "机器学习工程师",
    "Mobile Tech Lead": "移动端技术负责人",
    "NLP Engineer": "自然语言处理工程师",
    "Next.js Developer": "Next.js 开发工程师",
    "Node.js Developer": "Node.js 开发工程师",
    "PHP Developer": "PHP 开发工程师",
    "Performance Test Engineer": "性能测试工程师",
    "Platform Engineer": "平台工程师",
    "QA Engineer": "测试工程师",
    "QA Lead": "测试负责人",
    "React Native Developer": "React Native 开发工程师",
    "Real-time Data Engineer": "实时数据工程师",
    "Recommendation Engineer": "推荐算法工程师",
    "Release Engineer": "发布工程师",
    "Rust Backend Developer": "Rust 后端开发工程师",
    "SDET": "测试开发工程师 (SDET)",
    "SRE": "站点可靠性工程师 (SRE)",
    "Security Engineer": "安全工程师",
    "Senior Backend Engineer": "高级后端工程师",
    "Senior Data Engineer": "高级数据工程师",
    "Senior DevOps Engineer": "高级 DevOps 工程师",
    "Senior Frontend Engineer": "高级前端工程师",
    "Senior ML Engineer": "高级机器学习工程师",
    "Senior QA Engineer": "高级测试工程师",
    "Svelte Developer": "Svelte 开发工程师",
    "Tech Lead": "技术负责人",
    "UI Engineer": "UI 工程师",
    "VP of Engineering": "工程副总裁",
    "Vue.js Developer": "Vue.js 开发工程师",
    "WebGL Developer": "WebGL 开发工程师",
    "iOS Developer": "iOS 开发工程师",
    # Already Chinese
    "高级后端工程师": "高级后端工程师",
}


async def main():
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    pw = os.getenv("NEO4J_PASSWORD", "starmap123456")

    logger.info(f"Connecting to {uri}...")
    driver = AsyncGraphDatabase.driver(uri, auth=(user, pw))
    try:
        await driver.verify_connectivity()
        async with driver.session() as session:
            updated = 0
            for en_name, cn_name in POSITION_NAME_CN.items():
                result = await session.run(
                    "MATCH (p:Position {name: $en}) SET p.name_cn = $cn RETURN p.name",
                    en=en_name, cn=cn_name,
                )
                if await result.single():
                    updated += 1
            logger.info(f"  Updated name_cn for {updated} / {len(POSITION_NAME_CN)} positions")

            # Verify
            verify = await session.run(
                "MATCH (p:Position) WHERE p.name_cn IS NOT NULL RETURN count(p) AS cnt"
            )
            record = await verify.single()
            logger.info(f"  Verification: {record['cnt'] if record else 0} positions have name_cn")
    finally:
        await driver.close()


if __name__ == "__main__":
    asyncio.run(main())
