"""部门统一配置、主管范围和登录在线状态的真实数据库边界。"""

import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.auth.security import create_access_token
from app.auth.service import resolve_access_user
from app.auth.store_access import allowed_store_ids_for_permission, supervised_store_ids
from app.conversations.models import Conversation
from app.customers.models import Customer
from app.reception_assignment.dispatch import dispatch_conversation
from app.reception_assignment.schemas import ReceptionDepartmentAgentInput, ReceptionDepartmentInput
from app.reception_assignment.service import configure_department_reception, get_department_reception
from app.shared.database.base import Role, User, UserLoginSession, user_roles
from app.shared.exceptions.errors import AppError
from app.stores.models import Store
from app.users.models import Department, department_members, department_stores
from app.users.service import list_team

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="需要隔离 PostgreSQL 测试库")


@pytest.mark.asyncio
async def test_department_configuration_and_supervisor_scope_follow_login_session() -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    ids = [uuid.uuid4() for _ in range(7)]
    first, second, outside, department_id, admin_id, supervisor_id, agent_id = ids
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
                            Store(id=first, name="接待一店", code=f"reception_{first.hex}", status="active"),
                            Store(id=second, name="接待二店", code=f"reception_{second.hex}", status="active"),
                            Store(id=outside, name="部门外店", code=f"reception_{outside.hex}", status="active"),
                            Department(id=department_id, name=f"接待部 {department_id.hex}"),
                            User(
                                id=admin_id,
                                email=f"admin-{admin_id.hex}@example.invalid",
                                name="管理员",
                                password_hash="test",
                            ),
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
                    for store_id in (first, second):
                        await session.execute(
                            department_stores.insert().values(department_id=department_id, store_id=store_id)
                        )
                    for user_id in (admin_id, supervisor_id, agent_id):
                        await session.execute(
                            department_members.insert().values(department_id=department_id, user_id=user_id)
                        )
                    for user_id, role, store_id in (
                        (admin_id, "admin", None),
                        (supervisor_id, "supervisor", first),
                        (agent_id, "agent", second),
                    ):
                        await session.execute(
                            user_roles.insert().values(user_id=user_id, role_id=roles[role], store_id=store_id)
                        )
                    await session.flush()
                    admin = await session.get(User, admin_id)
                    supervisor = await session.get(User, supervisor_id)
                    assert admin is not None and supervisor is not None
                    assert await supervised_store_ids(session, supervisor) == {first, second}
                    assert await allowed_store_ids_for_permission(session, supervisor, "workspace.reply") == {
                        first,
                        second,
                    }
                    assert await allowed_store_ids_for_permission(session, supervisor, "settings.team") == {
                        first,
                        second,
                    }
                    directory = await list_team(session, supervisor)
                    admin_entry = next(item for item in directory if item.id == admin_id)
                    assert admin_entry.name == "管理员"
                    assert admin_entry.login_name == f"admin-{admin_id.hex}@example.invalid"
                    assert admin_entry.email is None and admin_entry.phone is None
                    assert (await get_department_reception(session, supervisor, department_id)).enabled is False
                    initial = await get_department_reception(session, admin, department_id)
                    assert initial.enabled is False
                    by_id = {item.user_id: item for item in initial.agents}
                    assert by_id[admin_id].active is True
                    assert set(by_id[admin_id].eligible_store_ids) == {first, second}
                    assert set(by_id[supervisor_id].eligible_store_ids) == {first, second}
                    assert by_id[agent_id].eligible_store_ids == [second]
                    with pytest.raises(AppError):
                        await configure_department_reception(
                            session, supervisor, department_id, ReceptionDepartmentInput(enabled=True)
                        )
                    configured = await configure_department_reception(
                        session,
                        admin,
                        department_id,
                        ReceptionDepartmentInput(
                            enabled=True,
                            agents=[
                                ReceptionDepartmentAgentInput(user_id=supervisor_id, auto_enabled=True),
                                ReceptionDepartmentAgentInput(user_id=agent_id, auto_enabled=True),
                            ],
                        ),
                    )
                    assert configured.enabled is True
                    assert all(item.auto_enabled for item in configured.agents if item.user_id != admin_id)
                    assert not any(item.online for item in configured.agents)
                    configured = await configure_department_reception(
                        session,
                        admin,
                        department_id,
                        ReceptionDepartmentInput(
                            enabled=True,
                            agents=[ReceptionDepartmentAgentInput(user_id=admin_id, auto_enabled=True)],
                        ),
                    )
                    assert next(item for item in configured.agents if item.user_id == admin_id).auto_enabled is True
                    admin_login = UserLoginSession(user_id=admin_id, expires_at=datetime.now(UTC) + timedelta(days=1))
                    customer_id = uuid.uuid4()
                    session.add_all(
                        [
                            admin_login,
                            Customer(
                                id=customer_id, store_id=first, platform="tiktok", external_customer_id=customer_id.hex
                            ),
                        ]
                    )
                    await session.flush()
                    conversation = Conversation(
                        store_id=first,
                        customer_id=customer_id,
                        platform="tiktok",
                        external_conversation_id=f"admin_dispatch_{uuid.uuid4().hex}",
                        awaiting_reply_since=datetime.now(UTC),
                    )
                    session.add(conversation)
                    await session.flush()
                    assert await dispatch_conversation(session, conversation.id) == admin_id
                    login = UserLoginSession(user_id=supervisor_id, expires_at=datetime.now(UTC) + timedelta(days=1))
                    session.add(login)
                    await session.commit()
                    refreshed = await get_department_reception(session, admin, department_id)
                    assert next(item for item in refreshed.agents if item.user_id == supervisor_id).online is True
                    token = create_access_token(supervisor_id, session_id=login.id)
                    assert (await resolve_access_user(session, token)).id == supervisor_id
                    login.revoked_at = datetime.now(UTC)
                    await session.commit()
                    with pytest.raises(AppError) as revoked_access:
                        await resolve_access_user(session, token)
                    assert revoked_access.value.status_code == 401
                    offline = await get_department_reception(session, admin, department_id)
                    assert next(item for item in offline.agents if item.user_id == supervisor_id).online is False
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()
