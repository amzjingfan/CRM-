"""Persist reviewed automatic delivery and reception timers.

Revision ID: 050_agent_reception_delivery
Revises: 049_agent_auto_reply_preview
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "050_agent_reception_delivery"
down_revision = "049_agent_auto_reply_preview"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agent_logistics_notifications",
        sa.Column("authorization_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.drop_constraint("ck_agent_tasks_status", "agent_tasks", type_="check")
    op.create_check_constraint(
        "ck_agent_tasks_status",
        "agent_tasks",
        "status IN ('pending','processing','succeeded','human_review','transferred','failed','blocked_mock',"
        "'queued','cancelled','preview_cancelled','no_suggestion')",
    )
    op.create_table(
        "automation_deliveries",
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
            "trigger_message_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("messages.id", ondelete="SET NULL")
        ),
        sa.Column("source_kind", sa.String(20), nullable=False),
        sa.Column("source_key", sa.String(200), nullable=False),
        sa.Column("part_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("message_type", sa.String(30), nullable=False, server_default="text"),
        sa.Column("card_order_id", sa.String(200)),
        sa.Column("card_package_id", sa.String(200)),
        sa.Column("agent_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_runs.id", ondelete="SET NULL")),
        sa.Column("authorized_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("policy_revision", sa.Integer(), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("mode", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("not_before", sa.DateTime(timezone=True)),
        sa.Column("authorization_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("remote_message_id", sa.String(200)),
        sa.Column("error_code", sa.String(100)),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("claim_token", postgresql.UUID(as_uuid=True)),
        sa.Column("claimed_until", sa.DateTime(timezone=True)),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "store_id",
            "conversation_id",
            "source_kind",
            "source_key",
            "part_index",
            name="uq_automation_delivery_source_part",
        ),
        sa.CheckConstraint("source_kind IN ('agent', 'welcome', 'timeout')", name="ck_automation_delivery_source"),
        sa.CheckConstraint("mode IN ('preview', 'auto')", name="ck_automation_delivery_mode"),
        sa.CheckConstraint(
            "status IN ('pending', 'claimed', 'dispatching', 'previewed', 'succeeded', "
            "'cancelled', 'failed', 'unknown')",
            name="ck_automation_delivery_status",
        ),
        sa.CheckConstraint("part_index >= 0 AND attempt_count >= 0", name="ck_automation_delivery_counts"),
    )
    op.create_index("idx_automation_delivery_due", "automation_deliveries", ["status", "not_before", "created_at"])
    for column in (
        sa.Column("content_en", sa.Text()),
        sa.Column("delivery_mode", sa.String(10), nullable=False, server_default="preview"),
        sa.Column("welcome_idle_hours", sa.Integer(), nullable=False, server_default="24"),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("authorized_by", postgresql.UUID(as_uuid=True)),
    ):
        op.add_column("reception_policies", column)
    op.create_foreign_key(
        "fk_reception_policies_authorized_by",
        "reception_policies",
        "users",
        ["authorized_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        "ck_reception_policies_delivery_mode", "reception_policies", "delivery_mode IN ('off', 'preview', 'auto')"
    )
    op.create_check_constraint(
        "ck_reception_policies_welcome_idle", "reception_policies", "welcome_idle_hours BETWEEN 1 AND 720"
    )
    op.create_check_constraint("ck_reception_policies_revision", "reception_policies", "revision >= 1")
    op.create_table(
        "reception_conversation_states",
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "store_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("segment_id", postgresql.UUID(as_uuid=True)),
        sa.Column("last_activity_at", sa.DateTime(timezone=True)),
        sa.Column("unanswered_message_id", postgresql.UUID(as_uuid=True)),
        sa.Column("unanswered_since", sa.DateTime(timezone=True)),
        sa.Column("timeout_policy_id", postgresql.UUID(as_uuid=True)),
        sa.Column("timeout_policy_revision", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    # 线上回退镜像须保留账本；有投递记录时禁止静默丢失幂等和 unknown 事实。
    if op.get_bind().execute(sa.text("SELECT EXISTS (SELECT 1 FROM automation_deliveries)")).scalar():
        raise RuntimeError("automatic delivery records must be preserved before schema downgrade")
    if (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT EXISTS (SELECT 1 FROM agent_logistics_notifications WHERE authorization_json <> '{}'::jsonb)"
            )
        )
        .scalar()
    ):
        raise RuntimeError("logistics delivery authorization records must be preserved before schema downgrade")
    if (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT EXISTS (SELECT 1 FROM agent_tasks WHERE status IN "
                "('queued','cancelled','preview_cancelled','no_suggestion'))"
            )
        )
        .scalar()
    ):
        raise RuntimeError("new Agent task states must be preserved before schema downgrade")
    op.drop_table("reception_conversation_states")
    for name in (
        "ck_reception_policies_delivery_mode",
        "ck_reception_policies_welcome_idle",
        "ck_reception_policies_revision",
    ):
        op.drop_constraint(name, "reception_policies", type_="check")
    op.drop_constraint("fk_reception_policies_authorized_by", "reception_policies", type_="foreignkey")
    for name in ("authorized_by", "revision", "welcome_idle_hours", "delivery_mode", "content_en"):
        op.drop_column("reception_policies", name)
    op.drop_index("idx_automation_delivery_due", table_name="automation_deliveries")
    op.drop_table("automation_deliveries")
    op.drop_column("agent_logistics_notifications", "authorization_json")
    op.drop_constraint("ck_agent_tasks_status", "agent_tasks", type_="check")
    op.create_check_constraint(
        "ck_agent_tasks_status",
        "agent_tasks",
        "status IN ('pending','processing','succeeded','human_review','transferred','failed','blocked_mock')",
    )
