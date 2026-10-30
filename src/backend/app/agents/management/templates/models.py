"""模板与已确认批次的持久结构；执行器以 token 和 revision 防止迟到写入。"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database.base import Base, TimestampMixin


class AgentTemplate(TimestampMixin, Base):
    """系统级通用模板；归档只阻止新应用，不修改已有 Agent。"""

    __tablename__ = "agent_templates"
    __table_args__ = (
        UniqueConstraint("code", name="uq_agent_templates_code"),
        CheckConstraint("draft_revision > 0", name="ck_agent_templates_revision_positive"),
        CheckConstraint(
            "published_version IS NULL OR published_version > 0", name="ck_agent_templates_version_positive"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(100), default=lambda: uuid.uuid4().hex, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    draft_revision: Mapped[int] = mapped_column(Integer, default=1, server_default="1", nullable=False)
    draft_config_json: Mapped[dict[str, object]] = mapped_column(
        JSONB, default=dict, server_default="{}", nullable=False
    )
    published_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class AgentTemplateVersion(Base):
    """模板版本只新增；数据库触发器拒绝对已发布快照的更新。"""

    __tablename__ = "agent_template_versions"
    __table_args__ = (
        UniqueConstraint("template_id", "version", name="uq_agent_template_versions_number"),
        CheckConstraint("version > 0", name="ck_agent_template_versions_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agent_templates.id", ondelete="CASCADE"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    config_json: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    published_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AgentTemplateBatch(TimestampMixin, Base):
    """预览、确认与执行共用一批次，确认前幂等键为空。"""

    __tablename__ = "agent_template_batches"
    __table_args__ = (
        UniqueConstraint("created_by", "idempotency_key", name="uq_agent_template_batches_creator_key"),
        ForeignKeyConstraint(
            ["template_id", "template_version"],
            ["agent_template_versions.template_id", "agent_template_versions.version"],
            name="fk_agent_template_batches_version",
            ondelete="RESTRICT",
        ),
        Index("idx_agent_template_batches_status", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agent_templates.id", ondelete="RESTRICT"), nullable=False
    )
    template_version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    confirmed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    parent_batch_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agent_template_batches.id", ondelete="RESTRICT"), nullable=True
    )
    mode: Mapped[str] = mapped_column(String(30), default="save_draft", server_default="save_draft", nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="preview", server_default="preview", nullable=False)
    preview_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict, server_default="{}", nullable=False)
    preview_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    confirmation_json: Mapped[dict[str, object]] = mapped_column(
        JSONB, default=dict, server_default="{}", nullable=False
    )
    confirmation_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"), nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AgentTemplateBatchItem(TimestampMixin, Base):
    """逐店完整快照、乐观锁、租约及同事务结果台账。"""

    __tablename__ = "agent_template_batch_items"
    __table_args__ = (
        UniqueConstraint("batch_id", "store_id", name="uq_agent_template_batch_items_store"),
        CheckConstraint("attempt_count >= 0", name="ck_agent_template_batch_items_attempts"),
        Index("idx_agent_template_batch_items_claim", "status", "lease_expires_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    batch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agent_template_batches.id", ondelete="CASCADE"), nullable=False
    )
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stores.id", ondelete="RESTRICT"), nullable=False)
    requested_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    agent_config_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agent_configs.id", ondelete="RESTRICT"), nullable=True
    )
    expected_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expected_published_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expected_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    field_choices_json: Mapped[dict[str, object]] = mapped_column(
        JSONB, default=dict, server_default="{}", nullable=False
    )
    knowledge_mapping_json: Mapped[dict[str, object]] = mapped_column(
        JSONB, default=dict, server_default="{}", nullable=False
    )
    target_config_json: Mapped[dict[str, object]] = mapped_column(
        JSONB, default=dict, server_default="{}", nullable=False
    )
    target_config_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    attempt_token: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="pending", server_default="pending", nullable=False)
    result_agent_config_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agent_configs.id", ondelete="RESTRICT"), nullable=True
    )
    result_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    result_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict, server_default="{}", nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
