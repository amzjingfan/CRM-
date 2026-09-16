"""为知识版本增加权威语义类型和人工发布审批。"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "020_knowledge_safety"
down_revision = "019_tiktok_channel_unique"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """旧知识统一保持 unknown + draft，禁止迁移过程自动提升权限。"""
    op.add_column(
        "knowledge_documents",
        sa.Column("statement_type", sa.String(length=40), nullable=False, server_default="unknown"),
    )
    op.add_column(
        "knowledge_documents",
        sa.Column("customer_scope", sa.String(length=30), nullable=False, server_default="none"),
    )
    op.add_column(
        "knowledge_documents",
        sa.Column("publication_approval", sa.String(length=40), nullable=False, server_default="draft"),
    )
    op.add_column(
        "knowledge_documents",
        sa.Column("semantic_schema_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "knowledge_documents",
        sa.Column("approved_by", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "knowledge_documents",
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_knowledge_documents_approved_by_users",
        "knowledge_documents",
        "users",
        ["approved_by"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "ck_knowledge_documents_statement_type",
        "knowledge_documents",
        "statement_type IN ('policy', 'technical_artifact', 'customer_instance_fact', "
        "'non_assertive_proposition', 'unknown')",
    )
    op.create_check_constraint(
        "ck_knowledge_documents_customer_scope",
        "knowledge_documents",
        "customer_scope IN ('none', 'generic', 'specific_customer')",
    )
    op.create_check_constraint(
        "ck_knowledge_documents_publication_approval",
        "knowledge_documents",
        "publication_approval IN ('draft', 'approved_for_internal_review', 'approved_for_public_reply')",
    )
    op.create_check_constraint(
        "ck_knowledge_documents_semantic_schema_version",
        "knowledge_documents",
        "semantic_schema_version = 1",
    )
    op.create_check_constraint(
        "ck_knowledge_documents_approval_actor_time",
        "knowledge_documents",
        "(publication_approval = 'draft' AND approved_by IS NULL AND approved_at IS NULL) OR "
        "(publication_approval <> 'draft' AND approved_by IS NOT NULL AND approved_at IS NOT NULL)",
    )
    op.create_check_constraint(
        "ck_knowledge_documents_semantic_scope",
        "knowledge_documents",
        "(statement_type <> 'technical_artifact' OR customer_scope = 'none') AND "
        "(statement_type NOT IN ('policy', 'non_assertive_proposition') OR customer_scope <> 'specific_customer')",
    )


def downgrade() -> None:
    """删除新增审批字段，不删除知识正文和历史向量。"""
    op.drop_constraint("ck_knowledge_documents_semantic_scope", "knowledge_documents", type_="check")
    op.drop_constraint("ck_knowledge_documents_approval_actor_time", "knowledge_documents", type_="check")
    op.drop_constraint("ck_knowledge_documents_semantic_schema_version", "knowledge_documents", type_="check")
    op.drop_constraint("ck_knowledge_documents_publication_approval", "knowledge_documents", type_="check")
    op.drop_constraint("ck_knowledge_documents_customer_scope", "knowledge_documents", type_="check")
    op.drop_constraint("ck_knowledge_documents_statement_type", "knowledge_documents", type_="check")
    op.drop_constraint("fk_knowledge_documents_approved_by_users", "knowledge_documents", type_="foreignkey")
    op.drop_column("knowledge_documents", "approved_at")
    op.drop_column("knowledge_documents", "approved_by")
    op.drop_column("knowledge_documents", "semantic_schema_version")
    op.drop_column("knowledge_documents", "publication_approval")
    op.drop_column("knowledge_documents", "customer_scope")
    op.drop_column("knowledge_documents", "statement_type")
