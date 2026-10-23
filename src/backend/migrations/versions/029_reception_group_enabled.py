"""分组状态用于隐藏工作台中的停用话术。"""

import sqlalchemy as sa
from alembic import op

revision = "029_reception_group_enabled"
down_revision = "028_basic_reception_config"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "reception_groups",
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    op.drop_column("reception_groups", "enabled")
