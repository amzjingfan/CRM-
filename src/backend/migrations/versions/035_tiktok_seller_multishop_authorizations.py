"""Add shared TikTok seller grants and bounded shop-selection state."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "035_tiktok_seller_multishop"
down_revision = "034_agent_debug_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tiktok_seller_authorizations",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("app_key", sa.String(200), nullable=False),
        sa.Column("open_id_hash", sa.String(64), nullable=False),
        sa.Column("access_token_ref", sa.String(1200), nullable=False),
        sa.Column("refresh_token_ref", sa.String(1200), nullable=False),
        sa.Column("access_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("refresh_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("next_refresh_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scopes", postgresql.JSONB(), nullable=False),
        sa.Column("authorized_shop_ids", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("app_key", "open_id_hash", name="uq_tiktok_seller_app_principal"),
    )
    op.add_column(
        "channel_accounts",
        sa.Column(
            "seller_authorization_id",
            sa.UUID(),
            sa.ForeignKey("tiktok_seller_authorizations.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_channel_accounts_seller_authorization_id", "channel_accounts", ["seller_authorization_id"])
    op.add_column("tiktok_oauth_jobs", sa.Column("selection_token_cipher", sa.Text(), nullable=True))
    op.add_column("tiktok_oauth_jobs", sa.Column("selection_shops", postgresql.JSONB(), nullable=True))
    op.add_column("tiktok_oauth_jobs", sa.Column("selection_expires_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    if bind.execute(sa.text("SELECT 1 FROM tiktok_seller_authorizations LIMIT 1")).first():
        raise RuntimeError("已有卖家共享授权；需先显式处理关联店铺和凭证后再回退迁移")
    if bind.execute(sa.text("SELECT 1 FROM tiktok_oauth_jobs WHERE status = 'selection_required' LIMIT 1")).first():
        raise RuntimeError("已有待选择店铺的授权任务；需先完成或过期清理后再回退迁移")
    op.drop_column("tiktok_oauth_jobs", "selection_expires_at")
    op.drop_column("tiktok_oauth_jobs", "selection_shops")
    op.drop_column("tiktok_oauth_jobs", "selection_token_cipher")
    op.drop_index("ix_channel_accounts_seller_authorization_id", table_name="channel_accounts")
    op.drop_column("channel_accounts", "seller_authorization_id")
    op.drop_table("tiktok_seller_authorizations")
