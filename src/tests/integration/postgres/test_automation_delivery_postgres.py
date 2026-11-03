"""普通自动投递在隔离 PostgreSQL 中的认领、现权和零外发捕获。"""

import asyncio
import os
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.agents.automation.eligibility import content_hash
from app.agents.automation.models import AutomationDelivery
from app.agents.automation.service import claim_delivery, enqueue_delivery, process_delivery, recover_expired_deliveries
from app.agents.management.config_models import AgentConfig, AgentTask
from app.agents.management.models import AgentConfigVersion
from app.agents.runtime.models import AgentRun
from app.conversations.models import Conversation, Message
from app.customers.models import Customer
from app.integrations.schemas import SendMessageResult
from app.shared.config.settings import Settings
from app.shared.database import models as registered_models  # noqa: F401
from app.shared.database.base import Role, User, user_roles
from app.stores.models import ChannelAccount, Store

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="需要隔离 PostgreSQL 测试库")


@pytest_asyncio.fixture
async def automation_db():
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    store_id, user_id, customer_id, conversation_id, trigger_id, agent_id, run_id = (uuid.uuid4() for _ in range(7))
    now = datetime.now(UTC)
    async with factory() as session:
        session.add_all(
            [
                Store(
                    id=store_id,
                    name="自动投递合成测试",
                    code=f"auto_{store_id.hex}",
                    status="active",
                    metadata_json={
                        "agent_automation": {
                            "mode": "auto",
                            "revision": 1,
                            "authorized_by": str(user_id),
                            "enabled_at": (now - timedelta(minutes=2)).isoformat(),
                        }
                    },
                ),
                User(
                    id=user_id,
                    name="测试管理员",
                    login_name=f"a{user_id.hex[:12]}",
                    password_hash="synthetic",
                    status="active",
                ),
            ]
        )
        await session.flush()
        role = await session.scalar(select(Role.id).where(Role.code == "admin"))
        assert role is not None
        await session.execute(user_roles.insert().values(user_id=user_id, role_id=role, store_id=None))
        session.add(
            Customer(id=customer_id, store_id=store_id, platform="tiktok", external_customer_id="synthetic-buyer")
        )
        session.add(
            ChannelAccount(
                id=uuid.uuid4(),
                store_id=store_id,
                platform="tiktok",
                external_store_id=f"auto_{store_id.hex}",
                display_name="synthetic",
                access_token_ref="unused-capture",
                status="connected",
                token_expires_at=now + timedelta(days=1),
                scopes=["seller.order.info", "seller.customer_service", "seller.logistics"],
                metadata_json={},
            )
        )
        session.add(
            AgentConfig(
                id=agent_id, store_id=store_id, name="合成Agent", code="service", status="enabled", published_version=2
            )
        )
        await session.flush()
        session.add(
            AgentConfigVersion(
                id=uuid.uuid4(),
                store_id=store_id,
                agent_config_id=agent_id,
                version=2,
                name="合成Agent",
                code="service",
                agent_type="service",
                model_provider="deepseek",
                model_name="deepseek-chat",
                ready_for_v2=True,
            )
        )
        session.add(
            Conversation(
                id=conversation_id,
                store_id=store_id,
                customer_id=customer_id,
                platform="tiktok",
                external_conversation_id="123456789",
                status="active",
                metadata_json={},
            )
        )
        await session.flush()
        session.add(
            Message(
                id=trigger_id,
                store_id=store_id,
                conversation_id=conversation_id,
                customer_id=customer_id,
                platform="tiktok",
                external_message_id=f"auto_{trigger_id.hex}",
                content="Where is my order?",
                role="user",
                direction="inbound",
                status="received",
                created_at=now - timedelta(minutes=1),
            )
        )
        await session.flush()
        session.add(
            AgentRun(
                id=run_id,
                store_id=store_id,
                agent_config_id=agent_id,
                conversation_id=conversation_id,
                trigger_message_id=trigger_id,
                model_provider="deepseek",
                model_name="deepseek-chat",
                action="human_review",
                status="succeeded",
                phase="review_ready",
                snapshot_ref={
                    "automation_eligibility": {
                        "eligible": True,
                        "review_phase": "review_ready",
                        "review_version": "independent-evidence-privacy-v1",
                        "content_hashes": [content_hash("Verified reply"), content_hash("Second verified reply")],
                        "required_permissions": ["orders.view"],
                        "agent_versions": [[str(agent_id), 2]],
                        "file_versions": [],
                    }
                },
            )
        )
        await session.commit()
    settings = Settings(_env_file=None).model_copy(
        update={
            "app_env": "test",
            "real_tiktok_automation_enabled": True,
            "auto_reply_enabled": True,
            "real_tiktok_message_write_enabled": True,
            "real_tiktok_read_enabled": True,
            "tiktok_message_write_allowed_store_ids": str(store_id),
        }
    )
    values = dict(
        store_id=store_id,
        conversation_id=conversation_id,
        source_kind="agent",
        source_key=str(trigger_id),
        content="Verified reply",
        authorized_by=user_id,
        policy_revision=1,
        mode="auto",
        trigger_message_id=trigger_id,
        agent_run_id=run_id,
        authorization_json={"conversation_revision": 0},
    )
    try:
        yield factory, settings, values
    finally:
        async with factory() as session:
            await session.execute(delete(Store).where(Store.id == store_id))
            await session.execute(delete(User).where(User.id == user_id))
            await session.commit()
        await engine.dispose()


async def enqueue(factory, values):
    async with factory() as session:
        row = await enqueue_delivery(session, **values)
        await session.commit()
        return row.id


@pytest.mark.asyncio
@pytest.mark.parametrize("source_kind", ["agent", "welcome", "timeout", "logistics_discovery"])
@pytest.mark.parametrize("window", [True, False, None])
async def test_official_http_contract_reaches_delivery_only_with_explicit_current_window(
    automation_db, monkeypatch, source_kind, window
):
    """详情缺字段、列表分页的真实解析贯穿数据库和末端发送；只捕获合成消息。"""
    import httpx
    from pydantic import SecretStr

    from app.agents.tools.logistics_updates import authorization as remote_auth
    from app.integrations.credential_crypto import encrypt_credential
    from app.integrations.tiktok_read import TikTokReadClient
    from app.reception.models import ReceptionConversationState, ReceptionPolicy, ReceptionPolicyStore
    from app.tools import executor

    factory, settings, values = automation_db
    encryption_key = "synthetic-window-encryption-key-at-least-32-characters"
    settings = settings.model_copy(
        update={
            "tiktok_app_key": "synthetic-key",
            "tiktok_app_secret": SecretStr("synthetic-secret-value"),
            "tiktok_credential_encryption_key": SecretStr(encryption_key),
        }
    )
    policy_id = None
    async with factory() as setup:
        channel = await setup.scalar(select(ChannelAccount).where(ChannelAccount.store_id == values["store_id"]))
        channel.metadata_json = {"shop_cipher": "synthetic-shop"}
        channel.access_token_ref = encrypt_credential(
            "synthetic-token", encryption_key, f"tiktok:{channel.store_id}:{channel.external_store_id}:access"
        )
        customer = await setup.scalar(select(Customer).where(Customer.store_id == values["store_id"]))
        customer.external_customer_id = "800001"
        conversation = await setup.get(Conversation, values["conversation_id"])
        conversation.unread_count = 4
        if source_kind in {"welcome", "timeout"}:
            policy_id = uuid.uuid4()
            at = datetime.now(UTC) - timedelta(minutes=61)
            trigger = await setup.get(Message, values["trigger_message_id"])
            trigger.created_at = at
            setup.add(
                ReceptionPolicy(
                    id=policy_id,
                    kind=source_kind,
                    name="合成窗口契约验收",
                    content="Verified reply",
                    content_en="Verified reply",
                    delivery_mode="auto",
                    enabled=True,
                    revision=1,
                    timeout_minutes=60 if source_kind == "timeout" else None,
                    schedule={"mode": "long_term"},
                    authorized_by=values["authorized_by"],
                    created_by=values["authorized_by"],
                    updated_at=at - timedelta(minutes=1),
                )
            )
            await setup.flush()
            setup.add(ReceptionPolicyStore(policy_id=policy_id, store_id=values["store_id"]))
            setup.add(
                ReceptionConversationState(
                    conversation_id=values["conversation_id"],
                    store_id=values["store_id"],
                    segment_id=trigger.id,
                    last_activity_at=at,
                    unanswered_message_id=trigger.id,
                    unanswered_since=at,
                    timeout_policy_id=policy_id if source_kind == "timeout" else None,
                    timeout_policy_revision=1 if source_kind == "timeout" else None,
                )
            )
            values = {
                **values,
                "source_kind": source_kind,
                "agent_run_id": None,
                "authorization_json": {"policy_id": str(policy_id)},
            }
        await setup.commit()
    calls, captured = [], []

    def official(request):
        assert request.method == "GET"
        calls.append((request.url.path, request.url.params.get("page_token")))
        if request.url.path == "/customer_service/202601/conversations/123456789":
            data = {
                "conversation": {
                    "id": "123456789",
                    "create_time": 1,
                    "participants": [{"role": "BUYER", "im_user_id": "800001", "user_id": "900001"}],
                }
            }
        elif request.url.path == "/customer_service/202309/conversations":
            if request.url.params.get("page_token") != "second":
                data = {"conversations": [], "next_page_token": "second"}
            else:
                item = {
                    "id": "123456789",
                    "create_time": 1,
                    "participants": [{"role": "BUYER", "im_user_id": "800001"}],
                }
                if window is not None:
                    item["can_send_message"] = window
                data = {"conversations": [item]}
        else:
            pytest.fail(f"unexpected endpoint {request.url.path}")
        return httpx.Response(200, json={"code": 0, "message": "Success", "data": data})

    class Capture:
        real_writes = True

        async def send_message(self, channel, command):
            captured.append(command)
            return SendMessageResult(status="sent", mock=False, external_message_id="987654321")

    http = httpx.AsyncClient(transport=httpx.MockTransport(official))
    monkeypatch.setattr(
        remote_auth,
        "TikTokReadClient",
        lambda settings, channel: TikTokReadClient(settings, channel, client=http),
    )
    monkeypatch.setattr(executor, "get_message_adapter", lambda _: Capture())
    monkeypatch.setattr(executor, "get_settings", lambda: settings)
    try:
        if source_kind == "logistics_discovery":
            from decimal import Decimal

            from app.agents.tools.logistics_updates import discovery
            from app.orders.models import Order

            reader = AsyncMock(
                return_value=(
                    SimpleNamespace(
                        external_order_id="7654321",
                        status="shipped",
                        payment_status="paid",
                        currency="USD",
                        total_amount=Decimal("25.00"),
                        ordered_at=datetime.now(UTC),
                    ),
                )
            )
            monkeypatch.setattr(discovery, "read_verified_buyer_orders", reader)
            async with factory() as session:
                conversation = await session.get(Conversation, values["conversation_id"])
                actor = await session.get(User, values["authorized_by"])
                count = await discovery.synchronize_conversation_orders(session, actor, conversation, settings)
                assert count == (1 if window is True else 0)
                assert reader.await_count == count
                order = await session.scalar(select(Order).where(Order.store_id == values["store_id"]))
                assert (order is not None) is (window is True)
                assert captured == []
                await session.commit()
            return
        row_id = await enqueue(factory, values)
        async with factory() as session:
            row = await claim_delivery(session, settings)
            assert row.id == row_id
            await process_delivery(session, row, settings)
            await session.refresh(row)
            assert row.status == ("succeeded" if window is True else "cancelled")
            assert len(captured) == (1 if window is True else 0)
            conversation = await session.get(Conversation, values["conversation_id"], populate_existing=True)
            assert conversation.unread_count == 4
            assert ("/customer_service/202309/conversations", "second") in calls
            message = await session.scalar(select(Message).where(Message.idempotency_key == f"automation:{row_id}"))
            if window is True:
                assert captured[0].sender_role == ("ROBOT" if source_kind == "agent" else "SYSTEM")
                assert message.external_message_id == "987654321"
                assert message.raw_payload["automation_source_kind"] == source_kind
            else:
                assert message is None
    finally:
        await http.aclose()
        if policy_id:
            async with factory() as cleanup:
                await cleanup.execute(delete(ReceptionPolicy).where(ReceptionPolicy.id == policy_id))
                await cleanup.commit()


@pytest.mark.asyncio
async def test_concurrent_enqueue_and_claim_have_one_persisted_owner(automation_db):
    factory, settings, values = automation_db
    ids = await asyncio.gather(enqueue(factory, values), enqueue(factory, values))
    assert ids[0] == ids[1]

    async def claim():
        async with factory() as session:
            row = await claim_delivery(session, settings)
            return row.id if row else None

    claims = await asyncio.gather(claim(), claim())
    assert claims.count(ids[0]) == 1
    assert claims.count(None) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "change", [None, "permission", "pause", "human_reply", "policy", "window", "unknown", "master_off", "automatic_off"]
)
async def test_persisted_dispatch_rechecks_grant_and_captures_robot_without_human_confirmation(
    automation_db, monkeypatch, change
):
    from app.agents.tools.logistics_updates import authorization as remote_auth
    from app.tools import executor

    factory, settings, values = automation_db
    if change in {"master_off", "automatic_off"}:
        settings = settings.model_copy(
            update={"real_tiktok_automation_enabled" if change == "master_off" else "auto_reply_enabled": False}
        )
    row_id = await enqueue(factory, values)
    sent = []

    class Capture:
        real_writes = True

        async def send_message(self, channel, command):
            sent.append(command)
            return SendMessageResult(
                status="unknown" if change == "unknown" else "sent",
                mock=False,
                external_message_id=None if change == "unknown" else "987654321",
            )

    monkeypatch.setattr(executor, "get_message_adapter", lambda _: Capture())
    monkeypatch.setattr(executor, "get_settings", lambda: settings)
    remote = SimpleNamespace(
        id="123456789",
        participants=[SimpleNamespace(role="BUYER", im_user_id="synthetic-buyer", user_id="platform-buyer")],
        can_send_message=change != "window",
    )
    monkeypatch.setattr(
        remote_auth,
        "TikTokReadClient",
        lambda *_: SimpleNamespace(
            get_conversation=AsyncMock(return_value=remote), get_conversation_send_status=AsyncMock(return_value=remote)
        ),
    )
    async with factory() as session:
        row = await claim_delivery(session, settings)
        assert row is not None and row.id == row_id
        if change == "permission":
            await session.execute(delete(user_roles).where(user_roles.c.user_id == values["authorized_by"]))
        elif change in {"pause", "human_reply"}:
            conversation = await session.get(Conversation, values["conversation_id"])
            if change == "pause":
                conversation.metadata_json = {"automation_paused": True}
            else:
                conversation.last_human_replied_at = datetime.now(UTC)
        elif change == "policy":
            store = await session.get(Store, values["store_id"])
            store.metadata_json = {"agent_automation": {"mode": "off", "revision": 2}}
        await session.commit()
        await process_delivery(session, row, settings)
        await session.refresh(row)
        assert row.status == ("unknown" if change == "unknown" else "succeeded" if change is None else "cancelled")
        assert len(sent) == (1 if change in {None, "unknown"} else 0)
        if sent:
            assert sent[0].human_confirmed is False
            assert sent[0].automation_authorized is True
            assert sent[0].sender_role == "ROBOT"
            message = await session.scalar(select(Message).where(Message.idempotency_key == f"automation:{row_id}"))
            assert message.raw_payload["automation_source_kind"] == "agent"
        assert await claim_delivery(session, settings) is None


@pytest.mark.asyncio
async def test_only_pre_dispatch_expired_lease_recovers_and_parts_stay_ordered(automation_db):
    factory, settings, values = automation_db
    first_id = await enqueue(factory, values)
    second_id = await enqueue(factory, {**values, "content": "Second verified reply", "part_index": 1})
    async with factory() as session:
        first = await claim_delivery(session, settings)
        assert first.id == first_id
        first.claimed_until = datetime.now(UTC) - timedelta(seconds=1)
        await session.commit()
        await recover_expired_deliveries(session)
        assert first.status == "pending"
        await session.commit()
        first = await claim_delivery(session, settings)
        first.status = "dispatching"
        first.claimed_until = datetime.now(UTC) - timedelta(seconds=1)
        await session.commit()
        await recover_expired_deliveries(session)
        assert first.status == "unknown"
        await session.commit()
        assert await claim_delivery(session, settings) is None
        second = await session.get(AutomationDelivery, second_id)
        assert second.status == "cancelled"


@pytest.mark.asyncio
async def test_policy_revoked_during_preflight_never_reaches_platform(automation_db, monkeypatch):
    from app.agents.tools.logistics_updates import authorization as remote_auth
    from app.tools import executor

    factory, settings, values = automation_db
    await enqueue(factory, values)
    reached, release = asyncio.Event(), asyncio.Event()

    class ReadClient:
        async def get_conversation(self, _):
            reached.set()
            await release.wait()
            return SimpleNamespace(
                id="123456789",
                participants=[SimpleNamespace(role="BUYER", im_user_id="synthetic-buyer", user_id="platform-buyer")],
                can_send_message=True,
            )

        async def get_conversation_send_status(self, _):
            return SimpleNamespace(
                id="123456789",
                participants=[SimpleNamespace(role="BUYER", im_user_id="synthetic-buyer")],
                can_send_message=True,
            )

    monkeypatch.setattr(remote_auth, "TikTokReadClient", lambda *_: ReadClient())
    monkeypatch.setattr(executor, "get_message_adapter", lambda _: pytest.fail("revoked policy reached platform"))
    monkeypatch.setattr(executor, "get_settings", lambda: settings)
    async with factory() as session:
        row = await claim_delivery(session, settings)
        pending = asyncio.create_task(process_delivery(session, row, settings))
        await asyncio.wait_for(reached.wait(), 5)
        async with factory() as revoker:
            store = await revoker.scalar(select(Store).where(Store.id == values["store_id"]).with_for_update())
            store.metadata_json = {"agent_automation": {"mode": "off", "revision": 2}}
            await revoker.commit()
        release.set()
        await asyncio.wait_for(pending, 10)
        await session.refresh(row)
        assert row.status == "cancelled"
        assert row.error_code == "AUTOMATION_AUTHORIZATION_CHANGED"


@pytest.mark.asyncio
async def test_internal_knowledge_approval_cannot_authorize_customer_reply(automation_db):
    from app.agents.automation.authorization import current_customer_files
    from app.knowledge_base.document_models import KnowledgeFile, KnowledgeFileVersion

    factory, _, values = automation_db
    async with factory() as session:
        file = KnowledgeFile(
            store_id=values["store_id"],
            original_filename="synthetic.txt",
            filename_key=uuid.uuid4().hex,
            active_version_number=1,
        )
        session.add(file)
        await session.flush()
        version = KnowledgeFileVersion(
            store_id=values["store_id"],
            file_id=file.id,
            version_number=1,
            source_object_key="synthetic/unused",
            file_sha256="a" * 64,
            media_type="text/plain",
            config_json={},
            status="ready",
            created_by=values["authorized_by"],
            publication_approval="approved_for_internal_review",
            approved_by=values["authorized_by"],
            approved_at=datetime.now(UTC),
        )
        session.add(version)
        await session.flush()
        references = [[str(file.id), 1]]
        assert not await current_customer_files(session, values["store_id"], references)
        version.publication_approval = "approved_for_public_reply"
        await session.flush()
        assert await current_customer_files(session, values["store_id"], references)
        file.active_version_number = 2
        await session.flush()
        assert not await current_customer_files(session, values["store_id"], references)
        await session.commit()


@pytest.mark.asyncio
@pytest.mark.parametrize("revocation", ["actor", "role", "file"])
async def test_final_remote_preflight_reloads_revoked_local_proof(automation_db, monkeypatch, revocation):
    from app.agents.tools.logistics_updates import authorization as remote_auth
    from app.knowledge_base.document_models import KnowledgeFile, KnowledgeFileVersion
    from app.tools import executor

    factory, settings, values = automation_db
    file_id = version_id = None
    if revocation == "file":
        async with factory() as setup:
            file = KnowledgeFile(
                store_id=values["store_id"],
                original_filename="proof.txt",
                filename_key=uuid.uuid4().hex,
                active_version_number=1,
            )
            setup.add(file)
            await setup.flush()
            version = KnowledgeFileVersion(
                store_id=values["store_id"],
                file_id=file.id,
                version_number=1,
                source_object_key="synthetic/proof",
                file_sha256="b" * 64,
                media_type="text/plain",
                config_json={},
                status="ready",
                created_by=values["authorized_by"],
                publication_approval="approved_for_public_reply",
                approved_by=values["authorized_by"],
                approved_at=datetime.now(UTC),
            )
            setup.add(version)
            await setup.flush()
            file_id, version_id = file.id, version.id
            run = await setup.get(AgentRun, values["agent_run_id"])
            proof = dict(run.snapshot_ref["automation_eligibility"])
            proof["file_versions"] = [[str(file_id), 1]]
            run.snapshot_ref = {"automation_eligibility": proof}
            await setup.commit()
    await enqueue(factory, values)
    reached, release = asyncio.Event(), asyncio.Event()
    remote_calls = 0
    captured = []

    class Remote:
        async def get_conversation(self, _):
            nonlocal remote_calls
            remote_calls += 1
            if remote_calls == 2:
                reached.set()
                await release.wait()
            return SimpleNamespace(
                id="123456789",
                participants=[SimpleNamespace(role="BUYER", im_user_id="synthetic-buyer", user_id="platform-buyer")],
                can_send_message=True,
            )

        async def get_conversation_send_status(self, _):
            return SimpleNamespace(
                id="123456789",
                participants=[SimpleNamespace(role="BUYER", im_user_id="synthetic-buyer")],
                can_send_message=True,
            )

    class Capture:
        real_writes = True

        async def send_message(self, channel, command):
            captured.append(command)
            return SendMessageResult(status="sent", mock=False, external_message_id="987654321")

    monkeypatch.setattr(remote_auth, "TikTokReadClient", lambda *_: Remote())
    monkeypatch.setattr(executor, "get_message_adapter", lambda _: Capture())
    monkeypatch.setattr(executor, "get_settings", lambda: settings)
    async with factory() as sender:
        row = await claim_delivery(sender, settings)
        pending = asyncio.create_task(process_delivery(sender, row, settings))
        try:
            await asyncio.wait_for(reached.wait(), 5)
            async with factory() as revoker:
                if revocation == "actor":
                    actor = await revoker.get(User, values["authorized_by"])
                    actor.status = "disabled"
                elif revocation == "role":
                    await revoker.execute(delete(user_roles).where(user_roles.c.user_id == values["authorized_by"]))
                else:
                    version = await revoker.get(KnowledgeFileVersion, version_id, with_for_update=True)
                    version.publication_approval = "draft"
                    version.approved_by = version.approved_at = None
                await asyncio.wait_for(revoker.commit(), 5)
        finally:
            release.set()
            await asyncio.wait_for(pending, 10)
        assert captured == []
        await sender.refresh(row)
        assert row.status == "failed"
        assert row.error_code == "TOOL_AUTOMATION_NOT_AUTHORIZED"


async def two_agent_tasks(factory, values):
    from app.agents.management.config_models import AgentTask

    async with factory() as session:
        run = await session.get(AgentRun, values["agent_run_id"])
        trigger = await session.get(Message, values["trigger_message_id"])
        second_trigger = Message(
            id=uuid.uuid4(),
            store_id=trigger.store_id,
            conversation_id=trigger.conversation_id,
            customer_id=trigger.customer_id,
            platform="tiktok",
            external_message_id=uuid.uuid4().hex,
            content="Second question",
            role="user",
            direction="inbound",
            status="received",
            created_at=trigger.created_at + timedelta(seconds=1),
        )
        session.add(second_trigger)
        await session.flush()
        tasks = [
            AgentTask(
                id=uuid.uuid4(),
                store_id=values["store_id"],
                conversation_id=values["conversation_id"],
                trigger_message_id=message_id,
                agent_config_id=run.agent_config_id,
                mode="automation",
                trace_id=f"automation:1:{uuid.uuid4()}",
                status="pending",
                created_at=datetime.now(UTC) + timedelta(seconds=index),
            )
            for index, message_id in enumerate((trigger.id, second_trigger.id))
        ]
        session.add_all(tasks)
        await session.commit()
        return tasks


@pytest.mark.asyncio
async def test_two_workers_hold_a_before_fast_b_through_receipt_and_lease_recovery(automation_db):
    from app.chat.worker import claim_task

    factory, settings, values = automation_db
    tasks = await two_agent_tasks(factory, values)
    async with factory() as worker_a, factory() as worker_b:
        first = await claim_task(worker_a, settings)
        assert first.id == tasks[0].id
        assert await claim_task(worker_b, settings) is None
        # 原Worker无事务持有；租约到期后只能恢复A，不能运行B。
        first.updated_at = datetime.now(UTC) - timedelta(minutes=6)
        await worker_a.commit()
        recovered = await claim_task(worker_b, settings)
        assert recovered.id == first.id and recovered.attempt_count == 2
        assert await claim_task(worker_a, settings) is None
        await enqueue_delivery(worker_b, **values)
        recovered.status = "queued"
        await worker_b.commit()
        assert await claim_task(worker_a, settings) is None
        receipt = await claim_delivery(worker_b, settings)
        assert receipt.trigger_message_id == tasks[0].trigger_message_id
        assert await claim_task(worker_a, settings) is None
        receipt.status = "succeeded"
        await worker_b.commit()
        second = await claim_task(worker_a, settings)
        assert second.id == tasks[1].id
        await worker_a.rollback()


@pytest.mark.asyncio
async def test_delivery_groups_serialize_across_trigger_ids_and_unknown_blocks_next_source(automation_db):
    factory, settings, values = automation_db
    tasks = await two_agent_tasks(factory, values)
    await enqueue(factory, values)
    await enqueue(
        factory,
        {**values, "source_key": str(tasks[1].trigger_message_id), "trigger_message_id": tasks[1].trigger_message_id},
    )
    async with factory() as first_worker, factory() as second_worker:
        first = await claim_delivery(first_worker, settings)
        assert first.trigger_message_id == tasks[0].trigger_message_id
        assert await claim_delivery(second_worker, settings) is None
        first.claimed_until = datetime.now(UTC) - timedelta(seconds=1)
        await first_worker.commit()
        recovered = await claim_delivery(second_worker, settings)
        assert recovered.id == first.id
        recovered.status = "unknown"
        await second_worker.commit()
        assert await claim_delivery(first_worker, settings) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("recover", [False, True])
async def test_held_model_a_fences_old_attempt_and_fast_b_waits_for_receipts(automation_db, monkeypatch, recover):
    from app.agents.automation import runner
    from app.agents.core.schemas import AgentAction
    from app.agents.management.config_models import AgentTask
    from app.agents.tools.logistics_updates import authorization as remote_auth
    from app.chat.worker import claim_task
    from app.tools import executor

    factory, settings, values = automation_db
    tasks = await two_agent_tasks(factory, values)
    reached, release = asyncio.Event(), asyncio.Event()
    calls, sent = [], []

    class Capture:
        real_writes = True

        async def send_message(self, channel, command):
            sent.append(command.content)
            return SendMessageResult(status="sent", mock=False, external_message_id=str(900000000 + len(sent)))

    remote = SimpleNamespace(
        id="123456789",
        participants=[SimpleNamespace(role="BUYER", im_user_id="synthetic-buyer", user_id="platform-buyer")],
        can_send_message=True,
    )
    monkeypatch.setattr(
        remote_auth,
        "TikTokReadClient",
        lambda *_: SimpleNamespace(
            get_conversation=AsyncMock(return_value=remote), get_conversation_send_status=AsyncMock(return_value=remote)
        ),
    )
    monkeypatch.setattr(executor, "get_message_adapter", lambda _: Capture())
    monkeypatch.setattr(executor, "get_settings", lambda: settings)

    async def model(session, config, conversation, trigger, *args, **kwargs):
        assert not session.in_transaction(), "模型等待期间不能持有数据库事务"
        calls.append(trigger.id)
        if len(calls) == 1:
            reached.set()
            await release.wait()
        run_id = values["agent_run_id"]
        content = "Verified reply"
        if trigger.id == tasks[1].trigger_message_id:
            original = await session.get(AgentRun, run_id)
            proof = dict(original.snapshot_ref["automation_eligibility"])
            content = "B fast reply"
            proof["content_hashes"] = [content_hash(content)]
            run_id = uuid.uuid4()
            session.add(
                AgentRun(
                    id=run_id,
                    store_id=original.store_id,
                    conversation_id=original.conversation_id,
                    agent_config_id=original.agent_config_id,
                    trigger_message_id=trigger.id,
                    model_provider="deepseek",
                    model_name="deepseek-chat",
                    status="succeeded",
                    action="human_review",
                    snapshot_ref={"automation_eligibility": proof},
                )
            )
            await session.commit()
        return SimpleNamespace(
            agent_run_id=run_id,
            action=AgentAction.HUMAN_REVIEW,
            draft_reply=content,
            reply_parts=[content],
            logistics_order_numbers=[],
            reply_language="en",
        )

    monkeypatch.setattr(runner, "run_agent_for_message", model)
    async with factory() as a, factory() as b:
        claimed = await claim_task(a, settings)
        pending = asyncio.create_task(runner.process_agent_task(a, claimed, settings))
        try:
            await asyncio.wait_for(reached.wait(), 5)
            assert await claim_task(b, settings) is None
            if recover:
                old = await b.get(AgentTask, tasks[0].id, with_for_update=True)
                old.updated_at = datetime.now(UTC) - timedelta(minutes=6)
                await b.commit()
                recovered = await claim_task(b, settings)
                assert recovered.id == tasks[0].id and recovered.attempt_count == 2
                await runner.process_agent_task(b, recovered, settings)
            release.set()
            await asyncio.wait_for(pending, 5)
            assert calls == [tasks[0].trigger_message_id] * (2 if recover else 1)
            assert await claim_task(b, settings) is None
            rows = (
                await b.scalars(select(AutomationDelivery).where(AutomationDelivery.store_id == values["store_id"]))
            ).all()
            assert len(rows) == 1 and rows[0].trigger_message_id == tasks[0].trigger_message_id
            receipt = await claim_delivery(b, settings)
            await process_delivery(b, receipt, settings)
            assert sent == ["Verified reply"]
            next_task = await claim_task(b, settings)
            assert next_task.id == tasks[1].id
            await runner.process_agent_task(b, next_task, settings)
            receipt = await claim_delivery(b, settings)
            await process_delivery(b, receipt, settings)
            assert sent == ["Verified reply", "B fast reply"]
        finally:
            release.set()
            await asyncio.wait_for(pending, 5)


@pytest.mark.asyncio
async def test_cross_source_fifo_keeps_a_text_card_before_b_even_if_card_enqueued_later(automation_db):
    factory, settings, values = automation_db
    tasks = await two_agent_tasks(factory, values)
    # 隔离验证投递序列；A/B模型已经完成，不让任务生成态干扰队列顺序。
    async with factory() as setup:
        from app.agents.management.config_models import AgentTask

        for task in tasks:
            row = await setup.get(AgentTask, task.id)
            row.status = "human_review"
        await setup.commit()
    a_text = await enqueue(factory, values)
    b_text = await enqueue(
        factory,
        {**values, "source_key": str(tasks[1].trigger_message_id), "trigger_message_id": tasks[1].trigger_message_id},
    )
    a_card = await enqueue(
        factory,
        {
            **values,
            "part_index": 1,
            "message_type": "logistics_card",
            "card_order_id": "123",
            "content": "Logistics update",
        },
    )
    async with factory() as a, factory() as b:
        first = await claim_delivery(a, settings)
        assert first.id == a_text
        assert await claim_delivery(b, settings) is None
        first.status = "succeeded"
        await a.commit()
        second = await claim_delivery(b, settings)
        assert second.id == a_card
        assert await claim_delivery(a, settings) is None
        second.status = "succeeded"
        await b.commit()
        third = await claim_delivery(a, settings)
        assert third.id == b_text


@pytest.mark.asyncio
@pytest.mark.parametrize("revocation", ["actor", "role"])
async def test_final_local_grant_locks_serialize_revoke_with_adapter_receipt(automation_db, monkeypatch, revocation):
    from app.agents.tools.logistics_updates import authorization as remote_auth
    from app.tools import executor

    factory, settings, values = automation_db
    await enqueue(factory, values)
    reached, release = asyncio.Event(), asyncio.Event()

    class Capture:
        real_writes = True

        async def send_message(self, channel, command):
            reached.set()
            await release.wait()
            return SendMessageResult(status="sent", mock=False, external_message_id="987654321")

    remote = SimpleNamespace(
        id="123456789",
        participants=[SimpleNamespace(role="BUYER", im_user_id="synthetic-buyer", user_id="platform-buyer")],
        can_send_message=True,
    )
    monkeypatch.setattr(
        remote_auth,
        "TikTokReadClient",
        lambda *_: SimpleNamespace(
            get_conversation=AsyncMock(return_value=remote), get_conversation_send_status=AsyncMock(return_value=remote)
        ),
    )
    monkeypatch.setattr(executor, "get_message_adapter", lambda _: Capture())
    monkeypatch.setattr(executor, "get_settings", lambda: settings)

    async def revoke():
        async with factory() as revoker:
            if revocation == "actor":
                actor = await revoker.get(User, values["authorized_by"], with_for_update=True)
                actor.status = "disabled"
            else:
                await revoker.execute(delete(user_roles).where(user_roles.c.user_id == values["authorized_by"]))
            await revoker.commit()

    async with factory() as sender:
        row = await claim_delivery(sender, settings)
        sending = asyncio.create_task(process_delivery(sender, row, settings))
        changing = None
        try:
            await asyncio.wait_for(reached.wait(), 5)
            changing = asyncio.create_task(revoke())
            with pytest.raises(TimeoutError):
                await asyncio.wait_for(asyncio.shield(changing), 0.15)
            assert not changing.done()
        finally:
            release.set()
            await asyncio.wait_for(sending, 5)
            if changing is not None:
                await asyncio.wait_for(changing, 5)
        await sender.refresh(row)
        assert row.status == "succeeded"


@pytest.mark.asyncio
@pytest.mark.parametrize("replacement_status", ["processing", "queued"])
async def test_process_one_old_error_preserves_recovered_owner_and_fifo(automation_db, monkeypatch, replacement_status):
    from app.agents.automation import runner
    from app.agents.core.schemas import AgentAction
    from app.agents.management.config_models import AgentTask
    from app.chat import worker

    factory, settings, values = automation_db
    tasks = await two_agent_tasks(factory, values)
    reached, release = asyncio.Event(), asyncio.Event()

    async def stale_process(session, task, current_settings):
        reached.set()
        await release.wait()
        raise ValueError("expired-attempt")

    monkeypatch.setattr(worker, "session_factory", factory)
    monkeypatch.setattr(runner, "process_one_delivery", AsyncMock(return_value=False))
    monkeypatch.setattr(worker, "process_task", stale_process)
    old_worker = asyncio.create_task(worker.process_one(settings))
    async with factory() as current:
        try:
            await asyncio.wait_for(reached.wait(), 5)
            for attempt in (2, 3):
                row = await current.get(AgentTask, tasks[0].id, with_for_update=True, populate_existing=True)
                row.updated_at = datetime.now(UTC) - timedelta(minutes=6)
                await current.commit()
                row = await worker.claim_task(current, settings)
                assert row.id == tasks[0].id and row.attempt_count == attempt
            row.status = replacement_status
            row.agent_run_id = values["agent_run_id"]
            if replacement_status == "queued":
                await enqueue_delivery(current, **values)
            await current.commit()
            release.set()
            assert await asyncio.wait_for(old_worker, 5) is True
            await current.refresh(row)
            assert row.status == replacement_status
            assert row.attempt_count == 3
            assert row.error_code is None and row.next_attempt_at is None and row.processed_at is None
            assert await worker.claim_task(current, settings) is None
            if replacement_status == "processing":
                monkeypatch.setattr(
                    runner,
                    "run_agent_for_message",
                    AsyncMock(
                        return_value=SimpleNamespace(
                            agent_run_id=values["agent_run_id"],
                            action=AgentAction.HUMAN_REVIEW,
                            draft_reply="Verified reply",
                            reply_parts=["Verified reply"],
                            logistics_order_numbers=[],
                            reply_language="en",
                        )
                    ),
                )
                await runner.process_agent_task(current, row, settings)
                await current.refresh(row)
                assert row.status == "queued"
            receipts = (
                await current.scalars(
                    select(AutomationDelivery).where(AutomationDelivery.store_id == values["store_id"])
                )
            ).all()
            assert len(receipts) == 1 and receipts[0].status == "pending"
            assert receipts[0].trigger_message_id == tasks[0].trigger_message_id
            assert await worker.claim_task(current, settings) is None
        finally:
            release.set()
            await asyncio.wait_for(old_worker, 5)


@pytest.mark.asyncio
@pytest.mark.parametrize("reception_kind", ["welcome", "timeout"])
async def test_completed_agent_reply_does_not_wait_for_its_reception_timer(automation_db, reception_kind):
    from app.chat.worker import claim_task

    factory, settings, values = automation_db
    tasks = await two_agent_tasks(factory, values)
    async with factory() as session:
        first = await session.get(AgentTask, tasks[0].id)
        first.status = "queued"
        own = await enqueue_delivery(session, **values)
        own.status = "succeeded"
        timer = await enqueue_delivery(
            session,
            **{
                **values,
                "source_kind": reception_kind,
                "agent_run_id": None,
                "not_before": datetime.now(UTC) + timedelta(hours=1),
            },
        )
        assert timer.status == "pending"
        await session.commit()
        claimed = await claim_task(session, settings)
        assert claimed is not None and claimed.id == tasks[1].id


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["order_card", "product_card", "image", "video"])
async def test_nontext_platform_placeholder_never_enqueues_an_automatic_question(automation_db, kind):
    from app.agents.automation.service import on_agent_inbound

    factory, settings, values = automation_db
    async with factory() as session:
        conversation = await session.get(Conversation, values["conversation_id"])
        trigger = await session.get(Message, values["trigger_message_id"])
        trigger.message_type = kind
        trigger.content = "订单卡片"
        await session.flush()
        assert await on_agent_inbound(session, conversation, trigger, settings)
        assert await session.scalar(select(AgentTask).where(AgentTask.trigger_message_id == trigger.id)) is None
        trigger.message_type = "text"
        trigger.content = "Please cancel the order I shared."
        await session.flush()
        assert await on_agent_inbound(session, conversation, trigger, settings)
        assert await session.scalar(select(AgentTask).where(AgentTask.trigger_message_id == trigger.id)) is not None
