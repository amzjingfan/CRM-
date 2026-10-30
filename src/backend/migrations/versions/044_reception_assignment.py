"""单客服部接待资格、在线证据和会话自动分配元数据。"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "044_reception_assignment"
down_revision = "043_logistics_updates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """只增加默认关闭的配置和空值列，不重写任何历史会话。"""
    op.create_table(
        "reception_store_configs",
        sa.Column(
            "store_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("stores.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column(
            "department_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("departments.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "reception_agent_configs",
        sa.Column(
            "store_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("stores.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("auto_enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("accepting", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("capacity", sa.Integer(), server_default="20", nullable=False),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_assigned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("capacity BETWEEN 1 AND 1000", name="ck_reception_agent_capacity"),
    )
    op.add_column("conversations", sa.Column("assignment_source", sa.String(20), nullable=True))
    op.add_column("conversations", sa.Column("assignment_wait_reason", sa.String(32), nullable=True))
    op.add_column("conversations", sa.Column("awaiting_reply_since", sa.DateTime(timezone=True), nullable=True))
    op.add_column("conversations", sa.Column("next_assignment_attempt_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "conversations",
        sa.Column(
            "last_human_responder_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column("conversations", sa.Column("last_human_replied_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(
        "ix_conversations_reception_queue",
        "conversations",
        ["store_id", "assigned_user_id", "next_assignment_attempt_at", "awaiting_reply_since"],
    )


def downgrade() -> None:
    """已有接待配置或派单事实时要求备份恢复，避免无声丢失。"""
    connection = op.get_bind()
    has_new_data = connection.scalar(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM reception_store_configs) "
            "OR EXISTS (SELECT 1 FROM reception_agent_configs) "
            "OR EXISTS (SELECT 1 FROM conversations WHERE assignment_source IS NOT NULL "
            "OR assignment_wait_reason IS NOT NULL OR awaiting_reply_since IS NOT NULL "
            "OR next_assignment_attempt_at IS NOT NULL "
            "OR last_human_responder_id IS NOT NULL "
            "OR last_human_replied_at IS NOT NULL)"
        )
    )
    if has_new_data:
        raise RuntimeError("已有接待配置或派单事实，不能无损降级；请使用部署备份恢复")
    op.drop_index("ix_conversations_reception_queue", table_name="conversations")
    op.drop_column("conversations", "last_human_replied_at")
    op.drop_column("conversations", "last_human_responder_id")
    op.drop_column("conversations", "awaiting_reply_since")
    op.drop_column("conversations", "next_assignment_attempt_at")
    op.drop_column("conversations", "assignment_source")
    op.drop_column("conversations", "assignment_wait_reason")
    op.drop_table("reception_agent_configs")
    op.drop_table("reception_store_configs")
