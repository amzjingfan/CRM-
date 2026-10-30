"""合流 Agent 模板与部门派单迁移，保留两条已验证的历史。"""

revision = "046_merge_templates_dispatch"
down_revision = ("045_agent_templates", "045_dept_dispatch_login")
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 两个父迁移各自拥有结构变更，合流节点不重复执行或改写历史。
    pass


def downgrade() -> None:
    pass
