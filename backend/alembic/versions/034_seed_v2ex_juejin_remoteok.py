"""Seed V2EX / Juejin / RemoteOK data sources + fix Remotive platform (D6, 2026-08-12).

背景 (deep-interview 7crawler-jd 收敛):
- 爬虫适配器注册表 (crawl.py build_spider_registry) 已含 7 平台: v2ex/remotive/arbeitnow/
  jobicy/weworkremotely/juejin/remoteok，但 DB 仅 seed 了 4 个远程源 (迁移 021)。
- 页面缺 V2EX / Juejin / RemoteOK 三个数据源卡片，补齐使 7 域全部可「立即采集」。
- Remotive (021) 的 config.platform 误配为 "v2ex"（v2ex_remote spider 双源时代遗留），
  D6 逐源隔离后必须改为 "remotive"，否则 Remotive 卡只会抓 V2EX 记录。

source_type 说明: juejin 为技术博客源 (非岗位 JD，PLAN-002)，source_type="blog" 已在
前端 SOURCE_TYPE_LABELS 覆盖 (技术博客)。
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "034"
down_revision: tuple[str, ...] = ("033",)
branch_labels = None
depends_on = None


def _seed_source(name: str, source_type: str, authority: float, config: str) -> None:
    op.execute(
        sa.text(
            """
            INSERT INTO data_sources (id, name, source_type, authority_score, status, config)
            VALUES (gen_random_uuid(), :name, :source_type, :authority_score, 'active', CAST(:config AS JSONB))
            ON CONFLICT (name) DO NOTHING
            """
        ).bindparams(
            name=name,
            source_type=source_type,
            authority_score=authority,
            config=config,
        )
    )


def upgrade() -> None:
    # 1. 修正 Remotive platform: v2ex → remotive (D6 逐源隔离)
    op.execute(
        sa.text(
            """
            UPDATE data_sources
            SET config = jsonb_set(CAST(config AS jsonb), CAST('{platform}' AS text[]), CAST('"remotive"' AS jsonb))
            WHERE name = 'Remotive (远程)' AND config->>'platform' = 'v2ex'
            """
        )
    )

    # 2. Seed V2EX (中文酷工作)
    _seed_source(
        "V2EX 酷工作",
        "job_board",
        0.45,
        '{"platform":"v2ex","max_count":30,"probe_url":"https://www.v2ex.com/api/topics/show.json?node_name=jobs"}',
    )

    # 3. Seed Juejin (技术博客非结构化源, 非岗位 JD)
    _seed_source(
        "掘金技术社区",
        "blog",
        0.35,
        '{"platform":"juejin","max_count":10,"probe_url":"https://juejin.cn/sitemap/posts/index.xml"}',
    )

    # 4. Seed RemoteOK (英文远程 JD 源)
    _seed_source(
        "RemoteOK",
        "api",
        0.5,
        '{"platform":"remoteok","tag":"python","max_count":20,"probe_url":"https://remoteok.com/api"}',
    )


def downgrade() -> None:
    # 还原 Remotive platform
    op.execute(
        sa.text(
            """
            UPDATE data_sources
            SET config = jsonb_set(CAST(config AS jsonb), CAST('{platform}' AS text[]), CAST('"v2ex"' AS jsonb))
            WHERE name = 'Remotive (远程)' AND config->>'platform' = 'remotive'
            """
        )
    )
    op.execute(
        "DELETE FROM data_sources WHERE name IN ('V2EX 酷工作', '掘金技术社区', 'RemoteOK')"
    )
