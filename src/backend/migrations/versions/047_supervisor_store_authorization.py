"""允许客服主管授权本部门 TikTok 店铺。"""

import uuid

import sqlalchemy as sa
from alembic import op

revision = "047_supervisor_store_auth"
down_revision = "046_merge_templates_dispatch"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text("""
        INSERT INTO permissions (id, code, name, resource, action)
        VALUES (:permission_id, 'settings.store_authorize', '店铺授权', 'settings', 'store_authorize')
        ON CONFLICT (code) DO NOTHING
    """),
        {"permission_id": uuid.uuid4()},
    )
    connection.execute(
        sa.text("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id FROM roles r CROSS JOIN permissions p
        WHERE r.code = 'supervisor' AND p.code = 'settings.store_authorize'
        ON CONFLICT DO NOTHING
    """)
    )


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text("""
        DELETE FROM role_permissions rp USING roles r, permissions p
        WHERE rp.role_id = r.id AND rp.permission_id = p.id
        AND r.code = 'supervisor' AND p.code = 'settings.store_authorize'
    """)
    )
    connection.execute(sa.text("DELETE FROM permissions WHERE code = 'settings.store_authorize'"))
