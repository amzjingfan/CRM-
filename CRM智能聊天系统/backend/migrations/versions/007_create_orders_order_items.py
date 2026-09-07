"""创建订单和订单商品表。"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "007_orders_items"
down_revision = "006_workspace"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """创建客服快捷查询所需的订单数据结构。"""
    op.create_table(
        "orders",
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
        sa.Column("platform", sa.String(30), nullable=False),
        sa.Column("external_order_id", sa.String(200), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("payment_status", sa.String(30), nullable=True),
        sa.Column("fulfillment_status", sa.String(30), nullable=True),
        sa.Column("currency", sa.String(10), nullable=False),
        sa.Column("total_amount", sa.Numeric(18, 2), server_default="0", nullable=False),
        sa.Column("shipping_address", postgresql.JSONB(), nullable=True),
        sa.Column("tracking_number", sa.String(200), nullable=True),
        sa.Column("tracking_status", sa.String(100), nullable=True),
        sa.Column("ordered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("shipped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("store_id", "platform", "external_order_id", name="uq_order_store_platform_external"),
    )
    op.create_index("idx_orders_store_external", "orders", ["store_id", "external_order_id"])
    op.create_index("idx_orders_customer_created", "orders", ["customer_id", "created_at"])
    op.create_table(
        "order_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("external_item_id", sa.String(200), nullable=True),
        sa.Column("product_id", sa.String(200), nullable=True),
        sa.Column("sku", sa.String(200), nullable=True),
        sa.Column("product_name", sa.String(500), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(18, 2), nullable=False),
        sa.Column("total_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("raw_payload", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_order_items_order", "order_items", ["order_id"])


def downgrade() -> None:
    """删除订单商品和订单表。"""
    op.drop_index("idx_order_items_order", table_name="order_items")
    op.drop_table("order_items")
    op.drop_index("idx_orders_customer_created", table_name="orders")
    op.drop_index("idx_orders_store_external", table_name="orders")
    op.drop_table("orders")
