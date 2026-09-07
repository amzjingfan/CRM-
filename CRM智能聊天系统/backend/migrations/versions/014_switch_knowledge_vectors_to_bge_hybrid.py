"""切换 BGE-M3 1024 维向量并启用 pg_trgm 混合召回。"""

from alembic import op

revision = "014_bge_hybrid"
down_revision = "013_marketing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """废弃 1536 维派生数据，重建 1024 维向量和词法检索索引。

    knowledge_chunks 只保存可重新生成的派生切片。迁移不执行模型推理，
    仅清理旧维度切片并把已发布文档重置为 pending，后续由 jobs Worker
    在迁移事务外使用固定 BGE-M3 Revision 全量回填。
    """
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.drop_index("idx_knowledge_chunks_embedding", table_name="knowledge_chunks")
    op.execute("DELETE FROM knowledge_chunks")
    op.execute("ALTER TABLE knowledge_chunks ALTER COLUMN embedding TYPE vector(1024)")
    op.execute(
        "UPDATE knowledge_documents SET vectorization_status = 'pending' "
        "WHERE status = 'published' AND deleted_at IS NULL"
    )
    op.execute(
        "CREATE INDEX idx_knowledge_chunks_embedding ON knowledge_chunks USING hnsw (embedding vector_cosine_ops)"
    )
    op.execute("CREATE INDEX idx_knowledge_chunks_content_trgm ON knowledge_chunks USING gin (content gin_trgm_ops)")


def downgrade() -> None:
    """恢复 1536 维结构；派生向量同样必须由旧 Provider 重新生成。"""
    op.drop_index("idx_knowledge_chunks_content_trgm", table_name="knowledge_chunks")
    op.drop_index("idx_knowledge_chunks_embedding", table_name="knowledge_chunks")
    op.execute("DELETE FROM knowledge_chunks")
    op.execute("ALTER TABLE knowledge_chunks ALTER COLUMN embedding TYPE vector(1536)")
    op.execute(
        "UPDATE knowledge_documents SET vectorization_status = 'pending' "
        "WHERE status = 'published' AND deleted_at IS NULL"
    )
    op.execute(
        "CREATE INDEX idx_knowledge_chunks_embedding ON knowledge_chunks USING hnsw (embedding vector_cosine_ops)"
    )
    # pg_trgm 可能由同库其他模块预先启用，回滚只删除本迁移创建的索引，
    # 不擅自 DROP EXTENSION 影响其他消费者。
