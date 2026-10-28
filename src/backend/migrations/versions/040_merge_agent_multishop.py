"""合流本地多店授权与动态 Agent 两条独立迁移链。"""

revision = "040_merge_agent_multishop"
down_revision = ("035_tiktok_seller_multishop", "039_agent_run_hierarchy")
branch_labels = None
depends_on = None


def upgrade() -> None:
    """两个父迁移都完成后，合流本身无需结构变更。"""


def downgrade() -> None:
    """降级到两个父头；实际数据恢复由部署门禁单独验证。"""
