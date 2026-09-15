"""创建客户评价和主动营销数据结构。"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "013_marketing"
down_revision = "012_tool_calls"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """创建评价、活动及具备去重和重试能力的营销事件。"""
    op.create_table(
        "customer_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "store_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "customer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customers.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orders.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("platform", sa.String(30), nullable=False),
        sa.Column("external_review_id", sa.String(200), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_payload", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("rating >= 1 AND rating <= 5", name="ck_customer_reviews_rating"),
        sa.UniqueConstraint("store_id", "platform", "external_review_id", name="uq_review_store_platform_external"),
    )
    op.create_index("idx_reviews_store_rating", "customer_reviews", ["store_id", "rating", "reviewed_at"])
    op.create_table(
        "marketing_campaigns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "store_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("trigger_type", sa.String(30), nullable=False),
        sa.Column("action_type", sa.String(40), nullable=False),
        sa.Column("content_mode", sa.String(20), nullable=False),
        sa.Column("template_content", sa.Text(), nullable=True),
        sa.Column("coupon_code", sa.String(100), nullable=True),
        sa.Column("trigger_delay_minutes", sa.Integer(), server_default="30", nullable=False),
        sa.Column("cooldown_hours", sa.Integer(), server_default="24", nullable=False),
        sa.Column("max_contacts_30d", sa.Integer(), server_default="3", nullable=False),
        sa.Column("status", sa.String(20), server_default="draft", nullable=False),
        sa.Column(
            "created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("trigger_type IN ('cart_abandoned','bad_review')", name="ck_marketing_campaigns_trigger"),
        sa.CheckConstraint(
            "action_type IN ('send_message','send_coupon','send_coupon_and_message')",
            name="ck_marketing_campaigns_action",
        ),
        sa.CheckConstraint("content_mode IN ('template','ai')", name="ck_marketing_campaigns_content_mode"),
        sa.CheckConstraint("status IN ('draft','active','disabled')", name="ck_marketing_campaigns_status"),
    )
    op.create_index("idx_marketing_campaigns_store_status", "marketing_campaigns", ["store_id", "status"])
    op.create_table(
        "marketing_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "store_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "campaign_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("marketing_campaigns.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "customer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customers.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("source_type", sa.String(30), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(30), server_default="pending", nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tool_call_ids", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("error_code", sa.String(100), nullable=True),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("converted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending','processing','waiting_ai','succeeded','failed','converted')",
            name="ck_marketing_events_status",
        ),
        sa.UniqueConstraint("campaign_id", "source_type", "source_id", name="uq_marketing_event_source"),
    )
    op.create_index("idx_marketing_events_due", "marketing_events", ["status", "next_attempt_at", "created_at"])
    op.create_index("idx_marketing_events_store_created", "marketing_events", ["store_id", "created_at"])


def downgrade() -> None:
    """按依赖逆序删除主动营销结构。"""
    op.drop_index("idx_marketing_events_store_created", table_name="marketing_events")
    op.drop_index("idx_marketing_events_due", table_name="marketing_events")
    op.drop_table("marketing_events")
    op.drop_index("idx_marketing_campaigns_store_status", table_name="marketing_campaigns")
    op.drop_table("marketing_campaigns")
    op.drop_index("idx_reviews_store_rating", table_name="customer_reviews")
    op.drop_table("customer_reviews")
