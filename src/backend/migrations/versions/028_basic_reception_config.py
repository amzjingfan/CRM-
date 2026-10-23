"""独立保存快捷回复与接待策略配置，未接入自动发送。"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "028_basic_reception_config"
down_revision = "027_tiktok_direct_store_oauth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reception_groups",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "store_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("scope", sa.String(10), nullable=False),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("scope IN ('personal', 'team')", name="ck_reception_groups_scope"),
        sa.CheckConstraint(
            "(scope = 'personal' AND owner_user_id IS NOT NULL) OR (scope = 'team' AND owner_user_id IS NULL)",
            name="ck_reception_groups_owner",
        ),
    )
    op.create_index(
        "ix_reception_groups_scope_order",
        "reception_groups",
        ["store_id", "scope", "owner_user_id", "sort_order", "id"],
    )
    op.create_table(
        "reception_replies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "store_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("scope", sa.String(10), nullable=False),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column(
            "group_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("reception_groups.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("shortcut", sa.String(8), nullable=False),
        sa.Column("tags", postgresql.JSONB(), nullable=False),
        sa.Column("site_code", sa.String(20)),
        sa.Column("messages", postgresql.JSONB(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("scope IN ('personal', 'team')", name="ck_reception_replies_scope"),
        sa.CheckConstraint(
            "(scope = 'personal' AND owner_user_id IS NOT NULL) OR (scope = 'team' AND owner_user_id IS NULL)",
            name="ck_reception_replies_owner",
        ),
    )
    op.create_index(
        "ix_reception_replies_order",
        "reception_replies",
        ["store_id", "scope", "owner_user_id", "sort_order", "id"],
    )
    op.create_index(
        "uq_reception_replies_personal_shortcut",
        "reception_replies",
        ["store_id", "owner_user_id", "shortcut"],
        unique=True,
        postgresql_where=sa.text("scope = 'personal'"),
    )
    op.create_index(
        "uq_reception_replies_team_shortcut",
        "reception_replies",
        ["store_id", "shortcut"],
        unique=True,
        postgresql_where=sa.text("scope = 'team'"),
    )
    op.create_table(
        "reception_policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("timeout_minutes", sa.Integer()),
        sa.Column("valid_from", sa.DateTime(timezone=True)),
        sa.Column("valid_to", sa.DateTime(timezone=True)),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column(
            "created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("kind IN ('timeout', 'welcome')", name="ck_reception_policies_kind"),
        sa.CheckConstraint(
            "(kind = 'timeout' AND timeout_minutes BETWEEN 1 AND 43200) OR "
            "(kind = 'welcome' AND timeout_minutes IS NULL)",
            name="ck_reception_policies_timeout",
        ),
        sa.CheckConstraint(
            "valid_from IS NULL OR valid_to IS NULL OR valid_from < valid_to", name="ck_reception_policies_dates"
        ),
    )
    op.create_index("ix_reception_policies_kind_order", "reception_policies", ["kind", "sort_order", "id"])
    op.create_table(
        "reception_policy_stores",
        sa.Column(
            "policy_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("reception_policies.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "store_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("stores.id", ondelete="CASCADE"), primary_key=True
        ),
    )
    op.create_index("ix_reception_policy_stores_store_id", "reception_policy_stores", ["store_id"])
    op.create_table(
        "reception_mutations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "actor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("key_hash", sa.String(64), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("permission", sa.String(100), nullable=False),
        sa.Column("response_body", postgresql.JSONB(), nullable=False),
        sa.Column("store_ids", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("actor_id", "key_hash", name="uq_reception_mutations_actor_key"),
    )


def downgrade() -> None:
    connection = op.get_bind()
    if connection.scalar(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM reception_groups) OR EXISTS (SELECT 1 FROM reception_replies) "
            "OR EXISTS (SELECT 1 FROM reception_policies)"
        )
    ):
        raise RuntimeError("基础接待已有配置，不能无损降级；请使用部署备份恢复")
    op.drop_table("reception_mutations")
    op.drop_index("ix_reception_policy_stores_store_id", table_name="reception_policy_stores")
    op.drop_table("reception_policy_stores")
    op.drop_index("ix_reception_policies_kind_order", table_name="reception_policies")
    op.drop_table("reception_policies")
    op.drop_index("uq_reception_replies_team_shortcut", table_name="reception_replies")
    op.drop_index("uq_reception_replies_personal_shortcut", table_name="reception_replies")
    op.drop_index("ix_reception_replies_order", table_name="reception_replies")
    op.drop_table("reception_replies")
    op.drop_index("ix_reception_groups_scope_order", table_name="reception_groups")
    op.drop_table("reception_groups")
