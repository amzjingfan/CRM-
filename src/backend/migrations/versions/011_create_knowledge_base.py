"""创建 FAQ 知识库、向量切片和导入任务。"""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision = "011_knowledge_base"
down_revision = "010_phase3_permissions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """创建知识库结构，并通过发布状态与向量状态双门禁隔离正式检索。"""
    op.create_table(
        "knowledge_categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "store_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "parent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("knowledge_categories.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("code", sa.String(100), nullable=False),
        sa.Column("layer", sa.String(1), server_default="C", nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("status", sa.String(20), server_default="active", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("layer IN ('A','B','C','D')", name="ck_knowledge_categories_layer"),
        sa.CheckConstraint("status IN ('active','disabled')", name="ck_knowledge_categories_status"),
        sa.UniqueConstraint("store_id", "code", name="uq_knowledge_category_store_code"),
    )
    op.create_index(
        "idx_knowledge_categories_store_parent", "knowledge_categories", ["store_id", "parent_id", "sort_order"]
    )
    op.create_table(
        "knowledge_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "store_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "category_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("knowledge_categories.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("source_type", sa.String(30), server_default="faq", nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("source", sa.String(200), nullable=True),
        sa.Column("tags", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("status", sa.String(20), server_default="draft", nullable=False),
        sa.Column("vectorization_status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("document_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("usage_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("satisfaction_rate", sa.Float(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('draft','published','archived')", name="ck_knowledge_documents_status"),
        sa.CheckConstraint(
            "vectorization_status IN ('pending','processing','ready','failed')",
            name="ck_knowledge_documents_vector_status",
        ),
    )
    op.create_index("idx_knowledge_documents_store_status", "knowledge_documents", ["store_id", "status", "updated_at"])
    op.create_index("idx_knowledge_documents_category", "knowledge_documents", ["category_id"])
    op.create_table(
        "knowledge_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "store_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("document_version", sa.Integer(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "document_id", "document_version", "chunk_index", name="uq_knowledge_chunk_document_version_index"
        ),
    )
    op.create_index("idx_knowledge_chunks_document", "knowledge_chunks", ["document_id"])
    op.execute(
        "CREATE INDEX idx_knowledge_chunks_embedding ON knowledge_chunks USING hnsw (embedding vector_cosine_ops)"
    )
    op.create_table(
        "knowledge_import_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "store_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("object_key", sa.String(500), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("status", sa.String(30), server_default="pending", nullable=False),
        sa.Column("total_rows", sa.Integer(), server_default="0", nullable=False),
        sa.Column("succeeded_rows", sa.Integer(), server_default="0", nullable=False),
        sa.Column("failed_rows", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_summary", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending','processing','succeeded','partially_succeeded','failed')",
            name="ck_knowledge_import_jobs_status",
        ),
    )
    op.create_index("idx_knowledge_import_jobs_status", "knowledge_import_jobs", ["status", "created_at"])


def downgrade() -> None:
    """按依赖逆序删除知识库结构。"""
    op.drop_index("idx_knowledge_import_jobs_status", table_name="knowledge_import_jobs")
    op.drop_table("knowledge_import_jobs")
    op.drop_index("idx_knowledge_chunks_embedding", table_name="knowledge_chunks")
    op.drop_index("idx_knowledge_chunks_document", table_name="knowledge_chunks")
    op.drop_table("knowledge_chunks")
    op.drop_index("idx_knowledge_documents_category", table_name="knowledge_documents")
    op.drop_index("idx_knowledge_documents_store_status", table_name="knowledge_documents")
    op.drop_table("knowledge_documents")
    op.drop_index("idx_knowledge_categories_store_parent", table_name="knowledge_categories")
    op.drop_table("knowledge_categories")
