"""隔离 PostgreSQL 验证账号登录和部门关系的完整数据库路径。"""

import os
import uuid

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.audit.models import AuditLog
from app.auth.service import authenticate_user
from app.shared.database.base import Role, User, user_roles
from app.stores.models import Store
from app.users.department_schemas import DepartmentCreate
from app.users.department_service import create_department, remove_member
from app.users.models import Department, department_members
from app.users.schemas import TeamMemberCreate, TeamRoleAssignment
from app.users.service import create_member

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="未提供隔离的 PostgreSQL 测试数据库")


@pytest.mark.asyncio
async def test_username_login_and_department_removal_keep_store_role() -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    actor_id, store_id = uuid.uuid4(), uuid.uuid4()
    member_id: uuid.UUID | None = None
    department_id: uuid.UUID | None = None
    try:
        async with sessions() as session:
            admin_role = await session.scalar(select(Role).where(Role.code == "admin"))
            assert admin_role is not None
            actor = User(
                id=actor_id,
                email=f"team-admin-{actor_id.hex}@example.com",
                password_hash="test-only",
                name="测试管理员",
                status="active",
            )
            store = Store(id=store_id, name="部门测试店铺", code=f"dept_{store_id.hex}", status="active")
            session.add_all([actor, store])
            await session.flush()
            await session.execute(
                user_roles.insert().values(
                    id=uuid.uuid4(),
                    user_id=actor_id,
                    role_id=admin_role.id,
                    store_id=None,
                )
            )
            await session.commit()

            department = await create_department(
                session, actor, DepartmentCreate(name=f"测试部门 {store_id.hex}", store_ids=[store_id])
            )
            department_id = department.id
            login_name = f"agent_{store_id.hex[:8]}"
            member = await create_member(
                session,
                actor,
                TeamMemberCreate(
                    login_name=login_name,
                    name="测试客服",
                    email=None,
                    temporary_password="ExamplePass123!",
                    assignments=[TeamRoleAssignment(role="agent", store_id=store_id)],
                    department_id=department_id,
                ),
            )
            member_id = member.id
            assert member.email is None
            assert member.department_ids == [department_id]
            assert (await authenticate_user(session, login_name.upper(), "ExamplePass123!")).id == member_id

            await remove_member(session, actor, department_id, member_id)
            assert (
                await session.scalar(
                    select(department_members.c.user_id).where(department_members.c.user_id == member_id)
                )
                is None
            )
            assert (
                await session.scalar(select(user_roles.c.store_id).where(user_roles.c.user_id == member_id)) == store_id
            )
    finally:
        async with sessions() as session:
            await session.execute(delete(AuditLog).where(AuditLog.actor_id == actor_id))
            if department_id is not None:
                await session.execute(delete(Department).where(Department.id == department_id))
            await session.execute(delete(User).where(User.id.in_([item for item in [actor_id, member_id] if item])))
            await session.execute(delete(Store).where(Store.id == store_id))
            await session.commit()
        await engine.dispose()
