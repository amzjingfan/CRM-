"""隔离 PostgreSQL 中核对配置持久化、店铺范围与不发送边界。"""

import os
import uuid

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.audit.models import AuditLog
from app.marketing.models import MarketingEvent
from app.reception import service
from app.reception.models import (
    ReceptionGroup,
    ReceptionMutation,
    ReceptionPolicy,
    ReceptionPolicyStore,
    ReceptionReply,
)
from app.reception.schemas import GroupCreate, GroupUpdate, PolicyCreate, PolicyUpdate, ReplyCreate, ReplyUpdate
from app.shared.database import models as _models  # noqa: F401
from app.shared.database.base import Role, User, user_roles
from app.shared.exceptions.errors import AppError
from app.stores.models import Store

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="未提供隔离的 PostgreSQL 测试数据库")


@pytest.mark.asyncio
async def test_reception_scope_idempotency_and_config_only() -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    first_store, second_store = uuid.uuid4(), uuid.uuid4()
    admin_id, manager_id, agent_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    try:
        async with sessions() as session:
            roles = {role.code: role.id for role in (await session.scalars(select(Role))).all()}
            users = [
                User(
                    id=admin_id, email=f"reception-{admin_id.hex}@example.com", password_hash="test-only", name="admin"
                ),
                User(
                    id=manager_id,
                    email=f"reception-{manager_id.hex}@example.com",
                    password_hash="test-only",
                    name="manager",
                ),
                User(
                    id=agent_id, email=f"reception-{agent_id.hex}@example.com", password_hash="test-only", name="agent"
                ),
            ]
            session.add_all(
                users
                + [
                    Store(id=first_store, name="Reception 1", code=f"reception_{first_store.hex}"),
                    Store(id=second_store, name="Reception 2", code=f"reception_{second_store.hex}"),
                ]
            )
            await session.flush()
            for user_id, role, store_id in (
                (admin_id, "admin", None),
                (manager_id, "supervisor", first_store),
                (agent_id, "agent", first_store),
            ):
                await session.execute(
                    user_roles.insert().values(id=uuid.uuid4(), user_id=user_id, role_id=roles[role], store_id=store_id)
                )
            await session.commit()
            admin, manager, agent = users

            team_group = await service.create_group(
                session, manager, GroupCreate(store_id=first_store, scope="team", name="Team"), "group-team"
            )
            personal_group = await service.create_group(
                session, agent, GroupCreate(store_id=first_store, scope="personal", name="Mine"), "group-personal"
            )
            assert (await service.list_groups(session, manager, first_store, "team", 1, 20)).total == 1
            assert (await service.list_groups(session, admin, first_store, "personal", 1, 20)).total == 0
            assert (await service.list_groups(session, agent, first_store, "personal", 1, 20)).total == 1
            with pytest.raises(AppError) as cross_store:
                await service.list_groups(session, agent, second_store, "personal", 1, 20)
            assert cross_store.value.status_code == 404

            reply_payload = ReplyCreate(
                store_id=first_store,
                scope="personal",
                group_id=personal_group.id,
                shortcut="welcome",
                tags=["greeting"],
                messages=["Hello", "How can I help?"],
            )
            reply = await service.create_reply(session, agent, reply_payload, "reply-once")
            replay = await service.create_reply(session, agent, reply_payload, "reply-once")
            assert replay.id == reply.id
            assert (
                await service.list_replies(session, agent, first_store, "personal", None, "Hello", 1, 20)
            ).total == 1
            with pytest.raises(AppError) as reused_key:
                await service.create_reply(
                    session, agent, reply_payload.model_copy(update={"shortcut": "different"}), "reply-once"
                )
            assert reused_key.value.status_code == 409
            with pytest.raises(AppError) as duplicate:
                await service.create_reply(
                    session,
                    agent,
                    ReplyCreate.model_validate(reply_payload.model_dump() | {"shortcut": "WELCOME"}),
                    "reply-twice",
                )
            assert duplicate.value.status_code == 409
            with pytest.raises(AppError) as nonempty_group:
                await service.delete_group(session, agent, personal_group.id, "delete-nonempty")
            assert nonempty_group.value.status_code == 409
            with pytest.raises(AppError) as team_write:
                await service.create_reply(
                    session,
                    agent,
                    ReplyCreate(
                        store_id=first_store, scope="team", group_id=team_group.id, shortcut="team", messages=["Hello"]
                    ),
                    "agent-team-write",
                )
            assert team_write.value.status_code == 403
            taken = await service.create_reply(
                session,
                agent,
                ReplyCreate(
                    store_id=first_store,
                    scope="personal",
                    group_id=personal_group.id,
                    shortcut="taken",
                    messages=["Other reply"],
                ),
                "reply-taken",
            )
            team_reply = await service.create_reply(
                session,
                manager,
                ReplyCreate(
                    store_id=first_store,
                    scope="team",
                    group_id=team_group.id,
                    shortcut="welcome",
                    messages=["Team welcome"],
                ),
                "team-welcome",
            )
            personal_match = await service.list_replies(
                session, agent, first_store, "personal", None, None, 1, 1, shortcut="WELCOME"
            )
            team_match = await service.list_replies(
                session, agent, first_store, "team", None, None, 1, 1, shortcut="welcome"
            )
            assert personal_match.total == 1 and personal_match.items[0].id == reply.id
            assert team_match.total == 1 and team_match.items[0].id == team_reply.id
            group_page = await service.list_groups(session, agent, first_store, "personal", 1, 20)
            assert group_page.items[0].reply_count == 2
            disabled = await service.update_group(
                session, agent, personal_group.id, GroupUpdate(enabled=False), "group-disable"
            )
            assert disabled.enabled is False
            assert (await service.list_replies(session, agent, first_store, "personal", None, None, 1, 20)).total == 0
            assert (
                await service.list_replies(
                    session, agent, first_store, "personal", None, None, 1, 20, include_disabled=True
                )
            ).total == 2
            assert (await service.list_groups(session, agent, first_store, "personal", 1, 20)).items[0].enabled is False
            await service.update_group(session, agent, personal_group.id, GroupUpdate(enabled=True), "group-enable")
            assert (
                await service.list_replies(session, agent, first_store, "team", None, None, 1, 1, shortcut="missing")
            ).total == 0
            with pytest.raises(AppError) as duplicate_update:
                await service.update_reply(
                    session,
                    agent,
                    reply.id,
                    ReplyUpdate(shortcut="TAKEN", messages=["Should not save"]),
                    "reply-duplicate-update",
                )
            assert duplicate_update.value.status_code == 409
            assert (await service.visible_reply(session, agent, reply.id)).shortcut == "welcome"
            assert (await service.visible_reply(session, agent, reply.id)).messages == ["Hello", "How can I help?"]
            changed = await service.update_reply(
                session, agent, reply.id, ReplyUpdate(messages=["Updated"], shortcut="HELLO"), "reply-update"
            )
            assert changed.messages == ["Updated"] and changed.shortcut == "hello"
            assert (
                await service.update_reply(
                    session, agent, reply.id, ReplyUpdate(messages=["Updated"], shortcut="hello"), "reply-update"
                )
            ).id == reply.id
            await service.delete_reply(session, agent, reply.id, "reply-delete")
            await service.delete_reply(session, agent, reply.id, "reply-delete")
            await service.delete_reply(session, agent, taken.id, "reply-taken-delete")
            await service.delete_group(session, agent, personal_group.id, "group-delete")
            assert (await service.list_groups(session, agent, first_store, "personal", 1, 20)).total == 0
            assert (
                await service.update_group(
                    session, manager, team_group.id, GroupUpdate(name="Team updated"), "group-update"
                )
            ).name == "Team updated"

            before_events = await session.scalar(select(func.count()).select_from(MarketingEvent))
            policy = await service.create_policy(
                session,
                admin,
                PolicyCreate(
                    kind="welcome", name="Welcome", content="Hello", enabled=True, store_ids=[first_store, second_store]
                ),
                "policy-multi-store",
            )
            assert policy.delivery_enabled is False and policy.enabled is True
            assert (await service.list_policies(session, manager, first_store, "welcome", 1, 20)).total == 0
            with pytest.raises(AppError) as hidden_policy:
                await service.visible_policy(session, manager, policy.id, write=True)
            assert hidden_policy.value.status_code == 404
            single_store = await service.create_policy(
                session,
                manager,
                PolicyCreate(
                    kind="timeout", name="Delay", content="Later", timeout_minutes=30, store_ids=[first_store]
                ),
                "policy-one-store",
            )
            with pytest.raises(AppError) as unauthorized_edit:
                await service.update_policy(
                    session,
                    manager,
                    single_store.id,
                    PolicyUpdate(store_ids=[first_store, second_store]),
                    "policy-unauthorized-edit",
                )
            assert unauthorized_edit.value.status_code == 404
            updated_policy = await service.update_policy(
                session, manager, single_store.id, PolicyUpdate(enabled=True, content="Later updated"), "policy-update"
            )
            assert updated_policy.enabled is True and updated_policy.delivery_enabled is False
            assert updated_policy.content == "Later updated"
            assert (
                await service.update_policy(
                    session,
                    manager,
                    single_store.id,
                    PolicyUpdate(enabled=True, content="Later updated"),
                    "policy-update",
                )
            ).id == single_store.id
            assert await session.scalar(select(func.count()).select_from(MarketingEvent)) == before_events
            audits = (
                await session.scalars(select(AuditLog).where(AuditLog.actor_id.in_([admin_id, manager_id, agent_id])))
            ).all()
            assert all("Hello" not in str(audit.after_data) for audit in audits)
    finally:
        async with sessions() as session:
            user_ids = [admin_id, manager_id, agent_id]
            store_ids = [first_store, second_store]
            await session.execute(delete(AuditLog).where(AuditLog.actor_id.in_(user_ids)))
            await session.execute(delete(ReceptionMutation).where(ReceptionMutation.actor_id.in_(user_ids)))
            await session.execute(delete(ReceptionReply).where(ReceptionReply.store_id.in_(store_ids)))
            await session.execute(delete(ReceptionGroup).where(ReceptionGroup.store_id.in_(store_ids)))
            policy_ids = select(ReceptionPolicy.id).where(ReceptionPolicy.created_by.in_(user_ids))
            await session.execute(delete(ReceptionPolicyStore).where(ReceptionPolicyStore.policy_id.in_(policy_ids)))
            await session.execute(delete(ReceptionPolicy).where(ReceptionPolicy.created_by.in_(user_ids)))
            await session.execute(delete(User).where(User.id.in_(user_ids)))
            await session.execute(delete(Store).where(Store.id.in_(store_ids)))
            await session.commit()
        await engine.dispose()
