"""图谱数据完整性验证脚本 (M4-A)。

检查 Neo4j 图谱中的岗位、技能、PREREQUISITE 关系的覆盖率和完整性。

用法：
    python scripts/validate_graph_data.py [--neo4j-uri bolt://localhost:7687]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

# 将项目根目录加入 sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from neo4j import AsyncGraphDatabase


async def validate(uri: str, user: str, password: str) -> dict:
    """运行图谱数据完整性验证。"""
    driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
    report: dict = {}

    async with driver.session() as session:
        # 1. 节点计数
        for label in ["Position", "Skill", "KnowledgeArea", "Tool", "Certificate", "LearningResource", "Industry"]:
            result = await session.run(f"MATCH (n:{label}) RETURN count(n) AS cnt")
            record = await result.single()
            report[f"count_{label}"] = record["cnt"] if record else 0

        # 2. 关系计数
        for rel in ["REQUIRES", "PREREQUISITE", "EVOLVES_TO", "USES", "BELONGS_TO", "RECOMMENDED_FOR", "CERTIFIES"]:
            result = await session.run(f"MATCH ()-[r:{rel}]->() RETURN count(r) AS cnt")
            record = await result.single()
            report[f"count_{rel}"] = record["cnt"] if record else 0

        # 3. 岗位有效覆盖率（有≥3个required_skills的岗位）
        result = await session.run("""
            MATCH (p:Position)-[r:REQUIRES]->(s:Skill)
            WITH p, count(s) AS skill_count
            RETURN count(CASE WHEN skill_count >= 3 THEN 1 END) AS covered,
                   count(CASE WHEN skill_count >= 5 THEN 1 END) AS well_covered,
                   count(p) AS total
        """)
        record = await result.single()
        if record:
            total = record["total"]
            covered = record["covered"]
            well_covered = record["well_covered"]
            report["position_total"] = total
            report["positions_with_3plus_skills"] = covered
            report["positions_with_5plus_skills"] = well_covered
            report["position_coverage_ratio_3"] = round(covered / total, 4) if total else 0.0
            report["position_coverage_ratio_5"] = round(well_covered / total, 4) if total else 0.0

        # 4. 技能可信度（source_count≥3的技能）
        result = await session.run("""
            MATCH (s:Skill)
            RETURN count(CASE WHEN s.source_count >= 3 THEN 1 END) AS trusted,
                   count(s) AS total
        """)
        record = await result.single()
        if record:
            total = record["total"]
            trusted = record["trusted"]
            report["skill_total"] = total
            report["skills_with_3plus_sources"] = trusted
            report["skill_trust_ratio"] = round(trusted / total, 4) if total else 0.0

        # 5. PREREQUISITE 关系覆盖率
        result = await session.run("""
            MATCH (s:Skill)
            OPTIONAL MATCH (s)<-[:PREREQUISITE]-(dependent)
            WITH s, count(dependent) AS dependents
            RETURN count(CASE WHEN dependents > 0 THEN 1 END) AS has_prerequisites,
                   count(s) AS total
        """)
        record = await result.single()
        if record:
            total = record["total"]
            has_prereq = record["has_prerequisites"]
            report["skills_with_prerequisites"] = has_prereq
            report["prerequisite_coverage_ratio"] = round(has_prereq / total, 4) if total else 0.0

        # 6. LearningResource 节点和 RECOMMENDED_FOR 关系
        result = await session.run("""
            MATCH (lr:LearningResource)
            OPTIONAL MATCH (lr)-[:RECOMMENDED_FOR]->(s:Skill)
            RETURN count(lr) AS total_resources,
                   count(DISTINCT s) AS covered_skills
        """)
        record = await result.single()
        if record:
            report["learning_resources_total"] = record["total_resources"]
            report["learning_resources_covered_skills"] = record["covered_skills"]

        # 7. 无技能的岗位列表（需要补充数据）
        result = await session.run("""
            MATCH (p:Position)
            WHERE NOT (p)-[:REQUIRES]->(:Skill)
            RETURN p.name AS name LIMIT 20
        """)
        records = await result.data()
        report["positions_without_skills"] = [r["name"] for r in records]

    await driver.close()
    return report


async def main() -> None:
    parser = argparse.ArgumentParser(description="图谱数据完整性验证")
    parser.add_argument("--neo4j-uri", default="bolt://localhost:7687")
    parser.add_argument("--neo4j-user", default="neo4j")
    parser.add_argument("--neo4j-password", default="password")
    parser.add_argument("--output", default=None, help="输出JSON文件路径")
    args = parser.parse_args()

    print("🔍 开始图谱数据完整性验证...")
    report = await validate(args.neo4j_uri, args.neo4j_user, args.neo4j_password)

    # 输出报告
    print("\n" + "=" * 60)
    print("📊 图谱数据完整性报告")
    print("=" * 60)

    print(f"\n📌 节点数量:")
    for key in ["count_Position", "count_Skill", "count_KnowledgeArea", "count_Tool",
                 "count_Certificate", "count_LearningResource", "count_Industry"]:
        label = key.replace("count_", "")
        print(f"  {label}: {report.get(key, 0)}")

    print(f"\n📌 关系数量:")
    for key in ["count_REQUIRES", "count_PREREQUISITE", "count_EVOLVES_TO", "count_USES",
                 "count_BELONGS_TO", "count_RECOMMENDED_FOR", "count_CERTIFIES"]:
        label = key.replace("count_", "")
        print(f"  {label}: {report.get(key, 0)}")

    print(f"\n📌 岗位覆盖率:")
    print(f"  总岗位数: {report.get('position_total', 0)}")
    print(f"  ≥3技能: {report.get('positions_with_3plus_skills', 0)} ({report.get('position_coverage_ratio_3', 0):.1%})")
    print(f"  ≥5技能: {report.get('positions_with_5plus_skills', 0)} ({report.get('position_coverage_ratio_5', 0):.1%})")

    print(f"\n📌 技能可信度:")
    print(f"  总技能数: {report.get('skill_total', 0)}")
    print(f"  ≥3来源: {report.get('skills_with_3plus_sources', 0)} ({report.get('skill_trust_ratio', 0):.1%})")

    print(f"\n📌 PREREQUISITE 覆盖率:")
    print(f"  有前置知识的技能: {report.get('skills_with_prerequisites', 0)} ({report.get('prerequisite_coverage_ratio', 0):.1%})")

    print(f"\n📌 学习资源:")
    print(f"  LearningResource 节点: {report.get('learning_resources_total', 0)}")
    print(f"  覆盖技能数: {report.get('learning_resources_covered_skills', 0)}")

    if report.get("positions_without_skills"):
        print(f"\n⚠️ 无技能数据的岗位（前20个）:")
        for name in report["positions_without_skills"]:
            print(f"  - {name}")

    # 阈值评估
    print("\n" + "=" * 60)
    coverage = report.get("position_coverage_ratio_3", 0)
    trust = report.get("skill_trust_ratio", 0)
    if coverage >= 0.8:
        print("✅ 岗位覆盖率达标（≥80%）")
    elif coverage >= 0.3:
        print("⚠️ 岗位覆盖率中等（≥30%），可用于MVP")
    else:
        print("❌ 岗位覆盖率不足（<30%），建议优先补充数据")

    if args.output:
        Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2))
        print(f"\n📄 报告已保存到: {args.output}")


if __name__ == "__main__":
    asyncio.run(main())
