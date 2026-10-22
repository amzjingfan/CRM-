"""补齐员工登录账号元数据及部门组织关系。"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "026_team_accounts_departments"
down_revision = "025_workspace_actions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """仅添加字段和组织表，现有登录与店铺授权原样保留。"""
    op.alter_column("users", "email", existing_type=sa.String(255), nullable=True)
    op.add_column("users", sa.Column("login_name", sa.String(16), nullable=True))
    op.add_column("users", sa.Column("phone", sa.String(21), nullable=True))
    op.add_column("users", sa.Column("timezone", sa.String(64), server_default="Asia/Shanghai", nullable=False))
    op.add_column("users", sa.Column("max_concurrent_sessions", sa.Integer(), server_default="50", nullable=False))
    op.add_column("users", sa.Column("auth_version", sa.Integer(), server_default="0", nullable=False))
    op.create_unique_constraint("uq_users_login_name", "users", ["login_name"])
    op.create_check_constraint("ck_users_email_or_login_name", "users", "email IS NOT NULL OR login_name IS NOT NULL")
    op.create_check_constraint(
        "ck_users_max_concurrent_sessions", "users", "max_concurrent_sessions BETWEEN 1 AND 1000"
    )

    op.create_table(
        "departments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("name", name="uq_departments_name"),
    )
    op.create_table(
        "department_stores",
        sa.Column(
            "department_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("departments.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "store_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("stores.id", ondelete="CASCADE"), primary_key=True
        ),
    )
    op.create_table(
        "department_members",
        sa.Column(
            "department_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("departments.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    """若已存新账号或部门数据则失败关闭，先走备份恢复而非丢弃数据。"""
    connection = op.get_bind()
    has_new_data = connection.scalar(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM users WHERE email IS NULL OR login_name IS NOT NULL) "
            "OR EXISTS (SELECT 1 FROM departments)"
        )
    )
    if has_new_data:
        raise RuntimeError("已有新账号或部门数据，不能无损降级；请使用部署备份恢复")
    op.drop_table("department_members")
    op.drop_table("department_stores")
    op.drop_table("departments")
    op.drop_constraint("ck_users_max_concurrent_sessions", "users", type_="check")
    op.drop_constraint("ck_users_email_or_login_name", "users", type_="check")
    op.drop_constraint("uq_users_login_name", "users", type_="unique")
    op.drop_column("users", "auth_version")
    op.drop_column("users", "max_concurrent_sessions")
    op.drop_column("users", "timezone")
    op.drop_column("users", "phone")
    op.drop_column("users", "login_name")
    op.alter_column("users", "email", existing_type=sa.String(255), nullable=False)
