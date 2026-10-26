"""通用文件导入的版本、解析单元和独立向量模型。"""

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database.base import Base, TimestampMixin


class KnowledgeFile(TimestampMixin, Base):
    """店铺内一个逻辑文件；有效版本仅在整个新版本完成后切换。"""

    __tablename__ = "knowledge_files"
    __table_args__ = (
        Index(
            "uq_knowledge_files_store_filename_active",
            "store_id",
            "filename_key",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), nullable=False, index=True)
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("knowledge_categories.id", ondelete="SET NULL"), nullable=True
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    filename_key: Mapped[str] = mapped_column(String(255), nullable=False)
    active_version_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class KnowledgeFileVersion(TimestampMixin, Base):
    """一次不可变来源与处理配置，包含整版本状态和 Worker 租约。"""

    __tablename__ = "knowledge_file_versions"
    __table_args__ = (
        UniqueConstraint("file_id", "version_number", name="uq_knowledge_file_version_number"),
        CheckConstraint(
            "status IN ('queued', 'parsing', 'review_required', 'indexing', 'ready', "
            "'failed_retryable', 'failed_final')",
            name="ck_knowledge_file_version_status",
        ),
        Index("ix_knowledge_file_version_claim", "status", "lease_until", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), nullable=False, index=True)
    file_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("knowledge_files.id", ondelete="CASCADE"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    source_object_key: Mapped[str] = mapped_column(String(500), nullable=False)
    file_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    media_type: Mapped[str] = mapped_column(String(100), nullable=False)
    config_json: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="queued")
    parser_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    cleaning_version: Mapped[str] = mapped_column(String(30), nullable=False, default="clean-v1")
    lease_owner: Mapped[str | None] = mapped_column(String(100), nullable=True)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    publication_approval: Mapped[str] = mapped_column(String(40), nullable=False, default="draft")
    statement_type: Mapped[str] = mapped_column(String(40), nullable=False, default="unknown")
    customer_scope: Mapped[str] = mapped_column(String(40), nullable=False, default="none")
    approved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class KnowledgeFileImportReceipt(Base):
    """每个已受理幂等键的永久映射，包括命中旧版本的重复上传。"""

    __tablename__ = "knowledge_file_import_receipts"
    __table_args__ = (
        UniqueConstraint("store_id", "created_by", "idempotency_key_hash", name="uq_knowledge_file_import_receipt_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_file_versions.id", ondelete="CASCADE"), nullable=False
    )
    idempotency_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class KnowledgeFileUnit(Base):
    """页、幻灯片、工作表或图像单元；人工修订不覆盖原始解析内容。"""

    __tablename__ = "knowledge_file_units"
    __table_args__ = (UniqueConstraint("version_id", "unit_index", name="uq_knowledge_file_unit_index"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), nullable=False, index=True)
    version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_file_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    unit_index: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_kind: Mapped[str] = mapped_column(String(30), nullable=False)
    source_locator: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    blocks_json: Mapped[list[dict[str, object]]] = mapped_column(JSONB, nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    cleaned_text: Mapped[str] = mapped_column(Text, nullable=False)
    issue_codes: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    parse_mode: Mapped[str] = mapped_column(String(30), nullable=False)
    needs_review: Mapped[bool] = mapped_column(nullable=False, default=False)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class KnowledgeFileChunk(Base):
    """与现有 FAQ `knowledge_chunks` 隔离的 1024 维文档向量。"""

    __tablename__ = "knowledge_file_chunks"
    __table_args__ = (UniqueConstraint("version_id", "chunk_index", name="uq_knowledge_file_chunk_index"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), nullable=False, index=True)
    file_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("knowledge_files.id", ondelete="CASCADE"), nullable=False)
    version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_file_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    unit_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    strategy: Mapped[str] = mapped_column(String(40), nullable=False)
    heading_path: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    source_locator: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    parser_version: Mapped[str] = mapped_column(String(50), nullable=False)
    cleaning_version: Mapped[str] = mapped_column(String(30), nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(100), nullable=False)
    embedding_revision: Mapped[str] = mapped_column(String(100), nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(1024), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class KnowledgeFileSettings(Base):
    """当前店铺未来导入任务的默认值；既有版本配置始终取自身快照。"""

    __tablename__ = "knowledge_file_settings"

    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), primary_key=True)
    strategy: Mapped[str] = mapped_column(String(40), nullable=False, default="recursive")
    chunk_size: Mapped[int] = mapped_column(Integer, nullable=False, default=500)
    overlap: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    parser_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="auto")
    embedding_model: Mapped[str] = mapped_column(String(100), nullable=False, default="BAAI/bge-m3")
    updated_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
