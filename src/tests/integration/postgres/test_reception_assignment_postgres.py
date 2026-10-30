"""单客服部接待设置的数据库默认值和隔离键。"""

import os
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.audit.models import AuditLog
from app.conversations.models import Conversation
from app.customers.models import Customer
from app.reception_assignment.models import ReceptionAgentConfig, ReceptionStoreConfig
from app.reception_assignment.schemas import ReceptionAgentInput, ReceptionStoreInput
from app.reception_assignment.service import configure_store_reception, get_store_reception, heartbeat
from app.shared.database.base import Role, User, user_roles
from app.shared.exceptions.errors import AppError
from app.stores.models import Store
from app.users.models import Department, department_members, department_stores
from app.users.schemas import TeamMemberUpdate, TeamRoleAssignment
from app.users.service import update_member
from app.workspace.service import get_session_messages

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="未提供隔离的 PostgreSQL 测试数据库")


@pytest.mark.asyncio
async def test_reception_configuration_defaults_off_and_keeps_store_agent_pair_unique() -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    store_id, department_id, agent_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    try:
        async with sessions() as session:
            session.add_all(
                [
                    Store(id=store_id, name="接待测试店铺", code=f"assign_{store_id.hex}", status="active"),
                    Department(id=department_id, name=f"客服部 {department_id.hex}"),
                    User(id=agent_id, login_name=f"agent_{agent_id.hex[:8]}", name="测试客服", password_hash="test"),
                ]
            )
            await session.flush()
            await session.execute(department_stores.insert().values(department_id=department_id, store_id=store_id))
            session.add(ReceptionStoreConfig(store_id=store_id, department_id=department_id))
            session.add(ReceptionAgentConfig(store_id=store_id, user_id=agent_id))
            await session.commit()

        async with sessions() as session:
            store_config = await session.scalar(
                select(ReceptionStoreConfig).where(ReceptionStoreConfig.store_id == store_id)
            )
            agent_config = await session.scalar(
                select(ReceptionAgentConfig).where(
                    ReceptionAgentConfig.store_id == store_id,
                    ReceptionAgentConfig.user_id == agent_id,
                )
            )
            assert store_config is not None and store_config.enabled is False
            assert agent_config is not None and agent_config.auto_enabled is False
            assert agent_config.capacity == 20
            assert agent_config.last_heartbeat_at is None
    finally:
        async with sessions() as session:
            await session.execute(delete(ReceptionAgentConfig).where(ReceptionAgentConfig.store_id == store_id))
            await session.execute(delete(ReceptionStoreConfig).where(ReceptionStoreConfig.store_id == store_id))
            await session.execute(delete(Department).where(Department.id == department_id))
            await session.execute(delete(User).where(User.id == agent_id))
            await session.execute(delete(Store).where(Store.id == store_id))
            await session.commit()
        await engine.dispose()


@pytest.mark.asyncio
async def test_only_admin_configures_and_only_eligible_agent_sends_own_heartbeat() -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    store_id, department_id, agent_id, admin_id = (uuid.uuid4() for _ in range(4))
    try:
        async with sessions() as session:
            admin_role = await session.scalar(select(Role).where(Role.code == "admin"))
            agent_role = await session.scalar(select(Role).where(Role.code == "agent"))
            assert admin_role is not None and agent_role is not None
            admin = User(id=admin_id, login_name=f"ad{admin_id.hex[:12]}", name="管理员", password_hash="test")
            agent = User(id=agent_id, login_name=f"ag{agent_id.hex[:12]}", name="客服", password_hash="test")
            admin.roles = [admin_role]
            session.add_all(
                [
                    Store(id=store_id, name="接待权限测试店铺", code=f"access_{store_id.hex}", status="active"),
                    Department(id=department_id, name=f"接待部 {department_id.hex}"),
                    admin,
                    agent,
                ]
            )
            await session.flush()
            await session.execute(department_stores.insert().values(department_id=department_id, store_id=store_id))
            await session.execute(department_members.insert().values(department_id=department_id, user_id=agent_id))
            await session.execute(
                user_roles.insert().values(user_id=agent_id, role_id=agent_role.id, store_id=store_id)
            )
            payload = ReceptionStoreInput(
                enabled=True,
                agents=[ReceptionAgentInput(user_id=agent_id, auto_enabled=True, capacity=2)],
            )
            with pytest.raises(AppError):
                await configure_store_reception(session, agent, department_id, store_id, payload)
            view = await configure_store_reception(session, admin, department_id, store_id, payload)
            assert view.enabled and view.agents[0].auto_enabled and not view.agents[0].online
            reception_audit = await session.scalar(
                select(AuditLog).where(
                    AuditLog.action == "reception.assignment.configure", AuditLog.store_id == store_id
                )
            )
            assert reception_audit is not None
            assert reception_audit.after_data == {
                "enabled": True,
                "agents": [{"user_id": str(agent_id), "auto_enabled": True, "capacity": 2}],
            }
            own_presence = await heartbeat(session, agent, store_id, accepting=True)
            assert own_presence.store_id == store_id and own_presence.accepting
            paused = await heartbeat(session, agent, store_id, accepting=False)
            assert paused.accepting is False
            await update_member(
                session,
                admin,
                agent_id,
                TeamMemberUpdate(assignments=[TeamRoleAssignment(role="supervisor", store_id=store_id)]),
            )
            role_audit = await session.scalar(
                select(AuditLog)
                .where(AuditLog.action == "team.member.update", AuditLog.resource_id == agent_id)
                .order_by(AuditLog.created_at.desc())
            )
            assert role_audit is not None
            assert role_audit.before_data == {"assignments": [{"role": "agent", "store_id": str(store_id)}]}
            assert role_audit.after_data is not None
            assert role_audit.after_data["assignments"] == [{"role": "supervisor", "store_id": str(store_id)}]
            await session.execute(
                delete(user_roles).where(user_roles.c.user_id == agent_id, user_roles.c.store_id == store_id)
            )
            await session.commit()
            with pytest.raises(AppError):
                await heartbeat(session, agent, store_id, accepting=True)
            customer_external_id = uuid.uuid4().hex
            customer = Customer(store_id=store_id, platform="tiktok", external_customer_id=customer_external_id)
            session.add(customer)
            await session.flush()
            conversation = Conversation(
                store_id=store_id,
                customer_id=customer.id,
                platform="tiktok",
                external_conversation_id=f"takeover_{customer_external_id}",
                assigned_user_id=agent_id,
                assignment_source="manual",
                awaiting_reply_since=datetime.now(UTC),
            )
            session.add(conversation)
            await session.flush()
            session.add(
                AuditLog(
                    store_id=store_id,
                    actor_type="user",
                    actor_id=admin_id,
                    action="conversation.assign",
                    resource_type="conversation",
                    resource_id=conversation.id,
                    after_data={"assigned_user_id": str(agent_id)},
                    result="succeeded",
                )
            )
            await session.commit()
            status = await get_store_reception(session, admin, department_id, store_id)
            assert status.takeover_count == 1 and status.takeover_conversation_ids == [conversation.id]
            detail = await get_session_messages(session, admin, conversation.id, 1, 20)
            assert detail.session.needs_takeover and detail.session.can_manage
            assert [event.action for event in detail.assignment_events] == ["conversation.assign"]
    finally:
        async with sessions() as session:
            await session.execute(delete(AuditLog).where(AuditLog.store_id == store_id))
            await session.execute(delete(Conversation).where(Conversation.store_id == store_id))
            await session.execute(delete(Customer).where(Customer.store_id == store_id))
            await session.execute(delete(ReceptionAgentConfig).where(ReceptionAgentConfig.store_id == store_id))
            await session.execute(delete(ReceptionStoreConfig).where(ReceptionStoreConfig.store_id == store_id))
            await session.execute(delete(department_members).where(department_members.c.department_id == department_id))
            await session.execute(delete(department_stores).where(department_stores.c.department_id == department_id))
            await session.execute(delete(user_roles).where(user_roles.c.user_id.in_([agent_id, admin_id])))
            await session.execute(delete(User).where(User.id.in_([agent_id, admin_id])))
            await session.execute(delete(Department).where(Department.id == department_id))
            await session.execute(delete(Store).where(Store.id == store_id))
            await session.commit()
        await engine.dispose()
