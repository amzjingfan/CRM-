"""Keep RAG file archive state separate from its immutable versions and soft deletion."""

import sqlalchemy as sa
from alembic import op

revision = "032_knowledge_file_archive"
down_revision = "031_reception_policy_schedule"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("knowledge_files", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    connection = op.get_bind()
    if connection.scalar(sa.text("SELECT EXISTS (SELECT 1 FROM knowledge_files WHERE archived_at IS NOT NULL)")):
        raise RuntimeError("文件已有归档状态，不能无损降级；请从部署备份恢复")
    op.drop_column("knowledge_files", "archived_at")
