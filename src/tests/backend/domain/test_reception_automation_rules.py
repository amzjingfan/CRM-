"""欢迎新段、最早未答与站点时间的确定性行为。"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from app.conversations.models import Conversation, Message
from app.reception import automation
from app.reception.automation import advance_inbound, on_reception_outbound, policy_active, reception_content
from app.reception.models import ReceptionConversationState, ReceptionPolicy
from app.reception.schemas import PolicyCreate

NOW = datetime(2026, 11, 2, 12, tzinfo=UTC)


def inbound(at: datetime = NOW, language: str = "en") -> Message:
    return Message(
        id=uuid.uuid4(),
        direction="inbound",
        role="user",
        status="received",
        created_at=at,
        content="Hello" if language == "en" else "你好",
        language=language,
    )


def test_policy_defaults_preview_and_accepts_explicit_auto() -> None:
    base = dict(kind="welcome", name="Welcome", content="您好", store_ids=[uuid.uuid4()])
    policy = PolicyCreate(**base)
    assert policy.delivery_mode == "preview"
    assert policy.welcome_idle_hours == 24
    assert PolicyCreate(**base, delivery_mode="auto").delivery_mode == "auto"


def test_new_segment_after_24h_and_repeated_inbound_keeps_earliest_timer() -> None:
    state = ReceptionConversationState(store_id=uuid.uuid4(), conversation_id=uuid.uuid4())
    first = inbound()
    assert advance_inbound(state, first, idle_hours=24)
    assert state.segment_id == first.id
    assert state.unanswered_since == NOW
    second = inbound(NOW + timedelta(minutes=59))
    assert not advance_inbound(state, second, idle_hours=24)
    assert state.unanswered_message_id == first.id
    assert state.unanswered_since == NOW
    assert advance_inbound(state, inbound(second.created_at + timedelta(hours=24)), idle_hours=24)


def test_duplicate_or_out_of_order_inbound_does_not_rewind_segment() -> None:
    state = ReceptionConversationState(store_id=uuid.uuid4(), conversation_id=uuid.uuid4())
    first = inbound()
    assert advance_inbound(state, first, idle_hours=24)
    assert not advance_inbound(state, first, idle_hours=24)
    delayed = inbound(NOW - timedelta(minutes=50))
    assert not advance_inbound(state, delayed, idle_hours=24)
    assert state.segment_id == first.id
    assert state.last_activity_at == NOW
    assert state.unanswered_since == delayed.created_at
    assert state.unanswered_message_id == delayed.id
    assert not advance_inbound(state, first, idle_hours=24)
    assert not advance_inbound(state, delayed, idle_hours=24)
    assert state.unanswered_since == delayed.created_at


def test_delayed_message_does_not_revive_answered_cycle() -> None:
    state = ReceptionConversationState(
        store_id=uuid.uuid4(),
        conversation_id=uuid.uuid4(),
        segment_id=uuid.uuid4(),
        last_activity_at=NOW,
    )
    assert not advance_inbound(state, inbound(NOW - timedelta(minutes=50)), idle_hours=24)
    assert state.unanswered_since is None
    assert state.last_activity_at == NOW


def test_policy_activity_uses_store_timezone_and_closed_end_boundary() -> None:
    policy = ReceptionPolicy(
        enabled=True,
        delivery_mode="auto",
        schedule={
            "mode": "fixed_hours",
            "start_date": "2026-11-02",
            "end_date": "2026-11-02",
            "daily_start_time": "09:00",
            "daily_end_time": "18:00",
        },
    )
    assert policy_active(policy, "Asia/Shanghai", NOW - timedelta(hours=3))
    assert not policy_active(policy, "Asia/Shanghai", NOW)
    assert not policy_active(policy, "invalid/timezone", NOW)
    policy.enabled = False
    assert not policy_active(policy, "Asia/Shanghai", NOW - timedelta(hours=3))


def test_buyer_language_uses_exact_approved_copy() -> None:
    welcome = ReceptionPolicy(kind="welcome", content="您好，欢迎咨询！请问有什么可以帮您？")
    timeout = ReceptionPolicy(kind="timeout", content="我们已收到您的消息，客服正在处理中。感谢您的耐心等待。")
    assert reception_content(welcome, inbound()) == "Hi! Welcome to our store. How can we help you today?"
    assert (
        reception_content(timeout, inbound())
        == "We've received your message. Our support team is working on your question. Thank you for your patience."
    )
    assert reception_content(welcome, inbound(language="zh-CN")) == welcome.content
    welcome.content = "自定义中文"
    assert reception_content(welcome, inbound()) is None
    welcome.content_en = "Custom approved English"
    assert reception_content(welcome, inbound()) == "Custom approved English"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status,source,cleared",
    [
        ("pending", None, False),
        ("unknown", None, False),
        ("failed", None, False),
        ("sent", "welcome", False),
        ("sent", "agent", True),
        ("delivered", None, True),
    ],
)
async def test_only_successful_non_welcome_clears_timer(monkeypatch, status, source, cleared) -> None:
    conversation = Conversation(id=uuid.uuid4(), store_id=uuid.uuid4())
    state = ReceptionConversationState(
        conversation_id=conversation.id,
        store_id=conversation.store_id,
        unanswered_message_id=uuid.uuid4(),
        unanswered_since=NOW,
        last_activity_at=NOW,
    )
    monkeypatch.setattr(automation, "_locked_conversation", AsyncMock(return_value=conversation))
    session = AsyncMock()
    session.get.return_value = state
    message = Message(
        store_id=conversation.store_id,
        conversation_id=conversation.id,
        direction="outbound",
        status=status,
        sent_at=NOW + timedelta(minutes=1),
    )
    await on_reception_outbound(session, conversation, message, source_kind=source)
    assert (state.unanswered_since is None) is cleared


@pytest.mark.asyncio
async def test_late_outbound_receipt_does_not_cancel_newer_inbound(monkeypatch) -> None:
    conversation = Conversation(id=uuid.uuid4(), store_id=uuid.uuid4())
    state = ReceptionConversationState(
        conversation_id=conversation.id,
        store_id=conversation.store_id,
        unanswered_message_id=uuid.uuid4(),
        unanswered_since=NOW,
        last_activity_at=NOW,
    )
    monkeypatch.setattr(automation, "_locked_conversation", AsyncMock(return_value=conversation))
    session = AsyncMock()
    session.get.return_value = state
    message = Message(
        store_id=conversation.store_id,
        conversation_id=conversation.id,
        direction="outbound",
        status="sent",
        sent_at=NOW - timedelta(minutes=1),
    )
    await on_reception_outbound(session, conversation, message)
    assert state.unanswered_since == NOW
