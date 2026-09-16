"""创建 Agent 运行追踪表。"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "009_agent_runs"
down_revision = "008_webhooks_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """创建只保存安全摘要、模型统计和最终动作的 Agent 运行表。"""
    op.create_table(
        "agent_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "store_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("stores.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "trigger_message_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("messages.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("model_provider", sa.String(50), nullable=False),
        sa.Column("model_name", sa.String(100), nullable=False),
        sa.Column("prompt_version", sa.String(100), nullable=True),
        sa.Column("intent", sa.String(100), nullable=True),
        sa.Column("intent_confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("retrieval_score", sa.Numeric(5, 4), nullable=True),
        sa.Column("final_confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("input_summary", sa.Text(), nullable=True),
        sa.Column("output_summary", sa.Text(), nullable=True),
        sa.Column("error_code", sa.String(100), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("trace_id", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "action IN ('auto_reply', 'human_review', 'transfer_human', 'failed')",
            name="ck_agent_runs_action",
        ),
        sa.CheckConstraint(
            "status IN ('running', 'succeeded', 'failed', 'timeout')",
            name="ck_agent_runs_status",
        ),
        sa.CheckConstraint(
            "intent_confidence IS NULL OR (intent_confidence >= 0 AND intent_confidence <= 1)",
            name="ck_agent_runs_intent_confidence",
        ),
        sa.CheckConstraint(
            "retrieval_score IS NULL OR (retrieval_score >= 0 AND retrieval_score <= 1)",
            name="ck_agent_runs_retrieval_score",
        ),
        sa.CheckConstraint(
            "final_confidence IS NULL OR (final_confidence >= 0 AND final_confidence <= 1)",
            name="ck_agent_runs_final_confidence",
        ),
    )
    op.create_index(
        "idx_agent_runs_conversation_created",
        "agent_runs",
        ["conversation_id", "created_at"],
    )
    op.create_index("idx_agent_runs_store_created", "agent_runs", ["store_id", "created_at"])


def downgrade() -> None:
    """回滚 Agent 运行追踪表，不影响 Phase 2 业务表。"""
    op.drop_index("idx_agent_runs_store_created", table_name="agent_runs")
    op.drop_index("idx_agent_runs_conversation_created", table_name="agent_runs")
    op.drop_table("agent_runs")
