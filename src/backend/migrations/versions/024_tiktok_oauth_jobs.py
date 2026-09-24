"""为 TikTok OAuth 快速回跳创建短期加密任务表。"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "024_tiktok_oauth_jobs"
down_revision = "023_marketing_review_idempotency"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """保存经用户、店铺绑定的一次性任务；不保存明文授权材料。"""
    op.create_table(
        "tiktok_oauth_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("store_id", UUID(as_uuid=True), sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False),
        sa.Column("state_cipher", sa.String(1200), nullable=True),
        sa.Column("code_cipher", sa.String(1200), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("error_code", sa.String(100), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_tiktok_oauth_jobs_user_id", "tiktok_oauth_jobs", ["user_id"])
    op.create_index("ix_tiktok_oauth_jobs_store_id", "tiktok_oauth_jobs", ["store_id"])
    op.create_index("ix_tiktok_oauth_jobs_status", "tiktok_oauth_jobs", ["status"])


def downgrade() -> None:
    """只在任务已终止且密文被清理后回退该表。"""
    op.drop_index("ix_tiktok_oauth_jobs_status", table_name="tiktok_oauth_jobs")
    op.drop_index("ix_tiktok_oauth_jobs_store_id", table_name="tiktok_oauth_jobs")
    op.drop_index("ix_tiktok_oauth_jobs_user_id", table_name="tiktok_oauth_jobs")
    op.drop_table("tiktok_oauth_jobs")
