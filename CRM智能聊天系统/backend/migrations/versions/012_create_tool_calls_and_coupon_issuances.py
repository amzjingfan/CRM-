"""创建受控工具调用和优惠券发放记录。"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "012_tool_calls"
down_revision = "011_knowledge_base"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """建立人、Agent 和任务共用的安全工具执行审计基础。"""
    op.create_table(
        "tool_calls",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "store_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "agent_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agent_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("actor_type", sa.String(20), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("tool_name", sa.String(100), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("input_summary", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("output_summary", postgresql.JSONB(), nullable=True),
        sa.Column("error_code", sa.String(100), nullable=True),
        sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("trace_id", sa.String(100), nullable=True),
        sa.Column("mocked", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("actor_type IN ('user','agent','job')", name="ck_tool_calls_actor_type"),
        sa.CheckConstraint(
            "status IN ('pending','running','succeeded','failed','timeout','unknown')", name="ck_tool_calls_status"
        ),
        sa.UniqueConstraint("store_id", "idempotency_key", name="uq_tool_call_store_idempotency"),
    )
    op.create_index("idx_tool_calls_agent_created", "tool_calls", ["agent_run_id", "created_at"])
    op.create_index("idx_tool_calls_store_created", "tool_calls", ["store_id", "created_at"])
    op.create_table(
        "coupon_issuances",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "store_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "customer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tool_call_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tool_calls.id", ondelete="RESTRICT"),
            nullable=False,
            unique=True,
        ),
        sa.Column("coupon_code", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(30), server_default="issued", nullable=False),
        sa.Column("mocked", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("external_reference", sa.String(200), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_coupon_customer_created", "coupon_issuances", ["customer_id", "created_at"])


def downgrade() -> None:
    """删除优惠券和工具调用表。"""
    op.drop_index("idx_coupon_customer_created", table_name="coupon_issuances")
    op.drop_table("coupon_issuances")
    op.drop_index("idx_tool_calls_store_created", table_name="tool_calls")
    op.drop_index("idx_tool_calls_agent_created", table_name="tool_calls")
    op.drop_table("tool_calls")
