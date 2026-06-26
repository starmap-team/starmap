"""从 jd_extraction_records 导出三元组，配合 R2 graph_writer 入图。

Issue #36 — 阶段3 配合 R2 实现图谱构建服务。

用法:
    python -m crawler.scripts.export_triples                    # 导出全部
    python -m crawler.scripts.export_triples --limit 50         # 导出最新 50 条
    python -m crawler.scripts.export_triples --output triples.json
    python -m crawler.scripts.export_triples --format cypher    # 输出 Cypher 语句
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from crawler.persistence.database import get_jd_raw_session  # noqa: E402
from sqlalchemy import text  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("export_triples")


def _skill_name(entry: Any) -> str:
    if isinstance(entry, dict):
        return str(entry.get("name") or entry.get("skill") or "").strip()
    return str(entry).strip()


def _skill_category(entry: Any) -> str:
    if isinstance(entry, dict):
        return str(entry.get("category") or "general")
    return "general"


def fetch_extraction_records(limit: int = 0) -> list[dict]:
    """从 jd_extraction_records 读取已完成的提取记录。"""
    with get_jd_raw_session() as s:
        q = text(
            "SELECT id, job_title, extracted_skills, experience_years, education, "
            "confidence, status FROM jd_extraction_records WHERE status = 'completed' "
            "ORDER BY created_at DESC"
        )
        if limit > 0:
            q = text(
                "SELECT id, job_title, extracted_skills, experience_years, education, "
                "confidence, status FROM jd_extraction_records WHERE status = 'completed' "
                "ORDER BY created_at DESC LIMIT :lim"
            )
            rows = s.execute(q, {"lim": limit}).fetchall()
        else:
            rows = s.execute(q).fetchall()

    records = []
    for row in rows:
        records.append({
            "id": str(row[0]),
            "job_title": row[1],
            "extracted_skills": row[2] if isinstance(row[2], dict) else {},
            "experience_years": row[3],
            "education": row[4],
            "confidence": float(row[5]) if row[5] else 0.0,
            "status": row[6],
        })
    return records


def extract_triples(records: list[dict]) -> list[dict]:
    """从提取记录生成三元组列表。

    三元组格式: {source, relationship, target, properties}
    关系类型: REQUIRES (必须技能), PREFERS (偏好技能), USES (工具)
    """
    triples: list[dict] = []
    seen: set[tuple] = set()

    for rec in records:
        position = rec["job_title"]
        if not position:
            continue
        skills = rec.get("extracted_skills", {})
        confidence = rec.get("confidence", 0.85)

        # Position -> required Skills (REQUIRES)
        for entry in skills.get("required_skills", []):
            name = _skill_name(entry)
            if not name:
                continue
            key = (position, "REQUIRES", name)
            if key in seen:
                continue
            seen.add(key)
            triples.append({
                "source": {"label": "Position", "name": position},
                "relationship": "REQUIRES",
                "target": {"label": "Skill", "name": name},
                "properties": {
                    "required": True,
                    "level": entry.get("level", "intermediate") if isinstance(entry, dict) else "intermediate",
                    "confidence": confidence,
                    "category": _skill_category(entry),
                },
            })

        # Position -> preferred Skills (REQUIRES, required=False)
        for entry in skills.get("preferred_skills", []):
            name = _skill_name(entry)
            if not name:
                continue
            key = (position, "REQUIRES", name)
            if key in seen:
                continue
            seen.add(key)
            triples.append({
                "source": {"label": "Position", "name": position},
                "relationship": "REQUIRES",
                "target": {"label": "Skill", "name": name},
                "properties": {
                    "required": False,
                    "level": entry.get("level", "intermediate") if isinstance(entry, dict) else "intermediate",
                    "confidence": confidence,
                    "category": _skill_category(entry),
                },
            })

        # Position -> Tools (USES)
        for entry in skills.get("tools", []):
            name = _skill_name(entry)
            if not name:
                continue
            key = (position, "USES", name)
            if key in seen:
                continue
            seen.add(key)
            triples.append({
                "source": {"label": "Position", "name": position},
                "relationship": "USES",
                "target": {"label": "Tool", "name": name},
                "properties": {"confidence": confidence},
            })

    log.info("从 %d 条记录生成 %d 个三元组", len(records), len(triples))
    return triples


def triples_to_cypher(triples: list[dict]) -> list[str]:
    """将三元组转为 Neo4j Cypher MERGE 语句。"""
    statements: list[str] = []
    for t in triples:
        src_label = t["source"]["label"]
        src_name = t["source"]["name"].replace("'", "\\'")
        rel = t["relationship"]
        tgt_label = t["target"]["label"]
        tgt_name = t["target"]["name"].replace("'", "\\'")

        props = t.get("properties", {})
        prop_parts = []
        for k, v in props.items():
            if isinstance(v, bool):
                prop_parts.append(f"{k}: {'true' if v else 'false'}")
            elif isinstance(v, (int, float)):
                prop_parts.append(f"{k}: {v}")
            else:
                prop_parts.append(f"{k}: '{str(v).replace(chr(39), chr(92) + chr(39))}'")
        prop_str = ", ".join(prop_parts)
        if prop_str:
            prop_str = " {" + prop_str + "}"

        stmt = (
            f"MERGE (s:{src_label} {{name: '{src_name}'}}) "
            f"MERGE (t:{tgt_label} {{name: '{tgt_name}'}}) "
            f"MERGE (s)-[r:{rel}]->(t) "
            f"SET r += {prop_str if prop_str else '{}'};"
        )
        statements.append(stmt)
    return statements


def main() -> None:
    p = argparse.ArgumentParser(prog="export_triples", description="导出三元组数据")
    p.add_argument("--limit", type=int, default=0, help="限制条数（0=全部）")
    p.add_argument("--output", "-o", type=str, default="", help="输出文件路径")
    p.add_argument("--format", "-f", choices=["json", "cypher"], default="json", help="输出格式")
    args = p.parse_args()

    records = fetch_extraction_records(limit=args.limit)
    log.info("读取到 %d 条提取记录", len(records))

    triples = extract_triples(records)

    if args.format == "cypher":
        output = triples_to_cypher(triples)
        text_out = "\n".join(output)
    else:
        text_out = json.dumps(triples, ensure_ascii=False, indent=2)

    if args.output:
        Path(args.output).write_text(text_out, encoding="utf-8")
        log.info("已写入 %s (%d 个三元组)", args.output, len(triples))
    else:
        print(text_out)

    # 统计
    positions = {t["source"]["name"] for t in triples if t["source"]["label"] == "Position"}
    skills = {t["target"]["name"] for t in triples if t["target"]["label"] == "Skill"}
    tools = {t["target"]["name"] for t in triples if t["target"]["label"] == "Tool"}
    log.info("统计: %d 岗位, %d 技能, %d 工具, %d 三元组", len(positions), len(skills), len(tools), len(triples))


if __name__ == "__main__":
    main()
