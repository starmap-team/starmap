"""D5 (2026-08-12): REQUIRES 边投影 —— Neo4j REQUIRES pairs 与 PG position_skill_relations 对齐。

孤儿图节点合并后，迁移的 REQUIRES 边落在 canonical 节点上；此脚本把 Neo4j 有而 PG 无的
(position_id, skill_id) 对写入 position_skill_relations（requirement_type='required',
confidence=0.6 —— 遗留图数据无置信度标注，取"可用但未验证"中性默认，审计见
docs/archive/pg-neo4j-database-audit.md）。
"""
from __future__ import annotations

import asyncio
import csv
import sys

from sqlalchemy import text

from app.db.session import get_session_factory

REQUIRED_CONFIDENCE = 0.6
PAIRS_PATH = sys.argv[1] if len(sys.argv) > 1 else "/tmp/neo4j_requires_pairs.tsv"


async def main() -> None:
    pairs: set[tuple[str, str]] = set()
    with open(PAIRS_PATH, encoding="utf-8") as fh:
        for row in csv.reader(fh, skipinitialspace=True):
            if len(row) == 2 and row[0] and row[1]:
                pairs.add((row[0].strip().strip('"'), row[1].strip().strip('"')))
    print(f"Neo4j REQUIRES pairs: {len(pairs)}")

    factory = get_session_factory()
    async with factory() as session:
        existing = set(
            (str(p), str(s))
            for p, s in (await session.execute(text(
                "SELECT position_id, skill_id FROM position_skill_relations"
            ))).all()
        )
        print(f"PG existing relations: {len(existing)}")

        missing = sorted(pairs - existing)
        print(f"Missing (to insert): {len(missing)}")

        for pid, sid in missing:
            await session.execute(text(
                "INSERT INTO position_skill_relations (position_id, skill_id, requirement_type, confidence) "
                "VALUES (:pid, :sid, 'required', :conf)"
            ), {"pid": pid, "sid": sid, "conf": REQUIRED_CONFIDENCE})
        await session.commit()

        # 验证
        after = set(
            (str(p), str(s))
            for p, s in (await session.execute(text(
                "SELECT position_id, skill_id FROM position_skill_relations"
            ))).all()
        )
        print(f"PG after: {len(after)}; Neo4j covered: {len(pairs & after)}")


if __name__ == "__main__":
    asyncio.run(main())
