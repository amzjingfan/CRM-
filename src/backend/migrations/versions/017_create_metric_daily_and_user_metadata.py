"""创建每日指标并补充用户登录时间。"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "017_phase4_metrics"
down_revision = "016_agent_ops"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """增加可回填的店铺级运营指标。"""
    op.add_column("users", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "metric_daily",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "store_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("stores.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("metric_date", sa.Date(), nullable=False),
        sa.Column("aggregation_timezone", sa.String(50), nullable=False),
        sa.Column("aggregation_version", sa.String(30), server_default="v1", nullable=False),
        sa.Column("session_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("message_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("agent_run_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("ai_reply_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("transfer_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("response_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("transfer_rate", sa.Numeric(7, 4), server_default="0", nullable=False),
        sa.Column("avg_response_ms", sa.Integer(), nullable=True),
        sa.Column("recovered_gmv", sa.Numeric(18, 2), server_default="0", nullable=False),
        sa.Column("channel_breakdown", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("intent_breakdown", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("store_id", "metric_date", name="uq_metric_daily_store_date"),
        sa.CheckConstraint("session_count >= 0", name="ck_metric_daily_sessions"),
        sa.CheckConstraint("message_count >= 0", name="ck_metric_daily_messages"),
        sa.CheckConstraint("response_count >= 0", name="ck_metric_daily_responses"),
        sa.CheckConstraint("transfer_rate >= 0 AND transfer_rate <= 1", name="ck_metric_daily_transfer_rate"),
    )
    op.create_index("idx_metric_daily_store_date", "metric_daily", ["store_id", "metric_date"])
    op.create_index("idx_messages_store_created", "messages", ["store_id", "created_at"])
    op.create_index("idx_marketing_events_store_converted", "marketing_events", ["store_id", "converted_at"])


def downgrade() -> None:
    """移除派生指标，不影响消息、Agent 和营销事实数据。"""
    op.drop_index("idx_marketing_events_store_converted", table_name="marketing_events")
    op.drop_index("idx_messages_store_created", table_name="messages")
    op.drop_index("idx_metric_daily_store_date", table_name="metric_daily")
    op.drop_table("metric_daily")
    op.drop_column("users", "last_login_at")
