"""Gate Agent document retrieval on reviewed, active file versions."""

import sqlalchemy as sa
from alembic import op

revision = "033_file_version_approval"
down_revision = "032_knowledge_file_archive"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "knowledge_file_versions",
        sa.Column("publication_approval", sa.String(40), nullable=False, server_default="draft"),
    )
    op.add_column(
        "knowledge_file_versions", sa.Column("statement_type", sa.String(40), nullable=False, server_default="unknown")
    )
    op.add_column(
        "knowledge_file_versions", sa.Column("customer_scope", sa.String(40), nullable=False, server_default="none")
    )
    op.add_column(
        "knowledge_file_versions",
        sa.Column("approved_by", sa.UUID(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
    )
    op.add_column("knowledge_file_versions", sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(
        "ix_knowledge_file_chunks_embedding_hnsw",
        "knowledge_file_chunks",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.create_index(
        "ix_knowledge_file_chunks_content_trgm",
        "knowledge_file_chunks",
        ["content"],
        postgresql_using="gin",
        postgresql_ops={"content": "gin_trgm_ops"},
    )


def downgrade() -> None:
    connection = op.get_bind()
    if connection.scalar(
        sa.text("SELECT EXISTS (SELECT 1 FROM knowledge_file_versions WHERE publication_approval <> 'draft')")
    ):
        raise RuntimeError("文件版本已有审批数据，不能无损降级；请从部署备份恢复")
    op.drop_index("ix_knowledge_file_chunks_content_trgm", table_name="knowledge_file_chunks")
    op.drop_index("ix_knowledge_file_chunks_embedding_hnsw", table_name="knowledge_file_chunks")
    for column in ("approved_at", "approved_by", "customer_scope", "statement_type", "publication_approval"):
        op.drop_column("knowledge_file_versions", column)
