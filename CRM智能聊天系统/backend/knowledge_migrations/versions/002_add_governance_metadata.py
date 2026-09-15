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


def upgrade() -> None:
    """补齐可服务资格推导所需的权威元数据。"""
    op.add_column("kb_coverage_cells", sa.Column("knowledge_shape", sa.String(length=8), nullable=False))
    op.add_column("kb_coverage_cells", sa.Column("content_owner_ref", sa.String(length=128), nullable=True))
    op.add_column("kb_coverage_cells", sa.Column("review_due_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("kb_coverage_cells", sa.Column("evaluation_set_ref", sa.String(length=256), nullable=True))
    op.add_column("kb_coverage_cells", sa.Column("gap_reason", sa.String(length=512), nullable=True))

    op.add_column("kb_sources", sa.Column("source_market", sa.String(length=16), nullable=False))
    op.add_column("kb_sources", sa.Column("source_language", sa.String(length=32), nullable=False))
    op.add_column("kb_sources", sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False))
    op.add_column("kb_sources", sa.Column("rights_review_status", sa.String(length=32), nullable=False))
    op.add_column("kb_sources", sa.Column("rights_reviewer_ref", sa.String(length=128), nullable=False))
    op.add_column("kb_sources", sa.Column("rights_reviewed_at", sa.DateTime(timezone=True), nullable=False))
    op.add_column("kb_sources", sa.Column("allowed_app_refs", sa.JSON(), nullable=False))
    op.add_column("kb_sources", sa.Column("allowed_space_codes", sa.JSON(), nullable=False))
    op.add_column("kb_sources", sa.Column("snapshot_allowed", sa.Boolean(), nullable=False))
    op.add_column("kb_sources", sa.Column("excerpt_allowed", sa.Boolean(), nullable=False))
    op.add_column("kb_sources", sa.Column("source_owner_ref", sa.String(length=128), nullable=False))
    op.add_column("kb_sources", sa.Column("review_due_at", sa.DateTime(timezone=True), nullable=False))
    op.add_column("kb_sources", sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False))
    op.add_column("kb_sources", sa.Column("effective_until", sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f("ix_kb_sources_review_due_at"), "kb_sources", ["review_due_at"])
    op.drop_index(op.f("ix_kb_sources_next_review_at"), table_name="kb_sources")
    op.drop_column("kb_sources", "rights_status")
    op.drop_column("kb_sources", "next_review_at")

    op.add_column("kb_content_versions", sa.Column("knowledge_shape", sa.String(length=8), nullable=False))
    op.add_column("kb_content_versions", sa.Column("statement_type", sa.String(length=48), nullable=False))
    op.add_column("kb_content_versions", sa.Column("customer_scope", sa.String(length=32), nullable=False))
    op.add_column("kb_content_versions", sa.Column("conflict_group_ref", sa.String(length=160), nullable=True))
    op.add_column("kb_content_versions", sa.Column("supersedes_version_ref", sa.String(length=160), nullable=True))
    op.create_foreign_key(
        "fk_kb_content_supersedes",
        "kb_content_versions",
        "kb_content_versions",
        ["supersedes_version_ref"],
        ["content_version_ref"],
    )
    op.create_index(
        op.f("ix_kb_content_versions_conflict_group_ref"),
        "kb_content_versions",
        ["conflict_group_ref"],
    )

    op.add_column("kb_content_approvals", sa.Column("approval_ref", sa.String(length=160), nullable=False))
    op.add_column("kb_content_approvals", sa.Column("approved_by_ref", sa.String(length=128), nullable=False))
    op.add_column("kb_content_approvals", sa.Column("approved_at", sa.DateTime(timezone=True), nullable=False))
    op.create_unique_constraint("uq_kb_content_approvals_approval_ref", "kb_content_approvals", ["approval_ref"])
    op.drop_column("kb_content_approvals", "reviewer_ref")
    op.drop_column("kb_content_approvals", "decided_at")

    op.add_column("kb_index_generations", sa.Column("tokenizer_revision", sa.String(length=160), nullable=False))
    op.add_column("kb_index_generations", sa.Column("parser_version", sa.String(length=64), nullable=False))
    op.add_column("kb_index_generations", sa.Column("chunker_version", sa.String(length=64), nullable=False))
    op.add_column("kb_index_generations", sa.Column("retrieval_config_json", sa.JSON(), nullable=False))
    op.add_column("kb_index_generations", sa.Column("built_at", sa.DateTime(timezone=True), nullable=False))


def downgrade() -> None:
    """恢复 001 基线字段，不跨库或操作 CRM 表。"""
    op.drop_column("kb_index_generations", "built_at")
    op.drop_column("kb_index_generations", "retrieval_config_json")
    op.drop_column("kb_index_generations", "chunker_version")
    op.drop_column("kb_index_generations", "parser_version")
    op.drop_column("kb_index_generations", "tokenizer_revision")

    op.add_column("kb_content_approvals", sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False))
    op.add_column("kb_content_approvals", sa.Column("reviewer_ref", sa.String(length=128), nullable=False))
    op.drop_constraint("uq_kb_content_approvals_approval_ref", "kb_content_approvals", type_="unique")
    op.drop_column("kb_content_approvals", "approved_at")
    op.drop_column("kb_content_approvals", "approved_by_ref")
    op.drop_column("kb_content_approvals", "approval_ref")

    op.drop_index(op.f("ix_kb_content_versions_conflict_group_ref"), table_name="kb_content_versions")
    op.drop_constraint("fk_kb_content_supersedes", "kb_content_versions", type_="foreignkey")
    op.drop_column("kb_content_versions", "supersedes_version_ref")
    op.drop_column("kb_content_versions", "conflict_group_ref")
    op.drop_column("kb_content_versions", "customer_scope")
    op.drop_column("kb_content_versions", "statement_type")
    op.drop_column("kb_content_versions", "knowledge_shape")

    op.add_column("kb_sources", sa.Column("next_review_at", sa.DateTime(timezone=True), nullable=False))
    op.add_column("kb_sources", sa.Column("rights_status", sa.String(length=32), nullable=False))
    op.create_index(op.f("ix_kb_sources_next_review_at"), "kb_sources", ["next_review_at"])
    op.drop_index(op.f("ix_kb_sources_review_due_at"), table_name="kb_sources")
    op.drop_column("kb_sources", "effective_until")
    op.drop_column("kb_sources", "effective_from")
    op.drop_column("kb_sources", "review_due_at")
    op.drop_column("kb_sources", "source_owner_ref")
    op.drop_column("kb_sources", "excerpt_allowed")
    op.drop_column("kb_sources", "snapshot_allowed")
    op.drop_column("kb_sources", "allowed_space_codes")
    op.drop_column("kb_sources", "allowed_app_refs")
    op.drop_column("kb_sources", "rights_reviewed_at")
    op.drop_column("kb_sources", "rights_reviewer_ref")
    op.drop_column("kb_sources", "rights_review_status")
    op.drop_column("kb_sources", "captured_at")
    op.drop_column("kb_sources", "source_language")
    op.drop_column("kb_sources", "source_market")

    op.drop_column("kb_coverage_cells", "gap_reason")
    op.drop_column("kb_coverage_cells", "evaluation_set_ref")
    op.drop_column("kb_coverage_cells", "review_due_at")
    op.drop_column("kb_coverage_cells", "content_owner_ref")
    op.drop_column("kb_coverage_cells", "knowledge_shape")
