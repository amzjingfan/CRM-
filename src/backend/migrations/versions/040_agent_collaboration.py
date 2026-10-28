"""persist scoped Agent internal collaboration records

Revision ID: 040_agent_collaboration
Revises: 039_agent_run_hierarchy
"""

import sqlalchemy as sa
from alembic import op

revision = "040_agent_collaboration"
down_revision = "039_agent_run_hierarchy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_collaboration_entries",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("store_id", sa.UUID(), sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False),
        sa.Column("conversation_id", sa.UUID(), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", sa.UUID(), sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent_run_id", sa.UUID(), sa.ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by", sa.UUID(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("kind IN ('handoff_request', 'internal_note')", name="ck_agent_collaboration_kind"),
        sa.UniqueConstraint(
            "store_id", "conversation_id", "agent_run_id", "kind", "content_hash", name="uq_agent_collaboration_replay"
        ),
    )
    op.create_index(
        "ix_agent_collaboration_conversation",
        "agent_collaboration_entries",
        ["store_id", "conversation_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_agent_collaboration_conversation", table_name="agent_collaboration_entries")
    op.drop_table("agent_collaboration_entries")
