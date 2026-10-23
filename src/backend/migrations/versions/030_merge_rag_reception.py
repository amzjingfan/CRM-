"""合流两个从 028 独立部署的 029 迁移。"""

revision = "030_merge_rag_reception"
down_revision = ("029_knowledge_file_ingestion", "029_reception_group_enabled")
branch_labels = None
depends_on = None


def upgrade() -> None:
    """两条父迁移均已完成，合流无需额外结构变更。"""


def downgrade() -> None:
    """降到两个 029 头；业务数据恢复由部署流程单独处理。"""
