"""StarMap 数据治理：批量清理非岗位/非技能内容（可持续脚本，dry-run 默认）。

复用 job_content_guard 的判定（与抽取门禁同源，保证入库与存量口径一致）。
- 扫 pending_review 岗位/技能 → 判定为非内容 → 标 rejected（保留审计）+ 可选同步 Neo4j 清理。
- 默认 dry-run 只打印；`--apply` 才写库。

用法（容器内，cwd=/app）:
    python scripts/cleanup_non_job.py                     # dry-run：统计 + 样本
    python scripts/cleanup_non_job.py --apply             # 执行岗位清理
    python scripts/cleanup_non_job.py --apply --entity skill
    python scripts/cleanup_non_job.py --apply --purge-graph  # 同时 DETACH 图内被拒节点
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from sqlalchemy import text  # noqa: E402

from app.core.extraction.job_content_guard import is_skill_content, job_reject_reason  # noqa: E402
from app.services.resources import init_resources  # noqa: E402


async def _scan(engine, entity: str) -> list[tuple[str, str, str]]:
    """返回 (id, name, reject_reason) 待清理项。entity in {position, skill}。"""
    table = "position_records" if entity == "position" else "skill_records"
    async with engine.begin() as conn:
        rows = (
            await conn.exec_driver_sql(
                f"SELECT id, name FROM {table} WHERE review_status = 'pending_review'"
            )
        ).fetchall()
    out: list[tuple[str, str, str]] = []
    for row in rows:
        name = row[1]
        if entity == "position":
            reason = job_reject_reason(name, title=name)
        else:
            reason = None if is_skill_content(name) else "non-skill content (regulatory/document entry)"
        if reason:
            out.append((str(row[0]), name, reason))
    return out


async def _apply_pg(engine, entity: str, items: list[tuple[str, str, str]]) -> int:
    table = "position_records" if entity == "position" else "skill_records"
    reason_col = "rejection_reason" if entity == "position" else "rejection_reason"
    async with engine.begin() as conn:
        for entity_id, _name, reason in items:
            await conn.execute(
                text(
                    f"UPDATE {table} SET review_status = 'rejected', "
                    f"{reason_col} = :reason WHERE id = CAST(:id AS uuid)"
                ),
                {"reason": reason, "id": entity_id},
            )
    return len(items)


async def _purge_graph(driver, item_type: str, names: list[str]) -> int:
    """按名 DETACH 图内同名被拒节点（含 canonical_id 关联节点）。"""
    if not names:
        return 0
    label = "Position" if item_type == "position" else "Skill"
    purged = 0
    async with driver.session() as s:
        for name in names:
            result = await s.run(
                f"MATCH (n:{label} {{name: $name}}) DETACH DELETE n RETURN count(n) AS c",
                name=name,
            )
            rec = await result.single()
            purged += int(rec["c"]) if rec else 0
    return purged


async def _resync_approved(driver) -> None:
    """重投影 approved 岗位到图，保证被拒节点清除后图内 approved 完整。"""
    if driver is None:
        return
    from app.services.admin_audit_service import _sync_neo4j_on_audit

    async with init_resources().pg_engine.begin() as conn:
        rows = (
            await conn.exec_driver_sql(
                "SELECT name FROM position_records WHERE review_status = 'approved'"
            )
        ).fetchall()
    done = 0
    for r in rows:
        try:
            await _sync_neo4j_on_audit(driver, "position", r[0], "approved")
            done += 1
        except Exception:  # noqa: BLE001 — 单条失败不阻断
            pass
    print(f"[apply] 图内重投影 approved 岗位 {done} 个")


async def main() -> None:
    parser = argparse.ArgumentParser(description="StarMap 非岗位/非技能存量清理")
    parser.add_argument("--entity", choices=["position", "skill"], default="position")
    parser.add_argument("--apply", action="store_true", help="实际写库（默认 dry-run）")
    parser.add_argument("--purge-graph", action="store_true", help="同时 DETACH 图内被拒节点")
    parser.add_argument("--resync-approved", action="store_true", help="清理后重投影 approved 到图")
    args = parser.parse_args()

    res = await init_resources()
    items = await _scan(res.pg_engine, args.entity)
    print(f"[{'apply' if args.apply else 'dry-run'}] {args.entity}: {len(items)} 条将标记 rejected")
    for _id, name, reason in items[:15]:
        print(f"   - {name[:44]:44} | {reason[:34]}")

    if not args.apply:
        print("[dry-run] 预览完成（未写库）。加 --apply 执行。")
        return

    done = await _apply_pg(res.pg_engine, args.entity, items)
    print(f"[apply] PG 已标记 {done} 条 {args.entity} 为 rejected")

    if args.purge_graph and res.neo4j_driver:
        names = [it[1] for it in items]
        purged = await _purge_graph(res.neo4j_driver, args.entity, names)
        print(f"[apply] 图内已清除被拒 {args.entity} 节点 {purged} 个")

    if args.resync_approved and res.neo4j_driver:
        await _resync_approved(res.neo4j_driver)


if __name__ == "__main__":
    asyncio.run(main())
