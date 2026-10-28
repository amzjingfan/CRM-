"""合流多店授权与 Agent 内部协作两条已验证的迁移链。"""

revision = "041_merge_agent_multishop_collab"
down_revision = ("040_merge_agent_multishop", "040_agent_collaboration")
branch_labels = None
depends_on = None


def upgrade() -> None:
    """两个父迁移都完成后，合流本身无需结构变更。"""


def downgrade() -> None:
    """降级到两个父头；业务数据恢复仍由部署门禁单独验证。"""
