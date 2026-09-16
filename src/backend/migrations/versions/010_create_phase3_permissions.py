"""写入 Phase 3 订单、优惠券和营销权限。"""

import uuid

import sqlalchemy as sa
from alembic import op

revision = "010_phase3_permissions"
down_revision = "009_agent_runs"
branch_labels = None
depends_on = None

PERMISSIONS = {
    "orders.view": ("查看订单与物流", "orders", "view"),
    "orders.address.update": ("修改收货地址", "orders", "address.update"),
    "coupons.issue": ("发放优惠券", "coupons", "issue"),
    "marketing.view": ("查看主动营销", "marketing", "view"),
    "marketing.manage": ("管理主动营销", "marketing", "manage"),
}
ROLE_PERMISSIONS = {
    "admin": list(PERMISSIONS),
    "supervisor": list(PERMISSIONS),
    "agent": ["orders.view", "orders.address.update", "coupons.issue"],
}


def upgrade() -> None:
    """新增权限并按已确认的 Phase 3 角色策略授权。"""
    connection = op.get_bind()
    permission_ids = {code: uuid.uuid4() for code in PERMISSIONS}
    connection.execute(
        sa.text(
            "INSERT INTO permissions (id, code, name, resource, action) VALUES (:id, :code, :name, :resource, :action)"
        ),
        [
            {
                "id": permission_ids[code],
                "code": code,
                "name": values[0],
                "resource": values[1],
                "action": values[2],
            }
            for code, values in PERMISSIONS.items()
        ],
    )
    role_rows = connection.execute(
        sa.text("SELECT id, code FROM roles WHERE code IN ('admin', 'supervisor', 'agent')")
    ).mappings()
    role_ids = {str(row["code"]): row["id"] for row in role_rows}
    connection.execute(
        sa.text("INSERT INTO role_permissions (role_id, permission_id) VALUES (:role_id, :permission_id)"),
        [
            {"role_id": role_ids[role], "permission_id": permission_ids[code]}
            for role, codes in ROLE_PERMISSIONS.items()
            if role in role_ids
            for code in codes
        ],
    )


def downgrade() -> None:
    """仅回滚本迁移新增权限，保留既有 RBAC 数据。"""
    op.get_bind().execute(
        sa.text("DELETE FROM permissions WHERE code = ANY(:codes)"),
        {"codes": list(PERMISSIONS)},
    )
