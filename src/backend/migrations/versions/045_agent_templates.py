"""通用 Agent 模板、不可变版本与持久逐店应用批次。"""

from datetime import datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "045_agent_templates"
down_revision = "044_reception_assignment"
branch_labels = None
depends_on = None


def _timestamps() -> list[sa.Column[datetime]]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def _json(name: str) -> sa.Column[dict[str, object]]:
    return sa.Column(name, postgresql.JSONB(), server_default="{}", nullable=False)


def upgrade() -> None:
    """不自动关联旧 Agent；模板和预览不会改变运行版本。"""
    op.create_table(
        "agent_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(100), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.String(1000), nullable=True),
        sa.Column("draft_revision", sa.Integer(), server_default="1", nullable=False),
        _json("draft_config_json"),
        sa.Column("published_version", sa.Integer(), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        *_timestamps(),
        sa.UniqueConstraint("code", name="uq_agent_templates_code"),
        sa.CheckConstraint("draft_revision > 0", name="ck_agent_templates_revision_positive"),
        sa.CheckConstraint(
            "published_version IS NULL OR published_version > 0", name="ck_agent_templates_version_positive"
        ),
    )
    op.create_table(
        "agent_template_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "template_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agent_templates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("config_json", postgresql.JSONB(), nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("published_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("published_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("template_id", "version", name="uq_agent_template_versions_number"),
        sa.CheckConstraint("version > 0", name="ck_agent_template_versions_positive"),
    )
    op.add_column("agent_configs", sa.Column("template_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_agent_configs_template_id", "agent_configs", "agent_templates", ["template_id"], ["id"], ondelete="RESTRICT"
    )
    op.add_column("agent_configs", sa.Column("template_state_json", postgresql.JSONB(), nullable=True))
    op.create_index(
        "uq_agent_configs_store_template_active",
        "agent_configs",
        ["store_id", "template_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL AND template_id IS NOT NULL"),
    )
    op.add_column("agent_config_versions", sa.Column("template_source_json", postgresql.JSONB(), nullable=True))
    op.create_table(
        "agent_template_batches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "template_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agent_templates.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("template_version", sa.Integer(), nullable=False),
        sa.Column(
            "created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("confirmed_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column(
            "parent_batch_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agent_template_batches.id", ondelete="RESTRICT"),
        ),
        sa.Column("mode", sa.String(30), server_default="save_draft", nullable=False),
        sa.Column("status", sa.String(30), server_default="preview", nullable=False),
        _json("preview_json"),
        sa.Column("preview_hash", sa.String(64), nullable=True),
        _json("confirmation_json"),
        sa.Column("confirmation_hash", sa.String(64), nullable=True),
        sa.Column("idempotency_key", sa.String(200), nullable=True),
        sa.Column("cancel_requested", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("created_by", "idempotency_key", name="uq_agent_template_batches_creator_key"),
        sa.ForeignKeyConstraint(
            ["template_id", "template_version"],
            ["agent_template_versions.template_id", "agent_template_versions.version"],
            name="fk_agent_template_batches_version",
            ondelete="RESTRICT",
        ),
    )
    op.create_index("idx_agent_template_batches_status", "agent_template_batches", ["status", "created_at"])
    op.create_table(
        "agent_template_batch_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "batch_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agent_template_batches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "store_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("stores.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("requested_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column(
            "agent_config_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_configs.id", ondelete="RESTRICT")
        ),
        sa.Column("expected_revision", sa.Integer(), nullable=True),
        sa.Column("expected_published_version", sa.Integer(), nullable=True),
        sa.Column("expected_status", sa.String(20), nullable=True),
        _json("field_choices_json"),
        _json("knowledge_mapping_json"),
        _json("target_config_json"),
        sa.Column("target_config_hash", sa.String(64), nullable=True),
        sa.Column("attempt_token", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("status", sa.String(30), server_default="pending", nullable=False),
        sa.Column(
            "result_agent_config_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agent_configs.id", ondelete="RESTRICT"),
        ),
        sa.Column("result_version", sa.Integer(), nullable=True),
        _json("result_json"),
        sa.Column("error_code", sa.String(100), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("batch_id", "store_id", name="uq_agent_template_batch_items_store"),
        sa.CheckConstraint("attempt_count >= 0", name="ck_agent_template_batch_items_attempts"),
    )
    op.create_index(
        "idx_agent_template_batch_items_claim",
        "agent_template_batch_items",
        ["status", "lease_expires_at", "created_at"],
    )
    # 作者外键允许用户删除时置空，配置和版本标识本身永不原位重写。
    op.execute("""
        CREATE FUNCTION agent_template_version_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'agent template versions are immutable' USING ERRCODE = '23514';
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER trg_agent_template_version_immutable
        BEFORE UPDATE OF id, template_id, version, config_json, content_sha256, published_at
        ON agent_template_versions FOR EACH ROW EXECUTE FUNCTION agent_template_version_immutable()
    """)


def downgrade() -> None:
    """仅空结构可无损降级；已有模板、来源或批次时要求先备份恢复。"""
    has_data = op.get_bind().scalar(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM agent_templates) "
            "OR EXISTS (SELECT 1 FROM agent_template_batches) "
            "OR EXISTS (SELECT 1 FROM agent_template_batch_items) "
            "OR EXISTS (SELECT 1 FROM agent_configs WHERE template_id IS NOT NULL OR template_state_json IS NOT NULL) "
            "OR EXISTS (SELECT 1 FROM agent_config_versions WHERE template_source_json IS NOT NULL)"
        )
    )
    if has_data:
        raise RuntimeError("已有模板、批次或 Agent 来源事实，不能无损降级；请使用部署备份恢复")
    op.drop_table("agent_template_batch_items")
    op.drop_table("agent_template_batches")
    op.drop_column("agent_config_versions", "template_source_json")
    op.drop_index("uq_agent_configs_store_template_active", table_name="agent_configs")
    op.drop_column("agent_configs", "template_state_json")
    op.drop_constraint("fk_agent_configs_template_id", "agent_configs", type_="foreignkey")
    op.drop_column("agent_configs", "template_id")
    op.drop_table("agent_template_versions")
    op.execute("DROP FUNCTION agent_template_version_immutable()")
    op.drop_table("agent_templates")
