"""对齐 DATA-001-KB 来源、内容和索引治理元数据。

Revision ID: 002_kb_governance
Revises: 001_kb_baseline
Create Date: 2026-09-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "002_kb_governance"
down_revision: str | None = "001_kb_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _make_not_null(table: str, columns: tuple[tuple[str, sa.types.TypeEngine], ...]) -> None:
    for name, column_type in columns:
        op.alter_column(table, name, existing_type=column_type, nullable=False)


def upgrade() -> None:
    """先扩展、隔离回填，再收紧非空约束，兼容 001 已有数据。"""
    op.add_column("kb_coverage_cells", sa.Column("knowledge_shape", sa.String(length=8), nullable=True))
    op.add_column("kb_coverage_cells", sa.Column("content_owner_ref", sa.String(length=128), nullable=True))
    op.add_column("kb_coverage_cells", sa.Column("review_due_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("kb_coverage_cells", sa.Column("evaluation_set_ref", sa.String(length=256), nullable=True))
    op.add_column("kb_coverage_cells", sa.Column("gap_reason", sa.String(length=512), nullable=True))
    op.execute("UPDATE kb_coverage_cells SET knowledge_shape = 'A' WHERE knowledge_shape IS NULL")
    _make_not_null("kb_coverage_cells", (("knowledge_shape", sa.String(length=8)),))

    source_columns: tuple[tuple[str, sa.types.TypeEngine], ...] = (
        ("source_market", sa.String(length=16)),
        ("source_language", sa.String(length=32)),
        ("captured_at", sa.DateTime(timezone=True)),
        ("rights_review_status", sa.String(length=32)),
        ("rights_reviewer_ref", sa.String(length=128)),
        ("rights_reviewed_at", sa.DateTime(timezone=True)),
        ("allowed_app_refs", sa.JSON()),
        ("allowed_space_codes", sa.JSON()),
        ("snapshot_allowed", sa.Boolean()),
        ("excerpt_allowed", sa.Boolean()),
        ("source_owner_ref", sa.String(length=128)),
        ("review_due_at", sa.DateTime(timezone=True)),
        ("effective_from", sa.DateTime(timezone=True)),
    )
    for name, column_type in source_columns:
        op.add_column("kb_sources", sa.Column(name, column_type, nullable=True))
    op.add_column("kb_sources", sa.Column("effective_until", sa.DateTime(timezone=True), nullable=True))
    op.execute(
        """
        UPDATE kb_sources SET
          source_market = COALESCE(source_market, 'UNKNOWN'),
          source_language = COALESCE(source_language, 'und'),
          captured_at = COALESCE(captured_at, created_at),
          rights_review_status = COALESCE(rights_review_status, rights_status),
          rights_reviewer_ref = COALESCE(rights_reviewer_ref, 'migration-unassigned'),
          rights_reviewed_at = COALESCE(rights_reviewed_at, created_at),
          allowed_app_refs = COALESCE(allowed_app_refs, '[]'::json),
          allowed_space_codes = COALESCE(allowed_space_codes, '[]'::json),
          snapshot_allowed = COALESCE(snapshot_allowed, false),
          excerpt_allowed = COALESCE(excerpt_allowed, false),
          source_owner_ref = COALESCE(source_owner_ref, 'migration-unassigned'),
          review_due_at = COALESCE(review_due_at, next_review_at),
          effective_from = COALESCE(effective_from, created_at)
        """
    )
    _make_not_null("kb_sources", source_columns)
    op.create_index(op.f("ix_kb_sources_review_due_at"), "kb_sources", ["review_due_at"])
    op.drop_index(op.f("ix_kb_sources_next_review_at"), table_name="kb_sources")
    op.drop_column("kb_sources", "rights_status")
    op.drop_column("kb_sources", "next_review_at")

    content_columns: tuple[tuple[str, sa.types.TypeEngine], ...] = (
        ("knowledge_shape", sa.String(length=8)),
        ("statement_type", sa.String(length=48)),
        ("customer_scope", sa.String(length=32)),
    )
    for name, column_type in content_columns:
        op.add_column("kb_content_versions", sa.Column(name, column_type, nullable=True))
    op.add_column("kb_content_versions", sa.Column("conflict_group_ref", sa.String(length=160), nullable=True))
    op.add_column("kb_content_versions", sa.Column("supersedes_version_ref", sa.String(length=160), nullable=True))
    op.execute(
        """
        UPDATE kb_content_versions SET
          knowledge_shape = COALESCE(knowledge_shape, 'A'),
          statement_type = COALESCE(statement_type, 'unknown'),
          customer_scope = COALESCE(customer_scope, 'none')
        """
    )
    _make_not_null("kb_content_versions", content_columns)
    op.create_foreign_key(
        "fk_kb_content_supersedes",
        "kb_content_versions",
        "kb_content_versions",
        ["supersedes_version_ref"],
        ["content_version_ref"],
    )
    op.create_index(op.f("ix_kb_content_versions_conflict_group_ref"), "kb_content_versions", ["conflict_group_ref"])

    approval_columns: tuple[tuple[str, sa.types.TypeEngine], ...] = (
        ("approval_ref", sa.String(length=160)),
        ("approved_by_ref", sa.String(length=128)),
        ("approved_at", sa.DateTime(timezone=True)),
    )
    for name, column_type in approval_columns:
        op.add_column("kb_content_approvals", sa.Column(name, column_type, nullable=True))
    op.execute(
        """
        UPDATE kb_content_approvals SET
          approval_ref = COALESCE(approval_ref, 'migration-' || id::text),
          approved_by_ref = COALESCE(approved_by_ref, reviewer_ref),
          approved_at = COALESCE(approved_at, decided_at)
        """
    )
    _make_not_null("kb_content_approvals", approval_columns)
    op.create_unique_constraint("uq_kb_content_approvals_approval_ref", "kb_content_approvals", ["approval_ref"])
    op.drop_column("kb_content_approvals", "reviewer_ref")
    op.drop_column("kb_content_approvals", "decided_at")

    index_columns: tuple[tuple[str, sa.types.TypeEngine], ...] = (
        ("tokenizer_revision", sa.String(length=160)),
        ("parser_version", sa.String(length=64)),
        ("chunker_version", sa.String(length=64)),
        ("retrieval_config_json", sa.JSON()),
        ("built_at", sa.DateTime(timezone=True)),
    )
    for name, column_type in index_columns:
        op.add_column("kb_index_generations", sa.Column(name, column_type, nullable=True))
    op.execute(
        """
        UPDATE kb_index_generations SET
          tokenizer_revision = COALESCE(tokenizer_revision, 'migration-unknown'),
          parser_version = COALESCE(parser_version, 'migration-unknown'),
          chunker_version = COALESCE(chunker_version, 'migration-unknown'),
          retrieval_config_json = COALESCE(retrieval_config_json, '{}'::json),
          built_at = COALESCE(built_at, created_at)
        """
    )
    _make_not_null("kb_index_generations", index_columns)


def downgrade() -> None:
    """先反向回填 001 字段，再删除增量字段，保留已有行。"""
    op.drop_column("kb_index_generations", "built_at")
    op.drop_column("kb_index_generations", "retrieval_config_json")
    op.drop_column("kb_index_generations", "chunker_version")
    op.drop_column("kb_index_generations", "parser_version")
    op.drop_column("kb_index_generations", "tokenizer_revision")

    op.add_column("kb_content_approvals", sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("kb_content_approvals", sa.Column("reviewer_ref", sa.String(length=128), nullable=True))
    op.execute(
        "UPDATE kb_content_approvals SET decided_at = approved_at, reviewer_ref = approved_by_ref"
    )
    _make_not_null(
        "kb_content_approvals",
        (("decided_at", sa.DateTime(timezone=True)), ("reviewer_ref", sa.String(length=128))),
    )
    op.drop_constraint("uq_kb_content_approvals_approval_ref", "kb_content_approvals", type_="unique")
    op.drop_column("kb_content_approvals", "approved_at")
    op.drop_column("kb_content_approvals", "approved_by_ref")
    op.drop_column("kb_content_approvals", "approval_ref")

    op.drop_index(op.f("ix_kb_content_versions_conflict_group_ref"), table_name="kb_content_versions")
    op.drop_constraint("fk_kb_content_supersedes", "kb_content_versions", type_="foreignkey")
    for column in (
        "supersedes_version_ref",
        "conflict_group_ref",
        "customer_scope",
        "statement_type",
        "knowledge_shape",
    ):
        op.drop_column("kb_content_versions", column)

    op.add_column("kb_sources", sa.Column("next_review_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("kb_sources", sa.Column("rights_status", sa.String(length=32), nullable=True))
    op.execute(
        "UPDATE kb_sources SET next_review_at = review_due_at, rights_status = rights_review_status"
    )
    _make_not_null(
        "kb_sources",
        (("next_review_at", sa.DateTime(timezone=True)), ("rights_status", sa.String(length=32))),
    )
    op.create_index(op.f("ix_kb_sources_next_review_at"), "kb_sources", ["next_review_at"])
    op.drop_index(op.f("ix_kb_sources_review_due_at"), table_name="kb_sources")
    for column in (
        "effective_until",
        "effective_from",
        "review_due_at",
        "source_owner_ref",
        "excerpt_allowed",
        "snapshot_allowed",
        "allowed_space_codes",
        "allowed_app_refs",
        "rights_reviewed_at",
        "rights_reviewer_ref",
        "rights_review_status",
        "captured_at",
        "source_language",
        "source_market",
    ):
        op.drop_column("kb_sources", column)

    for column in ("gap_reason", "evaluation_set_ref", "review_due_at", "content_owner_ref", "knowledge_shape"):
        op.drop_column("kb_coverage_cells", column)
