"""隔离数据库中的持久幂等响应不冻结资格，也不把重放人冒充原授权人。"""

import os
import uuid

import pytest
from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.shared.database.models  # noqa: F401
from app.audit.models import AuditLog
from app.reception import service
from app.reception.models import ReceptionMutation, ReceptionPolicy
from app.reception.schemas import PolicyCreate, PolicyUpdate
from app.shared.database.base import Role, User, user_roles
from app.stores.models import Store

URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="未提供隔离 PostgreSQL")


@pytest.mark.asyncio
@pytest.mark.parametrize("legacy_author_missing", [False, True])
async def test_policy_views_recompute_current_eligibility_for_durable_replays(monkeypatch, legacy_author_missing):
    engine = create_async_engine(URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    store_id, author_id, editor_id = (uuid.uuid4() for _ in range(3))
    from app.shared.config.settings import Settings

    flags = Settings(_env_file=None).model_copy(
        update={"real_tiktok_automation_enabled": True, "auto_reply_enabled": True}
    )
    monkeypatch.setattr(service, "get_settings", lambda: flags)
    try:
        async with sessions() as session:
            session.add(Store(id=store_id, name="合成接待资格店", code=f"reception-view-{store_id.hex}"))
            session.add_all(
                [
                    User(id=actor, name="合成坐席", password_hash="unused", email=f"{actor.hex}@example.test")
                    for actor in (author_id, editor_id)
                ]
            )
            await session.flush()
            role_id = await session.scalar(select(Role.id).where(Role.code == "admin"))
            for actor in (author_id, editor_id):
                await session.execute(insert(user_roles).values(user_id=actor, role_id=role_id, store_id=store_id))
            await session.commit()
        async with sessions() as session:
            author = await session.get(User, author_id)
            payload = PolicyCreate(
                kind="welcome",
                name="合成欢迎",
                content="您好",
                content_en="Hello",
                delivery_mode="auto",
                enabled=True,
                store_ids=[store_id],
            )
            original = await service.create_policy(session, author, payload, "create-policy")
            assert original.delivery_enabled and original.authorized_by == author_id
            page = await service.list_policies(session, author, store_id, "welcome", 1, 20)
            assert page.items[0].delivery_enabled
            audit = await session.scalar(
                select(AuditLog).where(
                    AuditLog.resource_id == original.id, AuditLog.action == "reception.policy.create"
                )
            )
            assert audit.after_data["delivery_enabled"] is True
            mutation = await session.scalar(select(ReceptionMutation).where(ReceptionMutation.actor_id == author_id))
            historic = {**mutation.response_body, "delivery_enabled": False}
            if legacy_author_missing:
                historic.pop("authorized_by")
            mutation.response_body = historic
            await session.commit()
            replay = await service.create_policy(session, author, payload, "create-policy")
            assert replay.delivery_enabled and replay.authorized_by == author_id
            flags.auto_reply_enabled = False
            assert not (await service.create_policy(session, author, payload, "create-policy")).delivery_enabled
            flags.auto_reply_enabled = True
            flags.real_tiktok_automation_enabled = False
            assert not (await service.create_policy(session, author, payload, "create-policy")).delivery_enabled
            assert (
                not (await service.list_policies(session, author, store_id, "welcome", 1, 20)).items[0].delivery_enabled
            )
            flags.real_tiktok_automation_enabled = True
            async with sessions() as other:
                editor = await other.get(User, editor_id)
                changed = await service.update_policy(
                    other, editor, original.id, PolicyUpdate(enabled=False), "disable-policy"
                )
                assert not changed.delivery_enabled and changed.authorized_by == editor_id
            # 原会话有未过期 ORM 实例，仍须读取另一事务最新开关，不能被旧响应或 identity map 误导。
            replay = await service.create_policy(session, author, payload, "create-policy")
            assert replay.enabled is True and replay.delivery_enabled is False
            assert replay.authorized_by == (editor_id if legacy_author_missing else author_id)
            stored = await session.scalar(select(ReceptionMutation).where(ReceptionMutation.actor_id == author_id))
            assert stored.response_body["delivery_enabled"] is False
    finally:
        async with sessions() as session:
            await session.execute(delete(ReceptionPolicy).where(ReceptionPolicy.created_by == author_id))
            await session.execute(delete(Store).where(Store.id == store_id))
            await session.execute(delete(User).where(User.id.in_([author_id, editor_id])))
            await session.commit()
        await engine.dispose()
