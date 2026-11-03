"""隔离 PostgreSQL 验证主管知识权限的迁移与部门范围。"""

import os
import uuid

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.auth.store_access import allowed_store_ids_for_permission
from app.shared.database.base import Permission, Role, User, role_permissions, user_roles
from app.stores.models import Store
from app.users.models import Department, department_members, department_stores

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="未提供隔离的 PostgreSQL 测试数据库")


@pytest.mark.asyncio
async def test_supervisor_manages_only_active_department_stores_and_loses_scope_after_removal() -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    user_id, department_id = uuid.uuid4(), uuid.uuid4()
    assigned_store, sibling_store, outside_store = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    try:
        async with sessions() as session:
            supervisor_role = await session.scalar(select(Role).where(Role.code == "supervisor"))
            agent_role = await session.scalar(select(Role).where(Role.code == "agent"))
            assert supervisor_role is not None and agent_role is not None
            manage_grant = await session.scalar(
                select(role_permissions.c.permission_id)
                .join(Permission, Permission.id == role_permissions.c.permission_id)
                .where(role_permissions.c.role_id == supervisor_role.id, Permission.code == "knowledge.manage")
            )
            assert manage_grant is not None
            user = User(
                id=user_id,
                login_name=f"kb_{user_id.hex[:12]}",
                password_hash="test-only",
                name="主管知识权限测试",
                status="active",
            )
            department = Department(id=department_id, name=f"knowledge-test-{department_id.hex}")
            stores = [
                Store(id=assigned_store, code=f"knowledge-{assigned_store.hex}", name="Assigned", status="active"),
                Store(id=sibling_store, code=f"knowledge-{sibling_store.hex}", name="Sibling", status="active"),
                Store(id=outside_store, code=f"knowledge-{outside_store.hex}", name="Outside", status="active"),
            ]
            session.add_all([user, department, *stores])
            await session.flush()
            await session.execute(
                user_roles.insert(),
                [
                    {"id": uuid.uuid4(), "user_id": user_id, "role_id": supervisor_role.id, "store_id": assigned_store},
                    {"id": uuid.uuid4(), "user_id": user_id, "role_id": agent_role.id, "store_id": outside_store},
                ],
            )
            await session.execute(
                department_stores.insert(),
                [
                    {"department_id": department_id, "store_id": assigned_store},
                    {"department_id": department_id, "store_id": sibling_store},
                ],
            )
            await session.execute(department_members.insert().values(department_id=department_id, user_id=user_id))

            assert await allowed_store_ids_for_permission(session, user, "knowledge.manage") == {
                assigned_store,
                sibling_store,
            }
            assert await allowed_store_ids_for_permission(session, user, "knowledge.view") == {
                assigned_store,
                sibling_store,
            }
            await session.execute(delete(department_members).where(department_members.c.user_id == user_id))
            assert await allowed_store_ids_for_permission(session, user, "knowledge.manage") == set()
            await session.rollback()
    finally:
        await engine.dispose()
