"""Attach low-sensitive frozen context references to Agent runs."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "037_agent_run_snapshot"
down_revision = "036_agent_prompt_drafts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agent_runs", sa.Column("snapshot_hash", sa.String(64), nullable=True))
    op.add_column("agent_runs", sa.Column("snapshot_ref", JSONB(), nullable=True))


def downgrade() -> None:
    if op.get_bind().scalar(sa.text("SELECT EXISTS (SELECT 1 FROM agent_runs WHERE snapshot_ref IS NOT NULL)")):
        raise RuntimeError("已有新版 Agent 运行快照，不能无损降级；请从部署备份恢复")
    op.drop_column("agent_runs", "snapshot_ref")
    op.drop_column("agent_runs", "snapshot_hash")
