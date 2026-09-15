"""创建 Webhook 事件和审计日志表。"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "008_webhooks_audit"
down_revision = "007_orders_items"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """创建可靠接入和敏感动作追踪所需的数据结构。"""
    op.create_table(
        "webhook_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("platform", sa.String(30), nullable=False),
        sa.Column(
            "channel_account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("channel_accounts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("external_event_id", sa.String(200), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("signature_valid", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("payload_hash", sa.String(128), nullable=False),
        sa.Column("raw_payload", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(20), server_default="received", nullable=False),
        sa.Column("error_code", sa.String(100), nullable=True),
        sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status IN ('received', 'processing', 'succeeded', 'failed', 'ignored')",
            name="ck_webhook_events_status",
        ),
        sa.UniqueConstraint("platform", "external_event_id", name="uq_webhook_platform_event"),
    )
    op.create_index("idx_webhook_status_created", "webhook_events", ["status", "created_at"])
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "store_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("stores.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("actor_type", sa.String(30), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(100), nullable=False),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("request_id", sa.String(100), nullable=True),
        sa.Column("before_data", postgresql.JSONB(), nullable=True),
        sa.Column("after_data", postgresql.JSONB(), nullable=True),
        sa.Column("result", sa.String(30), nullable=False),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_audit_store_created", "audit_logs", ["store_id", "created_at"])
    op.create_index("idx_audit_resource", "audit_logs", ["resource_type", "resource_id"])


def downgrade() -> None:
    """删除审计和 Webhook 事件表。"""
    op.drop_index("idx_audit_resource", table_name="audit_logs")
    op.drop_index("idx_audit_store_created", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_index("idx_webhook_status_created", table_name="webhook_events")
    op.drop_table("webhook_events")
