"""认证领域数据库访问。"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.database.base import Permission, Role, User


async def find_user_by_email(session: AsyncSession, email: str) -> User | None:
    """按邮箱查找用户并预加载角色权限。"""
    result = await session.execute(select(User).where(User.email == email.lower()))
    return result.scalar_one_or_none()


async def find_user_by_login_name(session: AsyncSession, login_name: str) -> User | None:
    """按不可变登录账号查找用户。"""
    result = await session.execute(select(User).where(User.login_name == login_name.lower()))
    return result.scalar_one_or_none()


async def find_user_by_id(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    """按内部 ID 查询用户。"""
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def find_role_by_code(session: AsyncSession, code: str) -> Role | None:
    """按角色编码查询角色。"""
    result = await session.execute(select(Role).where(Role.code == code))
    return result.scalar_one_or_none()


async def find_permission_by_code(session: AsyncSession, code: str) -> Permission | None:
    """按权限编码查询权限。"""
    result = await session.execute(select(Permission).where(Permission.code == code))
    return result.scalar_one_or_none()
