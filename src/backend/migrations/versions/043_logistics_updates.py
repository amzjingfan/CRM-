"""persist independent logistics notification policy and observation ledger

Revision ID: 043_logistics_updates
Revises: 042_agent_reply_delivery
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "043_logistics_updates"
down_revision = "042_agent_reply_delivery"
branch_labels = None
depends_on = None


def _timestamps() -> list[sa.Column[sa.DateTime]]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "agent_logistics_observations",
        sa.Column("scope_key", sa.String(64), primary_key=True),
        sa.Column("store_id", sa.UUID(), sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", sa.UUID(), sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order_id", sa.UUID(), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("package_id", sa.String(200), nullable=False),
        sa.Column("latest_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("latest_fingerprint", sa.String(64), nullable=False),
        *_timestamps(),
    )
    op.create_index(
        "idx_agent_logistics_observations_store_order", "agent_logistics_observations", ["store_id", "order_id"]
    )
    op.create_table(
        "agent_logistics_notifications",
        sa.Column("idempotency_key", sa.String(80), primary_key=True),
        sa.Column(
            "scope_key",
            sa.String(64),
            sa.ForeignKey("agent_logistics_observations.scope_key", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("store_id", sa.UUID(), sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", sa.UUID(), sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("conversation_id", sa.UUID(), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order_id", sa.UUID(), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("context_json", JSONB(), nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("reason", sa.String(80)),
        sa.Column("reviewed_text", sa.Text()),
        sa.Column("mode", sa.String(20), nullable=False),
        sa.Column("delivery_reference", sa.String(200)),
        sa.Column("review_claim_token", sa.UUID()),
        sa.Column("review_lease_expires_at", sa.DateTime(timezone=True)),
        *_timestamps(),
    )
    op.create_index(
        "idx_agent_logistics_notifications_store_state", "agent_logistics_notifications", ["store_id", "state"]
    )
    op.create_index(
        "idx_agent_logistics_notifications_scope", "agent_logistics_notifications", ["store_id", "scope_key"]
    )
    op.create_index(
        "idx_agent_logistics_notifications_recovery",
        "agent_logistics_notifications",
        ["state", "review_lease_expires_at"],
    )
    op.create_table(
        "agent_logistics_notification_policies",
        sa.Column("store_id", sa.UUID(), sa.ForeignKey("stores.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("agent_id", sa.UUID(), sa.ForeignKey("agent_configs.id", ondelete="SET NULL")),
        sa.Column("authorized_by", sa.UUID(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("mode", sa.String(20), nullable=False, server_default="preview"),
        sa.Column("enabled_at", sa.DateTime(timezone=True)),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_scan_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("mode IN ('preview', 'external')", name="ck_logistics_policy_mode"),
        sa.CheckConstraint("NOT enabled OR enabled_at IS NOT NULL", name="ck_logistics_policy_enabled_cutoff"),
    )
    op.create_table(
        "agent_logistics_order_scans",
        sa.Column("store_id", sa.UUID(), sa.ForeignKey("stores.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("order_id", sa.UUID(), sa.ForeignKey("orders.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("next_poll_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claimed_until", sa.DateTime(timezone=True)),
        sa.Column("claim_token", sa.UUID()),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_polled_at", sa.DateTime(timezone=True)),
        sa.Column("last_reason", sa.String(80)),
    )
    op.create_index("idx_logistics_order_scans_due", "agent_logistics_order_scans", ["next_poll_at", "claimed_until"])


def downgrade() -> None:
    op.drop_index("idx_logistics_order_scans_due", table_name="agent_logistics_order_scans")
    op.drop_table("agent_logistics_order_scans")
    op.drop_table("agent_logistics_notification_policies")
    op.drop_index("idx_agent_logistics_notifications_recovery", table_name="agent_logistics_notifications")
    op.drop_index("idx_agent_logistics_notifications_scope", table_name="agent_logistics_notifications")
    op.drop_index("idx_agent_logistics_notifications_store_state", table_name="agent_logistics_notifications")
    op.drop_table("agent_logistics_notifications")
    op.drop_index("idx_agent_logistics_observations_store_order", table_name="agent_logistics_observations")
    op.drop_table("agent_logistics_observations")
