"""写入初始角色和权限。"""

import uuid

import sqlalchemy as sa
from alembic import op

revision = "004_seed_rbac"
down_revision = "003_rbac"
branch_labels = None
depends_on = None

ROLE_DATA = {
    "admin": ("管理员", "系统全部权限"),
    "supervisor": ("主管", "工作台和运营查看权限"),
    "agent": ("客服", "工作台回复和转人工权限"),
}
PERMISSION_CODES = [
    "auth.login",
    "auth.me",
    "dashboard.view",
    "workspace.view",
    "workspace.reply",
    "workspace.transfer",
    "knowledge.view",
    "knowledge.manage",
    "settings.channels",
    "settings.team",
    "agent.view",
    "agent.manage",
]
ROLE_PERMISSION_CODES = {
    "admin": PERMISSION_CODES,
    "supervisor": [
        "dashboard.view",
        "workspace.view",
        "workspace.transfer",
        "knowledge.view",
        "settings.team",
        "agent.view",
    ],
    "agent": ["workspace.view", "workspace.reply", "workspace.transfer"],
}


def upgrade() -> None:
    """插入稳定的初始 RBAC 数据；管理员使用星号权限便于新增权限默认可用。"""
    connection = op.get_bind()
    role_ids = {code: uuid.uuid4() for code in ROLE_DATA}
    permission_ids = {code: uuid.uuid4() for code in PERMISSION_CODES}
    connection.execute(
        sa.text("INSERT INTO roles (id, code, name, description) VALUES (:id, :code, :name, :description)"),
        [
            {"id": role_id, "code": code, "name": data[0], "description": data[1]}
            for code, role_id in role_ids.items()
            for data in [ROLE_DATA[code]]
        ],
    )
    connection.execute(
        sa.text(
            "INSERT INTO permissions (id, code, name, resource, action) VALUES (:id, :code, :name, :resource, :action)"
        ),
        [
            {
                "id": permission_id,
                "code": code,
                "name": code,
                "resource": code.split(".")[0],
                "action": code.split(".")[1],
            }
            for code, permission_id in permission_ids.items()
        ],
    )
    connection.execute(
        sa.text("INSERT INTO role_permissions (role_id, permission_id) VALUES (:role_id, :permission_id)"),
        [
            {"role_id": role_ids[role_code], "permission_id": permission_ids[permission_code]}
            for role_code, codes in ROLE_PERMISSION_CODES.items()
            for permission_code in codes
        ],
    )


def downgrade() -> None:
    """删除本迁移写入的角色权限数据。"""
    connection = op.get_bind()
    connection.execute(sa.text("DELETE FROM role_permissions"))
    connection.execute(sa.text("DELETE FROM permissions"))
    connection.execute(sa.text("DELETE FROM roles"))
