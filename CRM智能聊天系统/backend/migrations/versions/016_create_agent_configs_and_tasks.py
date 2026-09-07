"""创建 Agent 运营配置和可靠自动处理任务。"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "016_agent_ops"
down_revision = "015_vector_ops"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """增加不修改 AI 工作流内部实现的全栈运营控制面。"""
    op.create_table(
        "agent_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "store_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("stores.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("code", sa.String(100), nullable=False),
        sa.Column("description", sa.String(1000), nullable=True),
        sa.Column("status", sa.String(20), server_default="disabled", nullable=False),
        sa.Column("enabled_tools", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column(
            "knowledge_scope",
            postgresql.JSONB(),
            server_default=sa.text('\'{"mode": "store_ready_faq"}\'::jsonb'),
            nullable=False,
        ),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('enabled','disabled')", name="ck_agent_configs_status"),
    )
    active_config = sa.text("deleted_at IS NULL")
    enabled_config = sa.text("deleted_at IS NULL AND status = 'enabled'")
    op.create_index(
        "uq_agent_configs_store_code_active",
        "agent_configs",
        ["store_id", "code"],
        unique=True,
        postgresql_where=active_config,
    )
    op.create_index(
        "uq_agent_configs_one_enabled_per_store",
        "agent_configs",
        ["store_id"],
        unique=True,
        postgresql_where=enabled_config,
    )
    op.create_index("idx_agent_configs_store_status", "agent_configs", ["store_id", "status"])

    op.add_column(
        "agent_runs",
        sa.Column("agent_config_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_agent_runs_config",
        "agent_runs",
        "agent_configs",
        ["agent_config_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("idx_agent_runs_config_created", "agent_runs", ["agent_config_id", "created_at"])

    op.create_table(
        "agent_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "store_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("stores.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "agent_config_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agent_configs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "trigger_message_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("messages.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "agent_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agent_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("status", sa.String(30), server_default="pending", nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result_action", sa.String(30), nullable=True),
        sa.Column("error_code", sa.String(100), nullable=True),
        sa.Column("trace_id", sa.String(100), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending','processing','succeeded','human_review','transferred','failed','blocked_mock')",
            name="ck_agent_tasks_status",
        ),
    )
    op.create_index(
        "idx_agent_tasks_due",
        "agent_tasks",
        ["status", "next_attempt_at", "created_at"],
    )
    op.create_index("idx_agent_tasks_store_created", "agent_tasks", ["store_id", "created_at"])


def downgrade() -> None:
    """按依赖逆序移除 Phase 4 Agent 运营结构。"""
    op.drop_index("idx_agent_tasks_store_created", table_name="agent_tasks")
    op.drop_index("idx_agent_tasks_due", table_name="agent_tasks")
    op.drop_table("agent_tasks")
    op.drop_index("idx_agent_runs_config_created", table_name="agent_runs")
    op.drop_constraint("fk_agent_runs_config", "agent_runs", type_="foreignkey")
    op.drop_column("agent_runs", "agent_config_id")
    op.drop_index("idx_agent_configs_store_status", table_name="agent_configs")
    op.drop_index("uq_agent_configs_one_enabled_per_store", table_name="agent_configs")
    op.drop_index("uq_agent_configs_store_code_active", table_name="agent_configs")
    op.drop_table("agent_configs")
