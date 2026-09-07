"""创建店铺与渠道账号，并修正用户角色的店铺范围。"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "005_store_channel_scope"
down_revision = "004_seed_rbac"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """创建租户基础表，并允许同一用户在不同店铺拥有相同角色。"""
    op.create_table(
        "stores",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("code", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), server_default="active", nullable=False),
        sa.Column("timezone", sa.String(50), server_default="UTC", nullable=False),
        sa.Column("currency", sa.String(10), server_default="USD", nullable=False),
        sa.Column("metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('active', 'disabled')", name="ck_stores_status"),
        sa.UniqueConstraint("code", name="uq_stores_code"),
    )
    op.create_table(
        "channel_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "store_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("platform", sa.String(30), nullable=False),
        sa.Column("external_store_id", sa.String(200), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("access_token_ref", sa.String(500), nullable=False),
        sa.Column("refresh_token_ref", sa.String(500), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), server_default="connected", nullable=False),
        sa.Column("scopes", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("platform IN ('tiktok', 'shopee', 'amazon')", name="ck_channel_platform"),
        sa.UniqueConstraint("platform", "external_store_id", name="uq_channel_platform_store"),
    )
    op.create_index("idx_channel_accounts_store", "channel_accounts", ["store_id"])

    op.add_column("user_roles", sa.Column("id", postgresql.UUID(as_uuid=True), nullable=True))
    op.execute("UPDATE user_roles SET id = gen_random_uuid() WHERE id IS NULL")
    op.drop_constraint("user_roles_pkey", "user_roles", type_="primary")
    op.drop_constraint("uq_user_roles_scope", "user_roles", type_="unique")
    op.alter_column("user_roles", "id", nullable=False)
    op.create_primary_key("pk_user_roles", "user_roles", ["id"])
    op.create_foreign_key("fk_user_roles_store", "user_roles", "stores", ["store_id"], ["id"], ondelete="CASCADE")
    op.create_index(
        "uq_user_roles_system_scope",
        "user_roles",
        ["user_id", "role_id"],
        unique=True,
        postgresql_where=sa.text("store_id IS NULL"),
    )
    op.create_index(
        "uq_user_roles_store_scope",
        "user_roles",
        ["user_id", "role_id", "store_id"],
        unique=True,
        postgresql_where=sa.text("store_id IS NOT NULL"),
    )


def downgrade() -> None:
    """恢复 Phase 1 用户角色结构并删除店铺表。"""
    op.drop_index("uq_user_roles_store_scope", table_name="user_roles")
    op.drop_index("uq_user_roles_system_scope", table_name="user_roles")
    op.drop_constraint("fk_user_roles_store", "user_roles", type_="foreignkey")
    op.drop_constraint("pk_user_roles", "user_roles", type_="primary")
    op.drop_column("user_roles", "id")
    op.create_primary_key("user_roles_pkey", "user_roles", ["user_id", "role_id"])
    op.create_unique_constraint("uq_user_roles_scope", "user_roles", ["user_id", "role_id", "store_id"])
    op.drop_index("idx_channel_accounts_store", table_name="channel_accounts")
    op.drop_table("channel_accounts")
    op.drop_table("stores")
