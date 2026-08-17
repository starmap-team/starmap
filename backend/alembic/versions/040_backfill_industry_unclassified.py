"""Backfill industry NULL/'' to 「未分类」literal + add CHECK constraint (2026-08-17).

Closes P0 root cause of "未分类" industry contract drift:

Before this migration, position_records.industry column had:
  - 486 rows with industry IS NULL
  - 9 rows with industry = ''
  - 0 rows with industry = '未分类'   ← violates the literal contract

Frontend compensated with `pos.industry || '未分类'` and backend stats
queries double-filtered with `!= ''` AND `!= UNCLASSIFIED_INDUSTRY_LITERAL`.
This worked at the UI surface but masked the broken DB invariant: any new
code path that forgets to filter gets polluted stats.

This migration:
1. Backfills all NULL/'' industry rows to the literal '未分类' (PRD US-003 C2).
2. Adds a CHECK constraint that future writes can't bypass normalize_industry()
   by inserting NULL/empty — backend layer already calls normalize_industry()
   at extract_repo.upsert_position_record:37, so the CHECK is a safety net.

Downgrade removes the CHECK and re-NULLs the literal for rollback safety.
"""
from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "040"
down_revision: tuple[str, ...] = ("039",)
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) Backfill: NULL → '未分类' and '' → '未分类'
    op.execute(
        "UPDATE position_records SET industry = '未分类' "
        "WHERE industry IS NULL OR industry = ''"
    )

    # 2) Safety-net CHECK: industry must be NULL or non-empty string.
    #    (Industry column is nullable; some legacy paths may still write NULL.)
    #    We intentionally do NOT constrain to NOT NULL because graph_writer
    #    Neo4j sync code paths may write NULL to indicate "no industry decided".
    op.create_check_constraint(
        "ck_position_records_industry_nonempty",
        "position_records",
        "industry IS NULL OR length(industry) > 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_position_records_industry_nonempty",
        "position_records",
        type_="check",
    )
    # Optional: revert backfilled literal to NULL. Skip in downgrade — the
    # literal was always the intended semantic value per industry.py contract.
