"""保存 CRM 内部星标和人工关闭时间。"""

import sqlalchemy as sa
from alembic import op

revision = "025_workspace_actions"
down_revision = "024_tiktok_oauth_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("conversations", sa.Column("is_starred", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column("conversations", sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("conversations", "closed_at")
    op.drop_column("conversations", "is_starred")
