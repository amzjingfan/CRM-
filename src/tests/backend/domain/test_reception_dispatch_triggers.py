"""Webhook 新买家消息派单，重复消息不得再次触发。"""

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.automation import service as automation_service
from app.conversations.models import Message
from app.integrations import service as webhook_service
from app.reception import automation as reception_automation


@pytest.mark.asyncio
async def test_webhook_dispatches_new_buyer_message_once(monkeypatch: pytest.MonkeyPatch) -> None:
    store_id, conversation_id, customer_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    now = datetime.now(UTC)
    customer = SimpleNamespace(id=customer_id)
    conversation = SimpleNamespace(
        id=conversation_id,
        store_id=store_id,
        status="active",
        closed_at=None,
        unread_count=0,
        last_human_replied_at=None,
        awaiting_reply_since=None,
        last_message_at=None,
        last_message_id=None,
    )
    normalized = SimpleNamespace(
        customer=SimpleNamespace(),
        external_conversation_id="conv-1",
        external_message_id="message-1",
        created_at=now,
        content="synthetic buyer message",
        message_type="product_card",
        display_data={"card": {"kind": "product_card", "product_id": "123"}},
        language="en",
    )
    session = Mock(spec=AsyncSession)
    session.scalar = AsyncMock(side_effect=[conversation, None, None])
    session.flush = AsyncMock()
    dispatch = AsyncMock(return_value=None)
    agent_inbound = AsyncMock(return_value=True)
    reception_inbound = AsyncMock()
    monkeypatch.setattr(automation_service, "on_agent_inbound", agent_inbound)
    monkeypatch.setattr(reception_automation, "on_reception_inbound", reception_inbound)
    monkeypatch.setattr(webhook_service, "_upsert_customer", AsyncMock(return_value=customer))
    monkeypatch.setattr(webhook_service, "dispatch_conversation", dispatch)
    monkeypatch.setattr(webhook_service, "get_settings", lambda: SimpleNamespace(auto_reply_enabled=False))
    channel = SimpleNamespace(store_id=store_id)
    event = SimpleNamespace(platform="tiktok")

    await webhook_service._process_message(session, event, channel, normalized)
    dispatch.assert_awaited_once()
    assert dispatch.await_args.args == (session, conversation_id)
    assert conversation.awaiting_reply_since == now
    assert conversation.unread_count == 1
    stored = next(call.args[0] for call in session.add.call_args_list if isinstance(call.args[0], Message))
    assert stored.message_type == "product_card"
    assert stored.raw_payload == normalized.display_data
    agent_inbound.assert_awaited_once()
    reception_inbound.assert_awaited_once()
    assert agent_inbound.await_args.args[1:3] == (conversation, stored)
    assert reception_inbound.await_args.args[1:3] == (conversation, stored)

    session.scalar = AsyncMock(side_effect=[conversation, SimpleNamespace(id=uuid.uuid4())])
    await webhook_service._process_message(session, event, channel, normalized)
    assert dispatch.await_count == 1
    assert conversation.unread_count == 1
    assert agent_inbound.await_count == 1
    assert reception_inbound.await_count == 1
