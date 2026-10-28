"""Persist editable Agent model and seven-section prompt drafts."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "036_agent_prompt_drafts"
down_revision = "035_dynamic_agent_versions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agent_configs", sa.Column("draft_model_provider", sa.String(50), nullable=True))
    op.add_column("agent_configs", sa.Column("draft_model_name", sa.String(150), nullable=True))
    op.add_column(
        "agent_configs",
        sa.Column("draft_prompt_sections", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )


def downgrade() -> None:
    connection = op.get_bind()
    if connection.scalar(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM agent_configs WHERE draft_model_provider IS NOT NULL "
            "OR draft_model_name IS NOT NULL OR draft_prompt_sections <> '{}'::jsonb)"
        )
    ):
        raise RuntimeError("已有新版 Agent 草稿，不能无损降级；请从部署备份恢复")
    op.drop_column("agent_configs", "draft_prompt_sections")
    op.drop_column("agent_configs", "draft_model_name")
    op.drop_column("agent_configs", "draft_model_provider")
