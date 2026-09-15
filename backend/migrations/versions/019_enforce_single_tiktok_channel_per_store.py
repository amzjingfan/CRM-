"""强制一个内部店铺只能绑定一个 TikTok 渠道。"""

import sqlalchemy as sa
from alembic import op

revision = "019_tiktok_channel_unique"
down_revision = "018_ai_observability"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """迁移前拒绝历史重复项，再建立 TikTok 专用部分唯一索引。"""
    duplicate_store_id = (
        op.get_bind()
        .execute(
            sa.text(
                """
            SELECT store_id
            FROM channel_accounts
            WHERE platform = 'tiktok'
            GROUP BY store_id
            HAVING count(*) > 1
            LIMIT 1
            """
            )
        )
        .scalar_one_or_none()
    )
    if duplicate_store_id is not None:
        # 自动删除授权记录会破坏审计和真实店铺归属，必须先人工确认保留项。
        raise RuntimeError("检测到同一内部店铺存在多个 TikTok 渠道，请先完成授权数据治理")
    op.create_index(
        "uq_channel_accounts_store_tiktok",
        "channel_accounts",
        ["store_id"],
        unique=True,
        postgresql_where=sa.text("platform = 'tiktok'"),
    )


def downgrade() -> None:
    """移除 TikTok 单渠道约束，保留所有授权数据。"""
    op.drop_index("uq_channel_accounts_store_tiktok", table_name="channel_accounts")
