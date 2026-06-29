"""Seed Neo4j demo properties for positions, skills, and REQUIRES relations.

This script enriches existing graph nodes with additional demo metadata:
- Position: industry, level
- Skill: trend (rising/stable/declining)
- REQUIRES: importance (required/bonus)

Requires environment variables or defaults used by the project:
- NEO4J_URI (default: bolt://neo4j:7687)
- NEO4J_USER (default: neo4j)
- NEO4J_PASSWORD (default: starmap123456)

Usage:
  cd starmap
  python scripts/seed_demo_data.py
"""
from __future__ import annotations

import asyncio
import os

from neo4j import AsyncGraphDatabase

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "starmap123456")

POSITION_UPDATES: list[dict[str, str]] = [
    {"name": "后端工程师", "industry": "互联网", "level": "中级"},
    {"name": "高级后端工程师", "level": "高级"},
    {"name": "前端开发工程师", "industry": "互联网", "level": "中级"},
    {"name": "高级前端开发工程师", "level": "高级"},
    {"name": "AI工程师", "industry": "人工智能", "level": "中级"},
    {"name": "大模型应用工程师", "industry": "人工智能", "level": "中级"},
    {"name": "数据分析师", "industry": "数据服务", "level": "初级"},
    {"name": "数据工程师", "industry": "数据服务", "level": "中级"},
    {"name": "DevOps工程师", "industry": "云服务", "level": "中级"},
    {"name": "安全工程师", "industry": "网络安全", "level": "中级"},
    {"name": "前端工程师", "industry": "互联网", "level": "中级"},
    {"name": "AI算法工程师", "industry": "人工智能", "level": "高级"},
]

SKILL_TRENDS: dict[str, str] = {
    "Python": "stable", "Java": "stable", "JavaScript": "stable",
    "TypeScript": "rising", "Go": "rising", "Rust": "rising",
    "Kotlin": "stable", "Swift": "stable", "SQL": "stable",
    "Shell Script": "stable", "React": "stable", "Vue.js": "stable",
    "HTML5": "stable", "CSS3": "stable", "Node.js": "stable",
    "FastAPI": "rising", "Docker": "stable", "Kubernetes": "stable",
    "PostgreSQL": "stable", "Redis": "stable", "Git": "stable",
    "Linux": "stable", "PyTorch": "rising", "TensorFlow": "declining",
    "Hugging Face": "rising", "LangChain": "rising", "RAG": "rising",
    "Prompt Engineering": "rising", "Elasticsearch": "stable",
    "Kafka": "stable", "Spark": "stable", "Airflow": "stable",
    "Terraform": "stable", "Ansible": "stable", "Prometheus": "stable",
    "Grafana": "stable", "Figma": "stable", "scikit-learn": "stable",
    "AWS": "stable", "MongoDB": "stable", "Flink": "rising",
    "ClickHouse": "rising", "CI/CD": "stable", "REST API": "stable",
    "Tableau": "stable", "Excel": "declining", "统计学": "stable",
    "Machine Learning": "rising", "Penetration Testing": "stable",
    "SIEM": "stable", "Cloud Security": "rising", "Fine-tuning": "rising",
    "Microservices": "stable", "System Design": "rising",
    "NumPy": "stable", "Pandas": "stable", "Webpack": "declining",
    "Vite": "rising", "Pinia": "stable", "Nuxt.js": "stable",
    "Next.js": "stable", "Tailwind CSS": "rising", "GraphQL": "stable",
    "Element Plus": "stable", "Spring Boot": "stable", "MyBatis": "stable",
    "Django": "stable", "MySQL": "stable", "C++": "stable", "C#": "stable",
}

REQUIRED_POSITION_SKILLS: dict[str, list[str]] = {
    "后端工程师": ["Python", "FastAPI", "PostgreSQL", "Redis", "Docker", "REST API"],
    "高级后端工程师": ["Python", "FastAPI", "PostgreSQL", "Redis", "Docker", "System Design", "Kubernetes"],
    "前端开发工程师": ["JavaScript", "Vue.js", "HTML5", "CSS3", "TypeScript"],
    "高级前端开发工程师": ["JavaScript", "React", "TypeScript", "HTML5", "CSS3", "Webpack", "Node.js"],
    "数据分析师": ["Python", "SQL", "Pandas", "Excel", "统计学"],
    "数据工程师": ["Spark", "Flink", "Airflow", "Kafka", "ClickHouse", "SQL", "Python"],
    "AI工程师": ["Python", "PyTorch", "scikit-learn", "TensorFlow", "Linux", "Git"],
    "大模型应用工程师": ["Python", "LLM", "RAG", "LangChain", "Prompt Engineering", "FastAPI"],
    "DevOps工程师": ["Docker", "Kubernetes", "Terraform", "Ansible", "Prometheus", "Grafana", "CI/CD"],
    "安全工程师": ["Python", "Penetration Testing", "SIEM", "Kubernetes", "Cloud Security"],
    "前端工程师": ["JavaScript", "Vue.js", "HTML5", "CSS3"],
    "AI算法工程师": ["Python", "PyTorch", "TensorFlow", "Hugging Face", "RAG"],
}

BONUS_POSITION_SKILLS: dict[str, list[str]] = {
    "后端工程师": ["Kubernetes", "Microservices"],
    "高级后端工程师": ["Apache Kafka", "Microservices"],
    "前端开发工程师": ["Node.js", "Webpack"],
    "高级前端开发工程师": ["Next.js", "Tailwind CSS", "GraphQL"],
    "数据分析师": ["Tableau", "Machine Learning"],
    "数据工程师": ["Hive", "AWS"],
    "AI工程师": ["Hugging Face", "Docker"],
    "大模型应用工程师": ["Fine-tuning", "Docker"],
    "DevOps工程师": ["Linux", "AWS"],
    "安全工程师": ["Linux", "Docker"],
    "前端工程师": ["Node.js", "Webpack"],
    "AI算法工程师": ["RAG", "LangChain"],
}


async def update_position_properties(driver) -> int:
    """Set industry and level on Position nodes."""
    updated = 0
    async with driver.session() as session:
        for pos in POSITION_UPDATES:
            set_parts: list[str] = []
            params: dict[str, str] = {"name": pos["name"]}
            if "industry" in pos:
                set_parts.append("p.industry = $industry")
                params["industry"] = pos["industry"]
            if "level" in pos:
                set_parts.append("p.level = $level")
                params["level"] = pos["level"]
            if not set_parts:
                continue
            query = (
                "MATCH (p:Position {name: $name}) "
                "SET " + ", ".join(set_parts) + " "
                "RETURN p.name AS name"
            )
            result = await session.run(query, **params)
            record = await result.single()
            if record:
                updated += 1
    return updated


async def update_skill_trends(driver) -> int:
    """Set trend property on Skill nodes."""
    updated = 0
    async with driver.session() as session:
        for skill_name, trend in SKILL_TRENDS.items():
            result = await session.run(
                "MATCH (s:Skill {name: $name}) SET s.trend = $trend RETURN s.name AS name",
                name=skill_name, trend=trend,
            )
            record = await result.single()
            if record:
                updated += 1
    return updated


async def update_requires_importance(driver) -> int:
    """Set importance property on REQUIRES relationships."""
    updated = 0
    async with driver.session() as session:
        for position_name, skills in REQUIRED_POSITION_SKILLS.items():
            for skill_name in skills:
                result = await session.run(
                    "MATCH (p:Position {name: $position})-[r:REQUIRES]->(s:Skill {name: $skill}) "
                    "SET r.importance = 'required' "
                    "RETURN count(r) AS updated",
                    position=position_name, skill=skill_name,
                )
                record = await result.single()
                if record and record["updated"]:
                    updated += record["updated"]

        for position_name, skills in BONUS_POSITION_SKILLS.items():
            for skill_name in skills:
                result = await session.run(
                    "MATCH (p:Position {name: $position})-[r:REQUIRES]->(s:Skill {name: $skill}) "
                    "SET r.importance = 'bonus' "
                    "RETURN count(r) AS updated",
                    position=position_name, skill=skill_name,
                )
                record = await result.single()
                if record and record["updated"]:
                    updated += record["updated"]
    return updated


async def main() -> None:
    print(f"Connecting to Neo4j: {NEO4J_URI}")
    async with AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)) as driver:
        await driver.verify_connectivity()
        print("Connected.")

        pos_count = await update_position_properties(driver)
        print(f"Position properties updated: {pos_count}")

        skill_count = await update_skill_trends(driver)
        print(f"Skill trends updated: {skill_count}")

        rel_count = await update_requires_importance(driver)
        print(f"REQUIRES importance updated: {rel_count}")


if __name__ == "__main__":
    asyncio.run(main())