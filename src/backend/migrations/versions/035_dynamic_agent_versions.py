"""Allow multiple enabled Agents and preserve published configuration snapshots."""

import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "035_dynamic_agent_versions"
down_revision = "034_agent_debug_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("uq_agent_configs_one_enabled_per_store", table_name="agent_configs")
    op.add_column(
        "agent_configs",
        sa.Column("draft_revision", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column("agent_configs", sa.Column("published_version", sa.Integer(), nullable=True))
    op.create_table(
        "agent_config_versions",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("store_id", sa.UUID(), sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent_config_id", sa.UUID(), sa.ForeignKey("agent_configs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("code", sa.String(100), nullable=False),
        sa.Column("description", sa.String(1000), nullable=True),
        sa.Column("agent_type", sa.String(30), nullable=False),
        sa.Column("model_provider", sa.String(50), nullable=True),
        sa.Column("model_name", sa.String(150), nullable=True),
        sa.Column("prompt_sections", JSONB(), nullable=False),
        sa.Column("prompt_hash", sa.String(64), nullable=True),
        sa.Column("tool_names", JSONB(), nullable=False),
        sa.Column("file_ids", JSONB(), nullable=False),
        sa.Column("ready_for_v2", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("published_by", sa.UUID(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("agent_config_id", "version", name="uq_agent_config_versions_number"),
    )
    op.create_index("idx_agent_config_versions_store_config", "agent_config_versions", ["store_id", "agent_config_id"])

    # 旧配置只具备固定运行 Prompt，回填为不可被 V2 直接执行的兼容快照。
    connection = op.get_bind()
    versions = sa.table(
        "agent_config_versions",
        sa.column("id", sa.UUID()),
        sa.column("store_id", sa.UUID()),
        sa.column("agent_config_id", sa.UUID()),
        sa.column("version", sa.Integer()),
        sa.column("name", sa.String()),
        sa.column("code", sa.String()),
        sa.column("description", sa.String()),
        sa.column("agent_type", sa.String()),
        sa.column("model_provider", sa.String()),
        sa.column("model_name", sa.String()),
        sa.column("prompt_sections", JSONB()),
        sa.column("prompt_hash", sa.String()),
        sa.column("tool_names", JSONB()),
        sa.column("file_ids", JSONB()),
        sa.column("ready_for_v2", sa.Boolean()),
        sa.column("published_by", sa.UUID()),
        sa.column("published_at", sa.DateTime(timezone=True)),
    )
    rows = connection.execute(
        sa.text(
            "SELECT id, store_id, name, code, description, enabled_tools, knowledge_scope, created_by "
            "FROM agent_configs"
        )
    ).mappings()
    now = datetime.now(UTC)
    for row in rows:
        scope = row["knowledge_scope"] if isinstance(row["knowledge_scope"], dict) else {}
        file_ids = scope.get("file_ids") if isinstance(scope.get("file_ids"), list) else []
        tool_names = row["enabled_tools"] if isinstance(row["enabled_tools"], list) else []
        connection.execute(
            versions.insert().values(
                id=uuid.uuid4(),
                store_id=row["store_id"],
                agent_config_id=row["id"],
                version=1,
                name=row["name"],
                code=row["code"],
                description=row["description"],
                agent_type=scope.get("agent_type", "service"),
                model_provider=None,
                model_name=None,
                prompt_sections={},
                prompt_hash=None,
                tool_names=tool_names,
                file_ids=file_ids,
                ready_for_v2=False,
                published_by=row["created_by"],
                published_at=now,
            )
        )
    connection.execute(sa.text("UPDATE agent_configs SET published_version = 1"))


def downgrade() -> None:
    connection = op.get_bind()
    if connection.scalar(
        sa.text("SELECT EXISTS (SELECT 1 FROM agent_config_versions WHERE ready_for_v2 = true OR version <> 1)")
    ):
        raise RuntimeError("已有新版 Agent 配置，不能无损降级；请从部署备份恢复")
    if connection.scalar(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM agent_configs GROUP BY store_id "
            "HAVING count(*) FILTER (WHERE status = 'enabled' AND deleted_at IS NULL) > 1)"
        )
    ):
        raise RuntimeError("同店已有多个启用 Agent，不能恢复旧唯一索引")
    op.drop_index("idx_agent_config_versions_store_config", table_name="agent_config_versions")
    op.drop_table("agent_config_versions")
    op.drop_column("agent_configs", "published_version")
    op.drop_column("agent_configs", "draft_revision")
    op.create_index(
        "uq_agent_configs_one_enabled_per_store",
        "agent_configs",
        ["store_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL AND status = 'enabled'"),
    )
