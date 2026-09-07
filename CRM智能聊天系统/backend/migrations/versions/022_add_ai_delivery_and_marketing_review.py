"""补齐 AI 营销草稿人工审核闭环。"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "022_ai_marketing_review"
down_revision = "021_message_unknown"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """增加低权限草稿和审核字段，并扩展营销事件状态机。"""
    op.add_column("marketing_events", sa.Column("ai_draft_content", sa.Text(), nullable=True))
    op.add_column(
        "marketing_events",
        sa.Column("ai_draft_agent_run_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column("marketing_events", sa.Column("ai_review_status", sa.String(20), nullable=True))
    op.add_column(
        "marketing_events",
        sa.Column("ai_reviewed_by", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column("marketing_events", sa.Column("ai_reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key(
        "fk_marketing_events_ai_draft_agent_run",
        "marketing_events",
        "agent_runs",
        ["ai_draft_agent_run_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_marketing_events_ai_reviewed_by",
        "marketing_events",
        "users",
        ["ai_reviewed_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        "ck_marketing_events_ai_review_status",
        "marketing_events",
        "ai_review_status IS NULL OR ai_review_status IN ('pending','approved','rejected')",
    )
    op.drop_constraint("ck_marketing_events_status", "marketing_events", type_="check")
    op.create_check_constraint(
        "ck_marketing_events_status",
        "marketing_events",
        "status IN ('pending','processing','waiting_ai','waiting_review','approved','rejected',"
        "'succeeded','failed','converted')",
    )
    op.create_index(
        "idx_marketing_events_store_review",
        "marketing_events",
        ["store_id", "ai_review_status", "created_at"],
    )


def downgrade() -> None:
    """把新审核终态安全降级为失败，再移除审核字段。"""
    op.execute(
        sa.text(
            """
            UPDATE marketing_events
            SET status = 'failed',
                error_code = COALESCE(error_code, 'DOWNGRADED_AI_REVIEW_STATE'),
                completed_at = COALESCE(completed_at, CURRENT_TIMESTAMP)
            WHERE status IN ('waiting_review', 'approved', 'rejected')
            """
        )
    )
    op.drop_index("idx_marketing_events_store_review", table_name="marketing_events")
    op.drop_constraint("ck_marketing_events_status", "marketing_events", type_="check")
    op.create_check_constraint(
        "ck_marketing_events_status",
        "marketing_events",
        "status IN ('pending','processing','waiting_ai','succeeded','failed','converted')",
    )
    op.drop_constraint("ck_marketing_events_ai_review_status", "marketing_events", type_="check")
    op.drop_constraint("fk_marketing_events_ai_reviewed_by", "marketing_events", type_="foreignkey")
    op.drop_constraint("fk_marketing_events_ai_draft_agent_run", "marketing_events", type_="foreignkey")
    op.drop_column("marketing_events", "ai_reviewed_at")
    op.drop_column("marketing_events", "ai_reviewed_by")
    op.drop_column("marketing_events", "ai_review_status")
    op.drop_column("marketing_events", "ai_draft_agent_run_id")
    op.drop_column("marketing_events", "ai_draft_content")
