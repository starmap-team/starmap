"""Add ForeignKey constraints to model relationship fields.

Revision ID: 010
Revises: 009
Create Date: 2026-07-12
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "010"
down_revision: str | None = "009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── Data cleanup: remove dangling references before adding FK ──

    # position_skill_relations.position_id → position_records.id
    op.execute(
        sa.text(
            "DELETE FROM position_skill_relations "
            "WHERE position_id NOT IN (SELECT id FROM position_records)"
        )
    )
    # position_skill_relations.skill_id → skill_records.id
    op.execute(
        sa.text(
            "DELETE FROM position_skill_relations "
            "WHERE skill_id NOT IN (SELECT id FROM skill_records)"
        )
    )
    # extraction_evaluation_records.extraction_id → jd_extraction_records.id (SET NULL)
    op.execute(
        sa.text(
            "UPDATE extraction_evaluation_records SET extraction_id = NULL "
            "WHERE extraction_id IS NOT NULL "
            "AND extraction_id NOT IN (SELECT id FROM jd_extraction_records)"
        )
    )
    # learning_progress.plan_id → learning_plans.id
    op.execute(
        sa.text(
            "DELETE FROM learning_progress "
            "WHERE plan_id NOT IN (SELECT id FROM learning_plans)"
        )
    )
    # evolution_changelog.snapshot_from_id → evolution_snapshots.id (SET NULL)
    op.execute(
        sa.text(
            "UPDATE evolution_changelog SET snapshot_from_id = NULL "
            "WHERE snapshot_from_id IS NOT NULL "
            "AND snapshot_from_id NOT IN (SELECT id FROM evolution_snapshots)"
        )
    )
    # evolution_changelog.snapshot_to_id → evolution_snapshots.id (SET NULL)
    op.execute(
        sa.text(
            "UPDATE evolution_changelog SET snapshot_to_id = NULL "
            "WHERE snapshot_to_id IS NOT NULL "
            "AND snapshot_to_id NOT IN (SELECT id FROM evolution_snapshots)"
        )
    )

    # ── Add FK constraints ──

    # PositionSkillRelation.position_id → PositionRecord.id (CASCADE)
    op.create_foreign_key(
        "fk_psr_position_id",
        "position_skill_relations",
        "position_records",
        ["position_id"],
        ["id"],
        ondelete="CASCADE",
    )
    # PositionSkillRelation.skill_id → SkillRecord.id (CASCADE)
    op.create_foreign_key(
        "fk_psr_skill_id",
        "position_skill_relations",
        "skill_records",
        ["skill_id"],
        ["id"],
        ondelete="CASCADE",
    )
    # ExtractionEvaluationRecord.extraction_id → JDExtractionRecord.id (SET NULL)
    op.create_foreign_key(
        "fk_eer_extraction_id",
        "extraction_evaluation_records",
        "jd_extraction_records",
        ["extraction_id"],
        ["id"],
        ondelete="SET NULL",
    )
    # LearningProgress.plan_id → LearningPlan.id (CASCADE)
    op.create_foreign_key(
        "fk_lp_plan_id",
        "learning_progress",
        "learning_plans",
        ["plan_id"],
        ["id"],
        ondelete="CASCADE",
    )
    # EvolutionChangelog.snapshot_from_id → EvolutionSnapshot.id (SET NULL)
    op.create_foreign_key(
        "fk_ec_snapshot_from_id",
        "evolution_changelog",
        "evolution_snapshots",
        ["snapshot_from_id"],
        ["id"],
        ondelete="SET NULL",
    )
    # EvolutionChangelog.snapshot_to_id → EvolutionSnapshot.id (SET NULL)
    op.create_foreign_key(
        "fk_ec_snapshot_to_id",
        "evolution_changelog",
        "evolution_snapshots",
        ["snapshot_to_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    # Remove FK constraints (reverse order)
    op.drop_constraint("fk_ec_snapshot_to_id", "evolution_changelog", type_="foreignkey")
    op.drop_constraint("fk_ec_snapshot_from_id", "evolution_changelog", type_="foreignkey")
    op.drop_constraint("fk_lp_plan_id", "learning_progress", type_="foreignkey")
    op.drop_constraint("fk_eer_extraction_id", "extraction_evaluation_records", type_="foreignkey")
    op.drop_constraint("fk_psr_skill_id", "position_skill_relations", type_="foreignkey")
    op.drop_constraint("fk_psr_position_id", "position_skill_relations", type_="foreignkey")
