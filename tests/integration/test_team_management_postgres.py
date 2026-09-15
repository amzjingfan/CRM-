"""在隔离 PostgreSQL 中验证团队禁用与永久删除闭环。"""

import os
import uuid

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.audit.models import AuditLog
from app.shared.database.base import User
from app.shared.exceptions.errors import AppError
from app.users.service import delete_member_permanently, disable_member

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="未提供隔离的 PostgreSQL 测试数据库")


@pytest.mark.asyncio
async def test_disabled_member_can_be_permanently_deleted() -> None:
    """有效员工必须先禁用，随后才能永久删除并保留审计记录。"""
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    actor = User(
        id=uuid.uuid4(),
        email=f"team-actor-{uuid.uuid4().hex}@example.com",
        password_hash="test-only",
        name="测试管理员",
        status="active",
    )
    target = User(
        id=uuid.uuid4(),
        email=f"team-target-{uuid.uuid4().hex}@example.com",
        password_hash="test-only",
        name="待删除员工",
        status="active",
    )
    try:
        async with sessions() as session:
            session.add_all([actor, target])
            await session.commit()

            with pytest.raises(AppError, match="请先禁用员工"):
                await delete_member_permanently(session, actor, target.id)

            await disable_member(session, actor, target.id)
            await delete_member_permanently(session, actor, target.id)

            assert await session.get(User, target.id) is None
            actions = set(
                await session.scalars(
                    select(AuditLog.action).where(
                        AuditLog.resource_type == "user",
                        AuditLog.resource_id == target.id,
                    )
                )
            )
            assert actions == {"team.member.disable", "team.member.delete"}
    finally:
        async with sessions() as session:
            await session.execute(delete(AuditLog).where(AuditLog.resource_id.in_({actor.id, target.id})))
            await session.execute(delete(User).where(User.id.in_({actor.id, target.id})))
            await session.commit()
        await engine.dispose()
