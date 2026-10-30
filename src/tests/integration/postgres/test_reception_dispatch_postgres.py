"""部门多店派单按逐店权限、登录状态和跨店负载执行。"""

import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.conversations.models import Conversation
from app.customers.models import Customer
from app.reception_assignment.dispatch import dispatch_conversation, requeue_offline_auto_assignments
from app.reception_assignment.models import ReceptionDepartmentAgent, ReceptionDepartmentConfig
from app.shared.database.base import Role, User, UserLoginSession, user_roles
from app.stores.models import Store
from app.users.models import Department, department_members, department_stores
from app.workspace.service import list_session_assignees

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="需要隔离 PostgreSQL 测试库")


@pytest.mark.asyncio
async def test_department_dispatch_across_stores_and_requeue_after_logout() -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    store_a, store_b, department_id, supervisor_id, agent_id = (uuid.uuid4() for _ in range(5))
    now = datetime.now(UTC)
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            try:
                async with AsyncSession(
                    bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
                ) as session:
                    roles = dict((await session.execute(select(Role.code, Role.id))).all())
                    session.add_all(
                        [
                            Store(id=store_a, name="派单一店", code=f"dispatch_{store_a.hex}", status="active"),
                            Store(id=store_b, name="派单二店", code=f"dispatch_{store_b.hex}", status="active"),
                            Department(id=department_id, name=f"派单部 {department_id.hex}"),
                            User(
                                id=supervisor_id,
                                login_name=f"s{supervisor_id.hex[:12]}",
                                name="主管",
                                password_hash="test",
                            ),
                            User(id=agent_id, login_name=f"g{agent_id.hex[:12]}", name="客服", password_hash="test"),
                        ]
                    )
                    await session.flush()
                    for store_id in (store_a, store_b):
                        await session.execute(
                            department_stores.insert().values(department_id=department_id, store_id=store_id)
                        )
                    for user_id in (supervisor_id, agent_id):
                        await session.execute(
                            department_members.insert().values(department_id=department_id, user_id=user_id)
                        )
                    await session.execute(
                        user_roles.insert().values(user_id=supervisor_id, role_id=roles["supervisor"], store_id=store_a)
                    )
                    await session.execute(
                        user_roles.insert().values(user_id=agent_id, role_id=roles["agent"], store_id=store_b)
                    )
                    supervisor_login = UserLoginSession(user_id=supervisor_id, expires_at=now + timedelta(days=1))
                    agent_login = UserLoginSession(user_id=agent_id, expires_at=now + timedelta(days=1))
                    session.add_all(
                        [
                            ReceptionDepartmentConfig(department_id=department_id, enabled=True),
                            ReceptionDepartmentAgent(
                                department_id=department_id, user_id=supervisor_id, auto_enabled=True
                            ),
                            ReceptionDepartmentAgent(department_id=department_id, user_id=agent_id, auto_enabled=True),
                            supervisor_login,
                            agent_login,
                        ]
                    )
                    customer_a, customer_b = uuid.uuid4(), uuid.uuid4()
                    session.add_all(
                        [
                            Customer(
                                id=customer_a, store_id=store_a, platform="tiktok", external_customer_id=customer_a.hex
                            ),
                            Customer(
                                id=customer_b, store_id=store_b, platform="tiktok", external_customer_id=customer_b.hex
                            ),
                        ]
                    )
                    await session.flush()
                    first = Conversation(
                        store_id=store_a,
                        customer_id=customer_a,
                        platform="tiktok",
                        external_conversation_id=f"dispatch_{uuid.uuid4().hex}",
                        awaiting_reply_since=now,
                    )
                    second = Conversation(
                        store_id=store_b,
                        customer_id=customer_b,
                        platform="tiktok",
                        external_conversation_id=f"dispatch_{uuid.uuid4().hex}",
                        awaiting_reply_since=now,
                    )
                    session.add_all([first, second])
                    await session.flush()
                    supervisor = await session.get(User, supervisor_id)
                    assert supervisor is not None
                    assert {item.id for item in await list_session_assignees(session, supervisor, second.id)} == {
                        supervisor_id,
                        agent_id,
                    }
                    assert await dispatch_conversation(session, first.id, now=now) == supervisor_id
                    assert await dispatch_conversation(session, second.id, now=now) == agent_id
                    assert first.assignment_source == second.assignment_source == "auto"
                    agent_login.revoked_at = now + timedelta(seconds=1)
                    await session.flush()
                    assert await requeue_offline_auto_assignments(session, now=now + timedelta(minutes=3)) == 1
                    assert second.assigned_user_id == supervisor_id
                    assert first.assigned_user_id == supervisor_id
                    second.assignment_source = "manual"
                    supervisor_login.revoked_at = now + timedelta(minutes=3)
                    await session.flush()
                    assert await requeue_offline_auto_assignments(session, now=now + timedelta(minutes=6)) == 0
                    assert second.assigned_user_id == supervisor_id
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()
