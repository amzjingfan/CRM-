"""允许客服主管管理所属部门店铺的知识库。"""

import sqlalchemy as sa
from alembic import op

revision = "051_supervisor_knowledge_manage"
down_revision = "050_agent_reception_delivery"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.get_bind().execute(
        sa.text("""
            INSERT INTO role_permissions (role_id, permission_id)
            SELECT r.id, p.id FROM roles r CROSS JOIN permissions p
            WHERE r.code = 'supervisor' AND p.code = 'knowledge.manage'
            ON CONFLICT DO NOTHING
        """)
    )


def downgrade() -> None:
    op.get_bind().execute(
        sa.text("""
            DELETE FROM role_permissions rp USING roles r, permissions p
            WHERE rp.role_id = r.id AND rp.permission_id = p.id
              AND r.code = 'supervisor' AND p.code = 'knowledge.manage'
        """)
    )
