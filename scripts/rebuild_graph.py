"""全量回填 Neo4j Position 节点缺失属性 — 以 PG position_records 为权威源。

运行方式:
    cd backend && poetry run python ../scripts/rebuild_graph.py

功能:
    1. 从 PG position_records 读取全部岗位
    2. 按 name 匹配 Neo4j Position 节点
    3. 回填缺失属性: position_id, industry, description, review_status, discovered_at
    4. 幂等 — 可安全重复运行

    注意：仅更新现有 Position 节点属性，不创建/删除节点或关系。
"""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

# 确保 backend/ 可导入
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "backend"))

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session_factory
from app.models.extraction_models import PositionRecord
from app.services.resources import init_resources

BATCH_SIZE = 50


async def main() -> None:
    print("═" * 60)
    print("Neo4j Position 节点属性回填")
    print("═" * 60)

    # 初始化资源
    resources = await init_resources()
    neo4j_driver = resources.neo4j_driver
    session_factory = get_session_factory()

    if neo4j_driver is None:
        print("[FAIL] Neo4j driver 未初始化，请检查 Docker 容器是否运行")
        return

    # 1. 从 PG 读取全部 position_records
    print("\n[1/3] 从 PostgreSQL 读取 position_records...")
    async with session_factory() as session:
        result = await session.execute(select(PositionRecord).order_by(PositionRecord.name))
        pg_positions = result.scalars().all()

    print(f"  → 读取到 {len(pg_positions)} 条 PG 记录")

    # 2. 构建回填数据
    updates: list[dict] = []
    for pos in pg_positions:
        updates.append({
            "name": pos.name,
            "position_id": str(pos.id),
            "industry": pos.industry or "",
            "description": pos.description or "",
            "review_status": pos.review_status or "pending_review",
            "discovered_at": pos.created_at.isoformat() if pos.created_at else datetime.now(timezone.utc).isoformat(),
            "name_cn": getattr(pos, "name_cn", "") or "",
        })

    print(f"  → 准备回填 {len(updates)} 个 Position 节点")

    # 3. 批量写入 Neo4j
    print("\n[2/3] 回填 Neo4j Position 节点...")
    updated = 0
    not_found = 0
    total = len(updates)

    cypher = """
    MATCH (p:Position {name: $name})
    SET p.position_id = $position_id,
        p.industry = $industry,
        p.description = $description,
        p.review_status = $review_status,
        p.discovered_at = $discovered_at,
        p.name_cn = $name_cn,
        p.updated_at = datetime()
    RETURN p.name AS name
    """

    for i in range(0, total, BATCH_SIZE):
        batch = updates[i : i + BATCH_SIZE]
        async with neo4j_driver.session() as neo_session:
            for item in batch:
                try:
                    result = await neo_session.run(cypher, **item)
                    record = await result.single()
                    if record:
                        updated += 1
                    else:
                        not_found += 1
                        if not_found <= 10:  # 仅打印前 10 条
                            print(f"  [WARN] Neo4j 中未找到: {item['name']}")
                except Exception as exc:
                    print(f"  [ERROR] {item['name']}: {exc}")

        progress = min(i + BATCH_SIZE, total)
        print(f"  → 进度: {progress}/{total} ({updated} 已更新, {not_found} 未找到)")

    # 4. 验证
    print(f"\n[3/3] 验证回填结果...")
    verify_cypher = """
    MATCH (p:Position)
    RETURN
        count(p) AS total,
        count(p.position_id) AS has_position_id,
        count(p.industry) AS has_industry,
        count(p.description) AS has_description,
        count(p.review_status) AS has_review_status
    """
    async with neo4j_driver.session() as neo_session:
        result = await neo_session.run(verify_cypher)
        record = await result.single()
        if record:
            print(f"  → Neo4j Position 节点: {record['total']}")
            print(f"  → 有 position_id: {record['has_position_id']}/{record['total']}")
            print(f"  → 有 industry:    {record['has_industry']}/{record['total']}")
            print(f"  → 有 description:  {record['has_description']}/{record['total']}")
            print(f"  → 有 review_status: {record['has_review_status']}/{record['total']}")

    print(f"\n{'═' * 60}")
    print(f"回填完成: {updated} 已更新, {not_found} 未在 Neo4j 找到")
    print(f"PG 共 {total} 条, Neo4j 共 {record['total'] if record else '?'} 个 Position 节点")
    print(f"{'═' * 60}")

    await resources.close()


if __name__ == "__main__":
    asyncio.run(main())
