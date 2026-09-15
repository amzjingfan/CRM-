"""增加 FAQ 向量化队列和店铺状态汇总索引。"""

import sqlalchemy as sa
from alembic import op

revision = "015_vector_ops"
down_revision = "014_bge_hybrid"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """为 Worker 认领和运营状态汇总增加仅覆盖有效已发布 FAQ 的索引。"""
    active_published = sa.text("status = 'published' AND deleted_at IS NULL")
    op.create_index(
        "idx_knowledge_documents_vector_queue",
        "knowledge_documents",
        ["vectorization_status", "updated_at", "id"],
        unique=False,
        postgresql_where=active_published,
    )
    op.create_index(
        "idx_knowledge_documents_store_vector_status",
        "knowledge_documents",
        ["store_id", "vectorization_status"],
        unique=False,
        postgresql_where=active_published,
    )


def downgrade() -> None:
    """只移除本迁移创建的运维索引，不改变向量和文档状态。"""
    op.drop_index("idx_knowledge_documents_store_vector_status", table_name="knowledge_documents")
    op.drop_index("idx_knowledge_documents_vector_queue", table_name="knowledge_documents")
