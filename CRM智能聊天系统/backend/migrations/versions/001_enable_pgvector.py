"""启用 pgvector 扩展。"""

from alembic import op

revision = "001_enable_pgvector"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """启用 PostgreSQL 向量扩展，为后续 RAG 做准备。"""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    """回滚向量扩展；仅允许在没有向量列时执行。"""
    op.execute("DROP EXTENSION IF EXISTS vector")
