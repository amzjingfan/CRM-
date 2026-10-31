"""Persist reviewed multi-Agent preview drafts without enabling platform sends.

Revision ID: 049_agent_auto_reply_preview
Revises: 048_published_reply_profile
"""

import sqlalchemy as sa
from alembic import op

revision = "049_agent_auto_reply_preview"
down_revision = "048_published_reply_profile"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agent_tasks", sa.Column("mode", sa.String(20), server_default="legacy", nullable=False))
    op.add_column("agent_tasks", sa.Column("preview_content", sa.Text(), nullable=True))
    op.create_index(
        "idx_agent_tasks_conversation_preview", "agent_tasks", ["store_id", "conversation_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("idx_agent_tasks_conversation_preview", table_name="agent_tasks")
    op.drop_column("agent_tasks", "preview_content")
    op.drop_column("agent_tasks", "mode")
