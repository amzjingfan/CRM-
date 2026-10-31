"""坐席只可读取获授权会话的自动预演草稿。"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.chat import auto_preview
from app.shared.exceptions.errors import AppError


@pytest.mark.asyncio
async def test_cross_store_preview_read_is_rejected_before_task_query(monkeypatch) -> None:
    session = SimpleNamespace(scalar=AsyncMock())
    monkeypatch.setattr(auto_preview, "allowed_store_ids", AsyncMock(return_value=set()))
    with pytest.raises(AppError):
        await auto_preview.get_auto_preview(session, SimpleNamespace(id=uuid.uuid4()), uuid.uuid4())
    session.scalar.assert_not_awaited()


@pytest.mark.asyncio
async def test_preview_read_returns_review_content_without_send_state(monkeypatch) -> None:
    store_id, conversation_id, trigger_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    conversation = SimpleNamespace(id=conversation_id, store_id=store_id)
    task = SimpleNamespace(
        id=uuid.uuid4(),
        store_id=store_id,
        conversation_id=conversation_id,
        trigger_message_id=trigger_id,
        agent_run_id=uuid.uuid4(),
        status="human_review",
        preview_content="Latest status: in transit.",
        processed_at=None,
    )
    session = SimpleNamespace(scalar=AsyncMock(side_effect=[conversation, task]))
    monkeypatch.setattr(auto_preview, "allowed_store_ids", AsyncMock(return_value={store_id}))
    view = await auto_preview.get_auto_preview(session, SimpleNamespace(id=uuid.uuid4()), conversation_id)
    assert view is not None
    assert view.content == "Latest status: in transit."
    assert view.send_performed is False
    assert view.trigger_message_id == trigger_id
