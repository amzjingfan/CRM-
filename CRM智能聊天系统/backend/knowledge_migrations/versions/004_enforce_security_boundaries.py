"""补齐委托主体、审计分域、数据约束和运行角色最小权限。

Revision ID: 004_kb_security
Revises: 003_kb_audit_trace
Create Date: 2026-09-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "004_kb_security"
down_revision: str | None = "003_kb_audit_trace"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _apply_runtime_grants() -> None:
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'knowledge_runtime') THEN
            REVOKE INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public FROM knowledge_runtime;
            GRANT SELECT ON ALL TABLES IN SCHEMA public TO knowledge_runtime;
            GRANT INSERT ON TABLE kb_audit_events TO knowledge_runtime;
          END IF;
        END
        $$
        """
    )


def upgrade() -> None:
    """把委托主体和最终权威状态固化到数据库边界。"""
    op.create_table(
        "kb_delegated_subject_grants",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("application_ref", sa.String(length=96), nullable=False),
        sa.Column("delegated_subject_ref", sa.String(length=128), nullable=False),
        sa.Column("shop_ref", sa.String(length=128), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "valid_until IS NULL OR valid_until > valid_from",
            name="ck_kb_delegated_subject_window",
        ),
        sa.ForeignKeyConstraint(["application_ref"], ["kb_applications.application_ref"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "application_ref",
            "delegated_subject_ref",
            "shop_ref",
            name="uq_kb_delegated_subject_grant",
        ),
    )
    op.create_index(
        op.f("ix_kb_delegated_subject_grants_application_ref"),
        "kb_delegated_subject_grants",
        ["application_ref"],
    )
    op.create_index(
        op.f("ix_kb_delegated_subject_grants_delegated_subject_ref"),
        "kb_delegated_subject_grants",
        ["delegated_subject_ref"],
    )
    op.create_index(
        op.f("ix_kb_delegated_subject_grants_shop_ref"),
        "kb_delegated_subject_grants",
        ["shop_ref"],
    )

    op.add_column("kb_audit_events", sa.Column("application_jti_hash", sa.String(length=64), nullable=True))
    op.add_column("kb_audit_events", sa.Column("delegation_jti_hash", sa.String(length=64), nullable=True))
    op.execute("UPDATE kb_audit_events SET application_jti_hash = jti_hash")
    op.drop_column("kb_audit_events", "jti_hash")

    op.execute(
        "UPDATE kb_sources SET object_key = 'migration/quarantine/' || source_ref "
        "WHERE source_uri IS NULL AND object_key IS NULL"
    )
    op.execute("UPDATE kb_content_versions SET content_sha256 = lower(content_sha256)")
    op.execute(
        "UPDATE kb_content_versions SET content_status = 'draft' "
        "WHERE content_status NOT IN ('draft', 'reviewed', 'approved', 'revoked')"
    )
    op.execute(
        "UPDATE kb_content_versions SET approval_status = 'pending' "
        "WHERE approval_status NOT IN ('pending', 'approved', 'rejected', 'revoked')"
    )
    op.execute(
        "UPDATE kb_index_generations SET index_state = 'not_indexed' "
        "WHERE index_state NOT IN ('not_indexed', 'building', 'ready', 'failed', 'stale')"
    )
    op.execute(
        "UPDATE kb_content_approvals SET decision = 'rejected' "
        "WHERE decision NOT IN ('approved', 'rejected', 'revoked')"
    )

    constraints = (
        ("kb_coverage_cells", "ck_kb_coverage_shape", "knowledge_shape IN ('A', 'B', 'C', 'D')"),
        ("kb_sources", "ck_kb_source_reference", "source_uri IS NOT NULL OR object_key IS NOT NULL"),
        (
            "kb_sources",
            "ck_kb_source_effective_window",
            "effective_until IS NULL OR effective_until > effective_from",
        ),
        ("kb_content_versions", "ck_kb_content_sha256", "content_sha256 ~ '^[0-9a-f]{64}$'"),
        (
            "kb_content_versions",
            "ck_kb_content_status",
            "content_status IN ('draft', 'reviewed', 'approved', 'revoked')",
        ),
        (
            "kb_content_versions",
            "ck_kb_content_approval_status",
            "approval_status IN ('pending', 'approved', 'rejected', 'revoked')",
        ),
        ("kb_content_versions", "ck_kb_content_shape", "knowledge_shape IN ('A', 'B', 'C', 'D')"),
        (
            "kb_content_versions",
            "ck_kb_statement_type",
            "statement_type IN ('policy', 'technical_artifact', 'customer_instance_fact', "
            "'non_assertive_proposition', 'unknown')",
        ),
        (
            "kb_content_versions",
            "ck_kb_customer_scope",
            "customer_scope IN ('none', 'generic', 'specific_customer')",
        ),
        (
            "kb_content_versions",
            "ck_kb_content_effective_window",
            "effective_until IS NULL OR effective_until > effective_from",
        ),
        (
            "kb_content_approvals",
            "ck_kb_approval_decision",
            "decision IN ('approved', 'rejected', 'revoked')",
        ),
        (
            "kb_index_generations",
            "ck_kb_index_state",
            "index_state IN ('not_indexed', 'building', 'ready', 'failed', 'stale')",
        ),
        ("kb_index_generations", "ck_kb_embedding_dimensions", "embedding_dimensions > 0"),
    )
    for table, name, condition in constraints:
        op.create_check_constraint(name, table, condition)
    _apply_runtime_grants()


def downgrade() -> None:
    """回退新增约束和委托主体表，并恢复 003 审计字段。"""
    constraints = (
        ("kb_index_generations", "ck_kb_embedding_dimensions"),
        ("kb_index_generations", "ck_kb_index_state"),
        ("kb_content_approvals", "ck_kb_approval_decision"),
        ("kb_content_versions", "ck_kb_content_effective_window"),
        ("kb_content_versions", "ck_kb_customer_scope"),
        ("kb_content_versions", "ck_kb_statement_type"),
        ("kb_content_versions", "ck_kb_content_shape"),
        ("kb_content_versions", "ck_kb_content_approval_status"),
        ("kb_content_versions", "ck_kb_content_status"),
        ("kb_content_versions", "ck_kb_content_sha256"),
        ("kb_sources", "ck_kb_source_effective_window"),
        ("kb_sources", "ck_kb_source_reference"),
        ("kb_coverage_cells", "ck_kb_coverage_shape"),
    )
    for table, name in constraints:
        op.drop_constraint(name, table, type_="check")

    op.add_column("kb_audit_events", sa.Column("jti_hash", sa.String(length=64), nullable=True))
    op.execute("UPDATE kb_audit_events SET jti_hash = application_jti_hash")
    op.drop_column("kb_audit_events", "delegation_jti_hash")
    op.drop_column("kb_audit_events", "application_jti_hash")
    op.drop_table("kb_delegated_subject_grants")
    _apply_runtime_grants()
