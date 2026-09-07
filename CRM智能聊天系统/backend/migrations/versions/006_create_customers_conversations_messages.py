"""创建客户、会话和消息表。"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "006_workspace"
down_revision = "005_store_channel_scope"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """创建工作台消息主链路数据结构。"""
    op.create_table(
        "customers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "store_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("platform", sa.String(30), nullable=True),
        sa.Column("external_customer_id", sa.String(200), nullable=True),
        sa.Column("name", sa.String(200), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("avatar", sa.String(500), nullable=True),
        sa.Column("tags", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("order_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_spend", sa.Numeric(18, 2), server_default="0", nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_customers_store", "customers", ["store_id"])
    op.create_index(
        "uq_customers_store_platform_external",
        "customers",
        ["store_id", "platform", "external_customer_id"],
        unique=True,
        postgresql_where=sa.text("platform IS NOT NULL AND external_customer_id IS NOT NULL"),
    )
    op.create_table(
        "conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "store_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "customer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customers.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("platform", sa.String(30), nullable=False),
        sa.Column("external_conversation_id", sa.String(200), nullable=False),
        sa.Column("status", sa.String(20), server_default="active", nullable=False),
        sa.Column(
            "assigned_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("unread_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_message_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("transfer_reason", sa.String(500), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status IN ('active', 'pending', 'transferred', 'resolved', 'closed')",
            name="ck_conversations_status",
        ),
        sa.UniqueConstraint("store_id", "external_conversation_id", name="uq_conversation_store_external"),
    )
    op.create_index("idx_conversations_store_status_updated", "conversations", ["store_id", "status", "updated_at"])
    op.create_index(
        "idx_conversations_store_unread",
        "conversations",
        ["store_id", "unread_count"],
        postgresql_where=sa.text("unread_count > 0"),
    )
    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "store_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "customer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customers.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("platform", sa.String(30), nullable=False),
        sa.Column("external_message_id", sa.String(200), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("direction", sa.String(20), nullable=False),
        sa.Column("message_type", sa.String(30), server_default="text", nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=True),
        sa.Column("language", sa.String(20), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("agent_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("error_code", sa.String(100), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("role IN ('user', 'assistant', 'agent', 'system')", name="ck_messages_role"),
        sa.CheckConstraint("direction IN ('inbound', 'outbound')", name="ck_messages_direction"),
        sa.CheckConstraint(
            "status IN ('received', 'processing', 'sent', 'delivered', 'failed')",
            name="ck_messages_status",
        ),
        sa.UniqueConstraint("platform", "external_message_id", name="uq_message_platform_external"),
    )
    op.create_index("idx_messages_conversation_created", "messages", ["conversation_id", "created_at"])
    op.create_index("idx_messages_store_status_created", "messages", ["store_id", "status", "created_at"])
    op.create_index(
        "uq_messages_store_idempotency",
        "messages",
        ["store_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )
    op.create_foreign_key(
        "fk_conversations_last_message",
        "conversations",
        "messages",
        ["last_message_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """按依赖顺序删除消息主链路表。"""
    op.drop_constraint("fk_conversations_last_message", "conversations", type_="foreignkey")
    op.drop_index("uq_messages_store_idempotency", table_name="messages")
    op.drop_index("idx_messages_store_status_created", table_name="messages")
    op.drop_index("idx_messages_conversation_created", table_name="messages")
    op.drop_table("messages")
    op.drop_index("idx_conversations_store_unread", table_name="conversations")
    op.drop_index("idx_conversations_store_status_updated", table_name="conversations")
    op.drop_table("conversations")
    op.drop_index("uq_customers_store_platform_external", table_name="customers")
    op.drop_index("idx_customers_store", table_name="customers")
    op.drop_table("customers")
