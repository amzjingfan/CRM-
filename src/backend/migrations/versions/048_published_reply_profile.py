"""冻结店铺 Agent 回复偏好；历史发布保留 NULL 兼容语义。"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "048_published_reply_profile"
down_revision = "047_supervisor_store_auth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agent_config_versions", sa.Column("reply_profile", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("agent_config_versions", "reply_profile")
