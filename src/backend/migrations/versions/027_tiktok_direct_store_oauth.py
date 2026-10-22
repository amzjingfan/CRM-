"""允许新店铺授权任务在平台身份确认前不绑定内部店铺。"""

import sqlalchemy as sa
from alembic import op

revision = "027_tiktok_direct_store_oauth"
down_revision = "026_team_accounts_departments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """仅放宽短期任务的店铺外键并记录经过校验的回跳页。"""
    op.alter_column("tiktok_oauth_jobs", "store_id", existing_type=sa.UUID(), nullable=True)
    op.add_column(
        "tiktok_oauth_jobs",
        sa.Column("return_to", sa.String(200), server_default="/settings/channels", nullable=False),
    )


def downgrade() -> None:
    """待处理的新店授权尚无店铺时禁止无损降级。"""
    connection = op.get_bind()
    has_unbound_jobs = connection.scalar(
        sa.text("SELECT EXISTS (SELECT 1 FROM tiktok_oauth_jobs WHERE store_id IS NULL)")
    )
    if has_unbound_jobs:
        raise RuntimeError("仍有未绑定店铺的 TikTok 授权任务，不能无损降级")
    op.drop_column("tiktok_oauth_jobs", "return_to")
    op.alter_column("tiktok_oauth_jobs", "store_id", existing_type=sa.UUID(), nullable=False)
