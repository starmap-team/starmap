"""Phase 16-01 Task 4: Add pipeline_runs + data_source_metrics indexes.

使用 IF NOT EXISTS 避免冲突 (Fix M2 from review).
"""
from __future__ import annotations

from alembic import op

revision: str = "025"
down_revision: str | None = "024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 优化 /pipeline/stages 的 run selection 查询 (按 status + started_at 排序)
    op.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_runs_status_started ON pipeline_runs(status, started_at DESC)")
    # 优化 health dashboard 的 metrics 查询
    op.execute("CREATE INDEX IF NOT EXISTS idx_data_source_metrics_source_started ON data_source_metrics(source_id, started_at DESC)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_pipeline_runs_status_started")
    op.execute("DROP INDEX IF EXISTS idx_data_source_metrics_source_started")