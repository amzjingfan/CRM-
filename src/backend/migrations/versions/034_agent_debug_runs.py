"""Allow isolated Agent debug traces without fabricating customer conversations."""

import sqlalchemy as sa
from alembic import op

revision = "034_agent_debug_runs"
down_revision = "033_file_version_approval"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("agent_runs", "conversation_id", existing_type=sa.UUID(), nullable=True)


def downgrade() -> None:
    if op.get_bind().execute(sa.text("SELECT 1 FROM agent_runs WHERE conversation_id IS NULL LIMIT 1")).first():
        raise RuntimeError("已有独立 Agent 调试记录，请先归档并显式处理后再回退迁移")
    op.alter_column("agent_runs", "conversation_id", existing_type=sa.UUID(), nullable=False)
