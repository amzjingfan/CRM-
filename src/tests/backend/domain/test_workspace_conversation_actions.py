"""会话操作只改变授权店铺的 CRM 状态，且保留人工发送边界。"""

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.conversations.workflow import reopen_on_new_buyer_message
from app.integrations import conversation_sync
from app.integrations.conversation_sync import _persist_page
from app.integrations.tiktok_read import TikTokConversationMessage, TikTokMessageSender
from app.shared.exceptions.errors import AppError, ErrorCode
from app.workspace import service as workspace_service


@pytest.fixture(autouse=True)
def synthetic_access_and_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    """本文件验证原有状态流转；归属安全由独立 PostgreSQL 用例验证。"""
    monkeypatch.setattr(workspace_service, "ensure_conversation_access", AsyncMock(return_value=None))
    monkeypatch.setattr(conversation_sync, "dispatch_conversation", AsyncMock(return_value=None))


@pytest.mark.asyncio
async def test_buyer_stage_override_is_scoped_audited_and_can_return_to_auto(monkeypatch: pytest.MonkeyPatch) -> None:
    session = Mock(spec=AsyncSession)
    session.scalar = AsyncMock()
    session.commit = AsyncMock()
    actor = SimpleNamespace(id=uuid.uuid4())
    store_id, conversation_id, customer_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    conversation = SimpleNamespace(id=conversation_id, store_id=store_id, customer_id=customer_id)
    customer = SimpleNamespace(
        id=customer_id,
        store_id=store_id,
        name="buyer",
        email=None,
        avatar=None,
        tags=[],
        metadata_json={"source": "tiktok"},
    )
    session.scalar.return_value = customer
    monkeypatch.setattr(workspace_service, "allowed_store_ids", AsyncMock(return_value={store_id}))
    lookup = AsyncMock(return_value=conversation)
    monkeypatch.setattr(workspace_service, "find_conversation", lookup)

    saved = await workspace_service.set_buyer_stage_override(session, actor, conversation_id, "after")
    assert saved.buyer_stage_override == "after"
    assert customer.metadata_json == {"source": "tiktok", "buyer_stage_override": "after"}
    assert lookup.await_args.args[2] == {store_id}
    audit = session.add.call_args.args[0]
    assert audit.action == "customer.buyer_stage_override"
    assert audit.store_id == store_id
    assert audit.after_data == {"stage": "after"}

    await workspace_service.set_buyer_stage_override(session, actor, conversation_id, "after")
    assert session.commit.await_count == 1
    restored = await workspace_service.set_buyer_stage_override(session, actor, conversation_id, None)
    assert restored.buyer_stage_override is None
    assert customer.metadata_json == {"source": "tiktok"}

    lookup.return_value = None
    with pytest.raises(AppError) as denied:
        await workspace_service.set_buyer_stage_override(session, actor, conversation_id, "pre")
    assert denied.value.code == ErrorCode.RESOURCE_NOT_FOUND


@pytest.mark.asyncio
async def test_star_change_is_scoped_audited_and_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    session = Mock(spec=AsyncSession)
    session.commit = AsyncMock()
    actor = SimpleNamespace(id=uuid.uuid4())
    store_id, conversation_id = uuid.uuid4(), uuid.uuid4()
    conversation = SimpleNamespace(
        id=conversation_id, store_id=store_id, status="active", is_starred=False, closed_at=None
    )
    monkeypatch.setattr(workspace_service, "allowed_store_ids", AsyncMock(return_value={store_id}))
    lookup = AsyncMock(return_value=conversation)
    monkeypatch.setattr(workspace_service, "find_conversation", lookup)

    result = await workspace_service.set_conversation_star(session, actor, conversation_id, True)
    assert result.is_starred is True
    assert conversation.is_starred is True
    assert lookup.await_args.args[2] == {store_id}
    audit = session.add.call_args.args[0]
    assert audit.action == "conversation.star"
    assert audit.store_id == store_id
    assert audit.actor_id == actor.id
    assert audit.after_data == {"is_starred": True}

    await workspace_service.set_conversation_star(session, actor, conversation_id, True)
    assert session.add.call_count == 1

    lookup.return_value = None
    with pytest.raises(AppError) as denied:
        await workspace_service.set_conversation_star(session, actor, conversation_id, False)
    assert denied.value.code == ErrorCode.RESOURCE_NOT_FOUND


@pytest.mark.asyncio
async def test_close_and_reopen_are_scoped_and_only_audit_transitions(monkeypatch: pytest.MonkeyPatch) -> None:
    session = Mock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.scalar = AsyncMock(return_value=None)
    actor = SimpleNamespace(id=uuid.uuid4())
    store_id, conversation_id = uuid.uuid4(), uuid.uuid4()
    conversation = SimpleNamespace(
        id=conversation_id, store_id=store_id, status="active", is_starred=True, closed_at=None
    )
    monkeypatch.setattr(workspace_service, "allowed_store_ids", AsyncMock(return_value={store_id}))
    monkeypatch.setattr(workspace_service, "find_conversation", AsyncMock(return_value=conversation))

    closed = await workspace_service.set_conversation_closed(session, actor, conversation_id, True)
    assert closed.status == "closed"
    assert conversation.closed_at is not None
    assert conversation.is_starred is True
    assert session.add.call_args.args[0].action == "conversation.close"
    await workspace_service.set_conversation_closed(session, actor, conversation_id, True)
    assert session.add.call_count == 1

    reopened = await workspace_service.set_conversation_closed(session, actor, conversation_id, False)
    assert reopened.status == "active"
    assert conversation.closed_at is None
    assert session.add.call_count == 2
    assert session.add.call_args.args[0].action == "conversation.reopen"


@pytest.mark.asyncio
async def test_close_refuses_unresolved_outbound_message(monkeypatch: pytest.MonkeyPatch) -> None:
    session = Mock(spec=AsyncSession)
    session.scalar = AsyncMock(return_value=uuid.uuid4())
    actor = SimpleNamespace(id=uuid.uuid4())
    conversation = SimpleNamespace(
        id=uuid.uuid4(), store_id=uuid.uuid4(), status="active", is_starred=False, closed_at=None
    )
    monkeypatch.setattr(workspace_service, "allowed_store_ids", AsyncMock(return_value={conversation.store_id}))
    monkeypatch.setattr(workspace_service, "find_conversation", AsyncMock(return_value=conversation))

    with pytest.raises(AppError) as blocked:
        await workspace_service.set_conversation_closed(session, actor, conversation.id, True)
    assert blocked.value.code == ErrorCode.RESOURCE_CONFLICT
    assert conversation.status == "active"
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_transfer_refuses_target_without_same_store_reply_access_before_tool_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = Mock(spec=AsyncSession)
    actor = SimpleNamespace(id=uuid.uuid4())
    conversation = SimpleNamespace(id=uuid.uuid4(), store_id=uuid.uuid4(), status="active")
    monkeypatch.setattr(workspace_service, "allowed_store_ids", AsyncMock(return_value={conversation.store_id}))
    monkeypatch.setattr(workspace_service, "find_conversation", AsyncMock(return_value=conversation))
    monkeypatch.setattr(workspace_service, "_assignee_can_reply", AsyncMock(return_value=False))
    begin = AsyncMock()
    monkeypatch.setattr(workspace_service, "begin_tool_call", begin)

    with pytest.raises(AppError) as denied:
        await workspace_service.transfer_session(session, actor, conversation.id, "handoff", uuid.uuid4(), "key")
    assert denied.value.code == ErrorCode.VALIDATION_ERROR
    begin.assert_not_awaited()


@pytest.mark.asyncio
async def test_transfer_does_not_override_a_concurrent_close(monkeypatch: pytest.MonkeyPatch) -> None:
    session = Mock(spec=AsyncSession)
    actor = SimpleNamespace(id=uuid.uuid4())
    conversation = SimpleNamespace(id=uuid.uuid4(), store_id=uuid.uuid4(), status="active")
    monkeypatch.setattr(workspace_service, "allowed_store_ids", AsyncMock(return_value={conversation.store_id}))
    monkeypatch.setattr(workspace_service, "find_conversation", AsyncMock(return_value=conversation))
    tool_call = SimpleNamespace()

    async def begin(*_args: object) -> tuple[SimpleNamespace, bool, float]:
        conversation.status = "closed"
        return tool_call, False, 0.0

    monkeypatch.setattr(workspace_service, "begin_tool_call", begin)
    finish = AsyncMock()
    monkeypatch.setattr(workspace_service, "finish_tool_call", finish)
    session.refresh = AsyncMock()

    with pytest.raises(AppError) as denied:
        await workspace_service.transfer_session(session, actor, conversation.id, "handoff", None, "key")
    assert denied.value.code == ErrorCode.RESOURCE_CONFLICT
    assert conversation.status == "closed"
    finish.assert_awaited_once_with(session, tool_call, 0.0, "failed", None, False, "CONVERSATION_CLOSED")


def test_only_new_buyer_message_reopens_locally_closed_conversation() -> None:
    closed_at = datetime.now(UTC)
    conversation = SimpleNamespace(status="closed", closed_at=closed_at)
    assert reopen_on_new_buyer_message(conversation, closed_at - timedelta(seconds=1)) is False
    assert conversation.status == "closed"
    assert reopen_on_new_buyer_message(conversation, closed_at + timedelta(seconds=1)) is True
    assert conversation.status == "active"
    assert conversation.closed_at is None


@pytest.mark.asyncio
async def test_sync_reopens_once_and_counts_each_new_buyer_message_across_pages() -> None:
    session = Mock(spec=AsyncSession)
    session.scalar = AsyncMock(return_value=None)
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.commit = AsyncMock()
    closed_at = datetime.now(UTC) - timedelta(minutes=2)
    conversation = SimpleNamespace(
        id=uuid.uuid4(),
        store_id=uuid.uuid4(),
        status="closed",
        closed_at=closed_at,
        unread_count=0,
        last_message_at=None,
        last_message_id=None,
        last_human_replied_at=None,
        awaiting_reply_since=None,
    )
    channel = SimpleNamespace(store_id=conversation.store_id, last_sync_at=None)
    customer = SimpleNamespace(id=uuid.uuid4())
    sender = TikTokMessageSender(im_user_id="123", role="BUYER")
    first = TikTokConversationMessage(
        id="101",
        content='{"content":"first"}',
        create_time=int((closed_at + timedelta(seconds=10)).timestamp()),
        sender=sender,
        type="TEXT",
    )
    second = TikTokConversationMessage(
        id="102",
        content='{"content":"second"}',
        create_time=int((closed_at + timedelta(seconds=20)).timestamp()),
        sender=sender,
        type="TEXT",
    )

    first_count, cutoff = await _persist_page(session, channel, conversation, customer, "123", [first], None)
    second_count, cutoff = await _persist_page(session, channel, conversation, customer, "123", [second], cutoff)

    assert (first_count, second_count) == (1, 1)
    assert cutoff == closed_at
    assert conversation.status == "active"
    assert conversation.unread_count == 2
    assert [
        item.action for call in session.add.call_args_list if (item := call.args[0]).__class__.__name__ == "AuditLog"
    ] == ["conversation.reopen.inbound"]


@pytest.mark.asyncio
async def test_sync_counts_new_buyer_messages_but_not_historical_backfill() -> None:
    session = Mock(spec=AsyncSession)
    session.scalar = AsyncMock(return_value=None)
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.commit = AsyncMock()
    last_sync_at = datetime.now(UTC) - timedelta(minutes=1)
    conversation = SimpleNamespace(
        id=uuid.uuid4(),
        store_id=uuid.uuid4(),
        status="active",
        closed_at=None,
        unread_count=0,
        last_message_at=None,
        last_message_id=None,
        last_human_replied_at=None,
        awaiting_reply_since=None,
    )
    channel = SimpleNamespace(store_id=conversation.store_id, last_sync_at=last_sync_at)
    customer = SimpleNamespace(id=uuid.uuid4())
    sender = TikTokMessageSender(im_user_id="123", role="BUYER")
    old = TikTokConversationMessage(
        id="201",
        content='{"content":"old"}',
        create_time=int((last_sync_at - timedelta(seconds=30)).timestamp()),
        sender=sender,
        type="TEXT",
    )
    new = TikTokConversationMessage(
        id="202",
        content='{"content":"new"}',
        create_time=int((last_sync_at + timedelta(seconds=30)).timestamp()),
        sender=sender,
        type="TEXT",
    )

    inserted, cutoff = await _persist_page(session, channel, conversation, customer, "123", [old, new], None)
    assert inserted == 2
    assert cutoff is None
    assert conversation.unread_count == 1
    assert conversation.status == "active"
    conversation_sync.dispatch_conversation.assert_awaited_once_with(session, conversation.id, now=ANY)
    new_message = next(
        call.args[0]
        for call in session.add.call_args_list
        if getattr(call.args[0], "external_message_id", None) == "202"
    )
    session.scalar = AsyncMock(return_value=new_message)
    duplicate_count, _ = await _persist_page(session, channel, conversation, customer, "123", [new], None)
    assert duplicate_count == 0
    assert conversation_sync.dispatch_conversation.await_count == 1


def test_closed_conversation_never_exposes_send_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        workspace_service,
        "get_settings",
        lambda: SimpleNamespace(real_tiktok_message_write_enabled=False, allow_mock_platform_adapters=True),
    )
    conversation = SimpleNamespace(status="closed", platform="tiktok")
    assert workspace_service._message_send_mode(conversation) == "disabled"
