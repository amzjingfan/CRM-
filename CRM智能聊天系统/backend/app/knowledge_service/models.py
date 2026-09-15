"""公司级知识服务 K2 权威数据模型。"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.knowledge_service.database import KnowledgeBase


def uuid_primary_key() -> Mapped[uuid.UUID]:
    """统一使用应用端 UUID，不依赖 CRM sequence。"""
    return mapped_column(primary_key=True, default=uuid.uuid4)


class KnowledgeApplication(KnowledgeBase):
    """获准调用知识服务的内部应用。"""

    __tablename__ = "kb_applications"

    application_ref: Mapped[str] = mapped_column(String(96), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(160))
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ApplicationSpaceGrant(KnowledgeBase):
    """应用级空间白名单。"""

    __tablename__ = "kb_application_space_grants"
    __table_args__ = (
        UniqueConstraint(
            "application_ref",
            "platform_code",
            "market_code",
            "language_tag",
            "audience_code",
            "space_code",
            name="uq_kb_application_space_grant",
        ),
        CheckConstraint("space_code IN ('company_shared', 'shop_private')", name="ck_kb_application_space_code"),
    )

    id: Mapped[uuid.UUID] = uuid_primary_key()
    application_ref: Mapped[str] = mapped_column(ForeignKey("kb_applications.application_ref"), index=True)
    platform_code: Mapped[str] = mapped_column(String(32))
    market_code: Mapped[str] = mapped_column(String(16))
    language_tag: Mapped[str] = mapped_column(String(32))
    audience_code: Mapped[str] = mapped_column(String(64))
    space_code: Mapped[str] = mapped_column(String(32))
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ShopSpaceGrant(KnowledgeBase):
    """应用对稳定低敏店铺代号的私有空间授权。"""

    __tablename__ = "kb_shop_space_grants"
    __table_args__ = (
        UniqueConstraint("application_ref", "shop_ref", "space_code", name="uq_kb_shop_space_grant"),
        CheckConstraint("space_code = 'shop_private'", name="ck_kb_shop_private_only"),
    )

    id: Mapped[uuid.UUID] = uuid_primary_key()
    application_ref: Mapped[str] = mapped_column(ForeignKey("kb_applications.application_ref"), index=True)
    shop_ref: Mapped[str] = mapped_column(String(128), index=True)
    space_code: Mapped[str] = mapped_column(String(32), default="shop_private")
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class RevokedCredential(KnowledgeBase):
    """服务 Token 和委托 Token 撤销列表，只保存 JTI 哈希。"""

    __tablename__ = "kb_revoked_credentials"
    __table_args__ = (UniqueConstraint("issuer", "jti_hash", name="uq_kb_revoked_credential"),)

    id: Mapped[uuid.UUID] = uuid_primary_key()
    issuer: Mapped[str] = mapped_column(String(128))
    jti_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reason_code: Mapped[str] = mapped_column(String(64))


class CoverageCell(KnowledgeBase):
    """领域、平台、市场、语言、读者和空间的稳定覆盖单元。"""

    __tablename__ = "kb_coverage_cells"
    __table_args__ = (
        CheckConstraint(
            "(space_code = 'company_shared' AND shop_ref IS NULL) OR "
            "(space_code = 'shop_private' AND shop_ref IS NOT NULL)",
            name="ck_kb_coverage_space_shop",
        ),
        Index(
            "uq_kb_coverage_dimensions",
            "domain_code",
            "platform_code",
            "market_code",
            "language_tag",
            "audience_code",
            "space_code",
            "shop_ref",
            unique=True,
            postgresql_nulls_not_distinct=True,
        ),
    )

    id: Mapped[uuid.UUID] = uuid_primary_key()
    coverage_cell_ref: Mapped[str] = mapped_column(String(160), unique=True)
    domain_code: Mapped[str] = mapped_column(String(64))
    platform_code: Mapped[str] = mapped_column(String(32))
    market_code: Mapped[str] = mapped_column(String(16))
    language_tag: Mapped[str] = mapped_column(String(32))
    audience_code: Mapped[str] = mapped_column(String(64))
    space_code: Mapped[str] = mapped_column(String(32))
    shop_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    knowledge_shape: Mapped[str] = mapped_column(String(8))
    coverage_status: Mapped[str] = mapped_column(String(32))
    content_owner_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    review_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    evaluation_set_ref: Mapped[str | None] = mapped_column(String(256), nullable=True)
    gap_reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class KnowledgeSource(KnowledgeBase):
    """来源与使用权元数据；原文放于受控对象存储。"""

    __tablename__ = "kb_sources"

    id: Mapped[uuid.UUID] = uuid_primary_key()
    source_ref: Mapped[str] = mapped_column(String(160), unique=True)
    publisher: Mapped[str] = mapped_column(String(200))
    source_type: Mapped[str] = mapped_column(String(48))
    source_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    object_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    source_market: Mapped[str] = mapped_column(String(16))
    source_language: Mapped[str] = mapped_column(String(32))
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    rights_basis_ref: Mapped[str] = mapped_column(String(256))
    rights_review_status: Mapped[str] = mapped_column(String(32))
    rights_reviewer_ref: Mapped[str] = mapped_column(String(128))
    rights_reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    allowed_app_refs: Mapped[list[str]] = mapped_column(JSON, default=list)
    allowed_space_codes: Mapped[list[str]] = mapped_column(JSON, default=list)
    snapshot_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    excerpt_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    source_owner_ref: Mapped[str] = mapped_column(String(128))
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    effective_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ContentVersion(KnowledgeBase):
    """按内容哈希不可变的知识版本。"""

    __tablename__ = "kb_content_versions"
    __table_args__ = (UniqueConstraint("coverage_cell_id", "content_sha256", name="uq_kb_content_hash"),)

    id: Mapped[uuid.UUID] = uuid_primary_key()
    content_version_ref: Mapped[str] = mapped_column(String(160), unique=True)
    coverage_cell_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("kb_coverage_cells.id"), index=True)
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("kb_sources.id"), index=True)
    content_sha256: Mapped[str] = mapped_column(String(64))
    object_key: Mapped[str] = mapped_column(String(512))
    content_status: Mapped[str] = mapped_column(String(32))
    approval_status: Mapped[str] = mapped_column(String(32))
    knowledge_shape: Mapped[str] = mapped_column(String(8))
    statement_type: Mapped[str] = mapped_column(String(48))
    customer_scope: Mapped[str] = mapped_column(String(32))
    risk_level: Mapped[str] = mapped_column(String(32))
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    effective_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    conflict_group_ref: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    supersedes_version_ref: Mapped[str | None] = mapped_column(
        ForeignKey("kb_content_versions.content_version_ref"),
        nullable=True,
    )
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ContentApproval(KnowledgeBase):
    """内容版本的逐版本人工审批记录。"""

    __tablename__ = "kb_content_approvals"

    id: Mapped[uuid.UUID] = uuid_primary_key()
    approval_ref: Mapped[str] = mapped_column(String(160), unique=True)
    content_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("kb_content_versions.id"), index=True)
    decision: Mapped[str] = mapped_column(String(32))
    approved_by_ref: Mapped[str] = mapped_column(String(128))
    decision_reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class IndexGeneration(KnowledgeBase):
    """索引代次权威状态；向量切片属于 K3。"""

    __tablename__ = "kb_index_generations"

    id: Mapped[uuid.UUID] = uuid_primary_key()
    generation_ref: Mapped[str] = mapped_column(String(160), unique=True)
    index_state: Mapped[str] = mapped_column(String(32), index=True)
    embedding_model: Mapped[str] = mapped_column(String(160))
    embedding_dimensions: Mapped[int] = mapped_column(Integer)
    tokenizer_revision: Mapped[str] = mapped_column(String(160))
    parser_version: Mapped[str] = mapped_column(String(64))
    chunker_version: Mapped[str] = mapped_column(String(64))
    retrieval_config_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    reranker_model: Mapped[str | None] = mapped_column(String(160), nullable=True)
    manifest_sha256: Mapped[str] = mapped_column(String(64))
    built_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AuditEvent(KnowledgeBase):
    """低敏认证、授权和检索决策审计。"""

    __tablename__ = "kb_audit_events"

    id: Mapped[uuid.UUID] = uuid_primary_key()
    request_id: Mapped[str] = mapped_column(String(64), index=True)
    trace_id: Mapped[str] = mapped_column(String(36), index=True)
    application_ref: Mapped[str | None] = mapped_column(String(96), nullable=True, index=True)
    shop_ref_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    requested_space_codes: Mapped[list[str]] = mapped_column(JSON, default=list)
    decision: Mapped[str] = mapped_column(String(32), index=True)
    reason_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    jti_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    evidence_count: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
