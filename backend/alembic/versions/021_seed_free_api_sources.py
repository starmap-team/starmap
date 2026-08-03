"""Seed 4 free API/Feed data sources (Phase 15-01 Task 6).

Insert 4 DataSource rows: Arbeitnow, Jobicy, WeWorkRemotely, Remotive
source_type='api' 表示这些是真实 API 调用而非爬虫。

Revision ID: 021
Revises: 020
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "021"
down_revision: str | None = "019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Seed 4 free API data sources. ON CONFLICT skip (idempotent)."""
    bind = op.get_bind()
    rows = [
        {
            "name": "Arbeitnow (远程)",
            "source_type": "api",
            "authority_score": 0.6,
            "status": "active",
            "config": '{"platform":"arbeitnow","keyword":"python","max_count":50,"probe_url":"https://arbeitnow.com/api/job-board-api"}',
        },
        {
            "name": "Jobicy (远程)",
            "source_type": "api",
            "authority_score": 0.5,
            "status": "active",
            "config": '{"platform":"jobicy","tag":"python","max_count":50,"probe_url":"https://jobicy.com/api/v2/remote-jobs?count=1"}',
        },
        {
            "name": "WeWorkRemotely (远程)",
            "source_type": "rss",
            "authority_score": 0.55,
            "status": "active",
            "config": '{"platform":"weworkremotely","max_count":50,"probe_url":"https://weworkremotely.com/categories/remote-programming-jobs.rss"}',
        },
        {
            "name": "Remotive (远程)",
            "source_type": "api",
            "authority_score": 0.6,
            "status": "active",
            "config": '{"platform":"v2ex","keyword":"python","max_count":50,"probe_url":"https://remotive.com/api/remote-jobs?limit=1"}',
        },
    ]
    for r in rows:
        op.execute(
            sa.text(
                """
                INSERT INTO data_sources (id, name, source_type, authority_score, status, config)
                VALUES (gen_random_uuid(), :name, :source_type, :authority_score, :status, CAST(:config AS JSONB))
                ON CONFLICT (name) DO NOTHING
                """
            ).bindparams(
                name=r["name"],
                source_type=r["source_type"],
                authority_score=r["authority_score"],
                status=r["status"],
                config=r["config"],
            )
        )


def downgrade() -> None:
    """Remove 4 free API data sources."""
    op.execute(
        "DELETE FROM data_sources WHERE name IN ('Arbeitnow (远程)', 'Jobicy (远程)', 'WeWorkRemotely (远程)', 'Remotive (远程)')"
    )