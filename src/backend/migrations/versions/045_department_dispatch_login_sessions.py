"""部门统一派单与登录会话在线证据。"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "045_dept_dispatch_login"
down_revision = "044_reception_assignment"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_login_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_user_login_sessions_online", "user_login_sessions", ["user_id", "expires_at"])
    op.create_table(
        "reception_department_configs",
        sa.Column(
            "department_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("departments.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "reception_department_agents",
        sa.Column(
            "department_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("departments.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("auto_enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("last_assigned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    # 已有店铺配置迁入部门配置；一间店铺开启过则保持部门开启，未配置仍默认关闭。
    connection = op.get_bind()
    connection.execute(
        sa.text("""
        INSERT INTO reception_department_configs (department_id, enabled)
        SELECT department_id, bool_or(enabled) FROM reception_store_configs GROUP BY department_id
    """)
    )
    connection.execute(
        sa.text("""
        INSERT INTO reception_department_agents (department_id, user_id, auto_enabled, last_assigned_at)
        SELECT s.department_id, a.user_id, bool_or(a.auto_enabled), max(a.last_assigned_at)
        FROM reception_agent_configs a JOIN reception_store_configs s ON s.store_id = a.store_id
        GROUP BY s.department_id, a.user_id
    """)
    )
    # 主管参加派单必须能回复本人部门店铺会话，店铺范围仍由服务端二次限制。
    connection.execute(
        sa.text("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id FROM roles r CROSS JOIN permissions p
        WHERE r.code = 'supervisor' AND p.code = 'workspace.reply'
        ON CONFLICT DO NOTHING
    """)
    )


def downgrade() -> None:
    connection = op.get_bind()
    if connection.scalar(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM user_login_sessions) "
            "OR EXISTS (SELECT 1 FROM reception_department_configs) "
            "OR EXISTS (SELECT 1 FROM reception_department_agents)"
        )
    ):
        raise RuntimeError("部门派单或登录会话已有数据；请使用部署备份恢复")
    connection.execute(
        sa.text("""
        DELETE FROM role_permissions rp USING roles r, permissions p
        WHERE rp.role_id = r.id AND rp.permission_id = p.id
        AND r.code = 'supervisor' AND p.code = 'workspace.reply'
    """)
    )
    op.drop_table("reception_department_agents")
    op.drop_table("reception_department_configs")
    op.drop_index("ix_user_login_sessions_online", table_name="user_login_sessions")
    op.drop_table("user_login_sessions")
