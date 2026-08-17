"""直接 inline 跑 pending_review 岗位的 industry backfill（2026-08-17 闭环补治）。

不依赖外部脚本（避免 parallel session 移动文件），直接用 Python+poetry 跑。
"""
import asyncio
import json
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.extraction.industry import (
    UNCLASSIFIED_INDUSTRY_LITERAL,
    is_generic_industry,
    normalize_industry,
)
from app.core.extraction.llm_client import LLMClient
from app.db.session import get_async_engine
from app.models.extraction_models import PositionRecord


async def main():
    engine = get_async_engine()
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    llm = LLMClient()
    done = 0
    skipped = 0
    async with sessionmaker() as session:
        rows = (await session.execute(
            select(PositionRecord)
            .where(PositionRecord.industry == UNCLASSIFIED_INDUSTRY_LITERAL)
            .where(PositionRecord.review_status == "pending_review")
            .order_by(PositionRecord.created_at.desc())
            .limit(500)
        )).scalars().all()
        print(f"扫描到 {len(rows)} 个 pending_review 未分类岗位")
        for start in range(0, len(rows), 10):
            batch = rows[start:start+10]
            names = [p.name for p in batch]
            prompt = (
                "You are a recruiting industry classifier. For each job position title, "
                "return the most specific industry it belongs to, in Simplified Chinese.\n"
                "Respond ONLY as JSON object mapping each original title to its industry.\n"
                "Rules: pick from the canonical industry list below if possible; "
                "the list has 30 standard industries; if a title truly "
                "cannot be classified, map it to null.\n"
                "Canonical industries (reference): 互联网/IT、金融科技、智能制造、医疗健康、零售/电商、销售/营销、教育/培训、人力资源服务、咨询服务、广告/传媒、文化创意、网络安全、半导体、通信/电信、汽车、生物医药、消费品、餐饮/酒店/旅游、物流/供应链、能源/环保、建筑工程/房地产、政府/公共事业、游戏、航空航天、海洋/船舶、学术研究、法律/合规、农业科技、制造业(传统)\n"
                "Output format: {\"title1\": \"行业1\", \"title2\": \"行业2\", ...}\n"
                f"Titles to classify: {json.dumps(names, ensure_ascii=False)}\n"
            )
            try:
                raw = await llm.generate(prompt, json_mode=True, temperature=0.0)
                data = json.loads(raw)
            except Exception as exc:
                print(f"  ! batch error: {exc}")
                data = {}
            for pos in batch:
                val = (data.get(pos.name) or "").strip()
                if val and not is_generic_industry(val):
                    normalized = normalize_industry(val)
                    pos.industry = normalized
                    print(f"  ✓ {pos.name!r} -> {normalized!r}")
                    done += 1
                else:
                    skipped += 1
            await session.commit()
        print(f"\n[backfill] 完成 {done}/{len(rows)} (skipped {skipped})")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
