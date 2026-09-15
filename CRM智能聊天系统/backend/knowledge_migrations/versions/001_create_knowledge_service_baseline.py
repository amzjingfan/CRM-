"""创建 K2 独立知识服务权威表。

Revision ID: 001_kb_baseline
Revises: None
Create Date: 2026-09-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "001_kb_baseline"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _id_column() -> sa.Column[sa.Uuid]:
    return sa.Column("id", sa.Uuid(), nullable=False)


def _created_at_column() -> sa.Column[sa.DateTime]:
    return sa.Column("created_at", sa.DateTime(timezone=True), nullable=False)


def upgrade() -> None:
    """只创建知识服务自有表，不引用 CRM schema。"""
    op.create_table(
        "kb_applications",
        sa.Column("application_ref", sa.String(length=96), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        _created_at_column(),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("application_ref"),
    )
    op.create_table(
        "kb_application_space_grants",
        _id_column(),
        sa.Column("application_ref", sa.String(length=96), nullable=False),
        sa.Column("platform_code", sa.String(length=32), nullable=False),
        sa.Column("market_code", sa.String(length=16), nullable=False),
        sa.Column("language_tag", sa.String(length=32), nullable=False),
        sa.Column("audience_code", sa.String(length=64), nullable=False),
        sa.Column("space_code", sa.String(length=32), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        _created_at_column(),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("space_code IN ('company_shared', 'shop_private')", name="ck_kb_application_space_code"),
        sa.ForeignKeyConstraint(["application_ref"], ["kb_applications.application_ref"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "application_ref",
            "platform_code",
            "market_code",
            "language_tag",
            "audience_code",
            "space_code",
            name="uq_kb_application_space_grant",
        ),
    )
    op.create_index(
        op.f("ix_kb_application_space_grants_application_ref"),
        "kb_application_space_grants",
        ["application_ref"],
    )
    op.create_table(
        "kb_shop_space_grants",
        _id_column(),
        sa.Column("application_ref", sa.String(length=96), nullable=False),
        sa.Column("shop_ref", sa.String(length=128), nullable=False),
        sa.Column("space_code", sa.String(length=32), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        _created_at_column(),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("space_code = 'shop_private'", name="ck_kb_shop_private_only"),
        sa.ForeignKeyConstraint(["application_ref"], ["kb_applications.application_ref"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("application_ref", "shop_ref", "space_code", name="uq_kb_shop_space_grant"),
    )
    op.create_index(op.f("ix_kb_shop_space_grants_application_ref"), "kb_shop_space_grants", ["application_ref"])
    op.create_index(op.f("ix_kb_shop_space_grants_shop_ref"), "kb_shop_space_grants", ["shop_ref"])
    op.create_table(
        "kb_revoked_credentials",
        _id_column(),
        sa.Column("issuer", sa.String(length=128), nullable=False),
        sa.Column("jti_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason_code", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("issuer", "jti_hash", name="uq_kb_revoked_credential"),
    )
    op.create_index(op.f("ix_kb_revoked_credentials_expires_at"), "kb_revoked_credentials", ["expires_at"])
    op.create_table(
        "kb_coverage_cells",
        _id_column(),
        sa.Column("coverage_cell_ref", sa.String(length=160), nullable=False),
        sa.Column("domain_code", sa.String(length=64), nullable=False),
        sa.Column("platform_code", sa.String(length=32), nullable=False),
        sa.Column("market_code", sa.String(length=16), nullable=False),
        sa.Column("language_tag", sa.String(length=32), nullable=False),
        sa.Column("audience_code", sa.String(length=64), nullable=False),
        sa.Column("space_code", sa.String(length=32), nullable=False),
        sa.Column("shop_ref", sa.String(length=128), nullable=True),
        sa.Column("coverage_status", sa.String(length=32), nullable=False),
        _created_at_column(),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(space_code = 'company_shared' AND shop_ref IS NULL) OR "
            "(space_code = 'shop_private' AND shop_ref IS NOT NULL)",
            name="ck_kb_coverage_space_shop",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("coverage_cell_ref"),
    )
    op.create_index(
        "uq_kb_coverage_dimensions",
        "kb_coverage_cells",
        ["domain_code", "platform_code", "market_code", "language_tag", "audience_code", "space_code", "shop_ref"],
        unique=True,
        postgresql_nulls_not_distinct=True,
    )
    op.create_table(
        "kb_sources",
        _id_column(),
        sa.Column("source_ref", sa.String(length=160), nullable=False),
        sa.Column("publisher", sa.String(length=200), nullable=False),
        sa.Column("source_type", sa.String(length=48), nullable=False),
        sa.Column("source_uri", sa.Text(), nullable=True),
        sa.Column("object_key", sa.String(length=512), nullable=True),
        sa.Column("rights_basis_ref", sa.String(length=256), nullable=False),
        sa.Column("rights_status", sa.String(length=32), nullable=False),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_review_at", sa.DateTime(timezone=True), nullable=False),
        _created_at_column(),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_ref"),
    )
    op.create_index(op.f("ix_kb_sources_next_review_at"), "kb_sources", ["next_review_at"])
    op.create_table(
        "kb_content_versions",
        _id_column(),
        sa.Column("content_version_ref", sa.String(length=160), nullable=False),
        sa.Column("coverage_cell_id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("object_key", sa.String(length=512), nullable=False),
        sa.Column("content_status", sa.String(length=32), nullable=False),
        sa.Column("approval_status", sa.String(length=32), nullable=False),
        sa.Column("risk_level", sa.String(length=32), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        _created_at_column(),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["coverage_cell_id"], ["kb_coverage_cells.id"]),
        sa.ForeignKeyConstraint(["source_id"], ["kb_sources.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("content_version_ref"),
        sa.UniqueConstraint("coverage_cell_id", "content_sha256", name="uq_kb_content_hash"),
    )
    op.create_index(op.f("ix_kb_content_versions_coverage_cell_id"), "kb_content_versions", ["coverage_cell_id"])
    op.create_index(op.f("ix_kb_content_versions_source_id"), "kb_content_versions", ["source_id"])
    op.create_table(
        "kb_content_approvals",
        _id_column(),
        sa.Column("content_version_id", sa.Uuid(), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("reviewer_ref", sa.String(length=128), nullable=False),
        sa.Column("decision_reason", sa.String(length=512), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        _created_at_column(),
        sa.ForeignKeyConstraint(["content_version_id"], ["kb_content_versions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_kb_content_approvals_content_version_id"), "kb_content_approvals", ["content_version_id"])
    op.create_table(
        "kb_index_generations",
        _id_column(),
        sa.Column("generation_ref", sa.String(length=160), nullable=False),
        sa.Column("index_state", sa.String(length=32), nullable=False),
        sa.Column("embedding_model", sa.String(length=160), nullable=False),
        sa.Column("embedding_dimensions", sa.Integer(), nullable=False),
        sa.Column("reranker_model", sa.String(length=160), nullable=True),
        sa.Column("manifest_sha256", sa.String(length=64), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        _created_at_column(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("generation_ref"),
    )
    op.create_index(op.f("ix_kb_index_generations_index_state"), "kb_index_generations", ["index_state"])
    op.create_table(
        "kb_audit_events",
        _id_column(),
        sa.Column("request_id", sa.String(length=64), nullable=False),
        sa.Column("application_ref", sa.String(length=96), nullable=True),
        sa.Column("shop_ref_hash", sa.String(length=64), nullable=True),
        sa.Column("requested_space_codes", sa.JSON(), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("reason_code", sa.String(length=64), nullable=True),
        sa.Column("jti_hash", sa.String(length=64), nullable=True),
        sa.Column("evidence_count", sa.Integer(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        _created_at_column(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_kb_audit_events_application_ref"), "kb_audit_events", ["application_ref"])
    op.create_index(op.f("ix_kb_audit_events_created_at"), "kb_audit_events", ["created_at"])
    op.create_index(op.f("ix_kb_audit_events_decision"), "kb_audit_events", ["decision"])
    op.create_index(op.f("ix_kb_audit_events_request_id"), "kb_audit_events", ["request_id"])


def downgrade() -> None:
    """按外键依赖逆序删除 K2 自有表。"""
    op.drop_table("kb_audit_events")
    op.drop_table("kb_index_generations")
    op.drop_table("kb_content_approvals")
    op.drop_table("kb_content_versions")
    op.drop_table("kb_sources")
    op.drop_table("kb_coverage_cells")
    op.drop_table("kb_revoked_credentials")
    op.drop_table("kb_shop_space_grants")
    op.drop_table("kb_application_space_grants")
    op.drop_table("kb_applications")
