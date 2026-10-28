"""Add per-conversation Agent summary and verified facts."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "038_agent_session_memory"
down_revision = "037_agent_run_snapshot"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_session_memories",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("store_id", sa.UUID(), sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "conversation_id",
            sa.UUID(),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("customer_id", sa.UUID(), sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("summary_source_ids", JSONB(), nullable=False),
        sa.Column("facts_json", JSONB(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "idx_agent_session_memories_scope", "agent_session_memories", ["store_id", "conversation_id", "customer_id"]
    )


def downgrade() -> None:
    if op.get_bind().scalar(sa.text("SELECT EXISTS (SELECT 1 FROM agent_session_memories)")):
        raise RuntimeError("已有会话记忆，不能无损降级；请从部署备份恢复")
    op.drop_index("idx_agent_session_memories_scope", table_name="agent_session_memories")
    op.drop_table("agent_session_memories")
