"""Persist reviewed ordered reply delivery plans."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "042_agent_reply_delivery"
down_revision = "041_merge_agent_multishop_collab"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_reply_batches",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("scope_key", sa.String(64), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("store_id", sa.Uuid(), sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("authorized_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("payload_json", JSONB(), nullable=False),
        sa.Column("state_json", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("scope_key", "idempotency_key", name="uq_agent_reply_batch_key"),
    )
    op.create_index("ix_agent_reply_batches_store_id", "agent_reply_batches", ["store_id"])


def downgrade() -> None:
    op.drop_index("ix_agent_reply_batches_store_id", table_name="agent_reply_batches")
    op.drop_table("agent_reply_batches")
