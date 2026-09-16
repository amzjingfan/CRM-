"""创建本地开发管理员账号。

生产环境不使用固定管理员密码；部署人员应通过安全配置注入账号和密码后执行本脚本。
"""

import asyncio
import os
import sys
import uuid

from sqlalchemy import insert, select

from app.auth.security import hash_password
from app.shared.database.base import Role, User, user_roles
from app.shared.database.session import session_factory


async def create_admin() -> None:
    """创建或更新本地管理员账号，并关联 admin 角色。"""
    email = os.environ.get("ADMIN_EMAIL", "admin@company.com").lower()
    password = os.environ.get("ADMIN_PASSWORD")
    if not password or len(password) < 8:
        raise ValueError("请通过 ADMIN_PASSWORD 提供至少 8 位管理员密码")

    async with session_factory() as session:
        user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if user is None:
            user = User(id=uuid.uuid4(), email=email, password_hash=hash_password(password), name="系统管理员")
            session.add(user)
            await session.flush()
        else:
            user.password_hash = hash_password(password)
            user.status = "active"
        role = (await session.execute(select(Role).where(Role.code == "admin"))).scalar_one()
        existing_role = await session.scalar(
            select(user_roles.c.id).where(
                user_roles.c.user_id == user.id,
                user_roles.c.role_id == role.id,
                user_roles.c.store_id.is_(None),
            )
        )
        if existing_role is None:
            await session.execute(
                insert(user_roles).values(id=uuid.uuid4(), user_id=user.id, role_id=role.id, store_id=None)
            )
        await session.commit()


if __name__ == "__main__":
    try:
        asyncio.run(create_admin())
    except (ValueError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1) from error
