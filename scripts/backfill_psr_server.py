"""StarMap 公网服务器 PSR 数据回填 — 从 jd_extraction_records 恢复技能关系。

在服务器上执行(容器内):
  docker exec -it starmap-backend-prod python /opt/starmap/backfill_psr.py

逻辑:
  1. 找到所有"已审核(approved)但无技能关系"的岗位
  2. 从 jd_extraction_records 表读取该岗位最近一次抽取结果
  3. 把 extracted_skills 里的技能名关联到 skill_records,写入 position_skill_relations
  4. 幂等: 已存在关系跳过
"""
import asyncio
import sys

sys.path.insert(0, "/app")

from sqlalchemy import select, text  # noqa: E402
from sqlalchemy.dialects.postgresql import insert as pg_insert  # noqa: E402

from app.db.session import get_session_factory  # noqa: E402


async def main():
    sf = get_session_factory()
    async with sf() as session:
        # 1. 找 approved 但无关系的岗位
        rows = await session.execute(text("""
            SELECT pr.id, pr.name
            FROM position_records pr
            WHERE pr.review_status = 'approved'
              AND NOT EXISTS (SELECT 1 FROM position_skill_relations psr WHERE psr.position_id = pr.id)
        """))
        positions = [(r.id, r.name) for r in rows]
        print(f"无关系岗位: {len(positions)}")

        if not positions:
            print("无需回填")
            return

        # 2. 批量读抽取记录
        inserted = 0
        for pid, name in positions:
            rec = await session.execute(text("""
                SELECT extracted_skills FROM jd_extraction_records
                WHERE job_title = :name AND status = 'completed'
                ORDER BY created_at DESC LIMIT 1
            """), {"name": name})
            rec_row = rec.first()
            if not rec_row or not rec_row[0]:
                continue

            raw = rec_row[0]
            skills = []
            if isinstance(raw, list):
                for s in raw:
                    if isinstance(s, dict):
                        skills.append(s.get("skill") or s.get("name") or "")
                    elif isinstance(s, str):
                        skills.append(s)
            elif isinstance(raw, dict):
                skills = raw.get("required_skills", []) if isinstance(raw.get("required_skills"), list) else []

            skills = [s for s in skills if s and isinstance(s, str)]
            if not skills:
                continue

            # 3. 按技能名查 skill_records
            sk_rows = await session.execute(text("""
                SELECT id, name FROM skill_records WHERE name = ANY(:names)
            """), {"names": skills})
            skill_ids = [(r.id, r.name) for r in sk_rows]

            # 4. 写 PSR(幂等)
            for sid, _ in skill_ids:
                exists = await session.execute(text("""
                    SELECT 1 FROM position_skill_relations
                    WHERE position_id = :pid AND skill_id = :sid
                """), {"pid": str(pid), "sid": str(sid)})
                if exists.first():
                    continue
                await session.execute(text("""
                    INSERT INTO position_skill_relations (id, position_id, skill_id, requirement_type, confidence, created_at)
                    VALUES (gen_random_uuid(), :pid, :sid, 'required', 0.9, NOW())
                """), {"pid": str(pid), "sid": str(sid)})
                inserted += 1

            await session.commit()

        print(f"完成: 写入 {inserted} 条 PSR 关系")

        # 复查
        cnt = await session.execute(text("""
            SELECT count(DISTINCT position_id) FROM position_skill_relations
        """))
        print(f"有关系岗位总数: {cnt.scalar()}")


asyncio.run(main())
