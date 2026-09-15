"""为现有用户分配店铺级角色，参数只接受非敏感标识。"""

import argparse
import asyncio
import uuid

from sqlalchemy import insert, select

from app.shared.database.base import Role, User, user_roles
from app.shared.database.session import session_factory
from app.stores.models import Store


async def assign(email: str, store_code: str, role_code: str) -> None:
    """幂等写入用户、角色和店铺关联。"""
    async with session_factory() as session:
        user = await session.scalar(select(User).where(User.email == email.lower()))
        store = await session.scalar(select(Store).where(Store.code == store_code))
        role = await session.scalar(select(Role).where(Role.code == role_code))
        if user is None or store is None or role is None:
            raise ValueError("用户、店铺或角色不存在")
        existing = await session.scalar(
            select(user_roles.c.id).where(
                user_roles.c.user_id == user.id,
                user_roles.c.role_id == role.id,
                user_roles.c.store_id == store.id,
            )
        )
        if existing is None:
            await session.execute(
                insert(user_roles).values(id=uuid.uuid4(), user_id=user.id, role_id=role.id, store_id=store.id)
            )
            await session.commit()


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True)
    parser.add_argument("--store", required=True)
    parser.add_argument("--role", choices=("supervisor", "agent"), required=True)
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    asyncio.run(assign(arguments.email, arguments.store, arguments.role))
