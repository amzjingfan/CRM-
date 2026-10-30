"""审阅交付的授权、原问题绑定及预演无发送边界。"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.agents.delivery import service
from app.agents.delivery.batches import MemoryBatchStore
from app.agents.delivery.contracts import ReplyBatchRequest
from app.shared.exceptions.errors import AppError
from app.workspace import service as workspace


def setup(monkeypatch):
    conversation = SimpleNamespace(id=uuid.uuid4(), store_id=uuid.uuid4(), status="active")
    actor = SimpleNamespace(id=uuid.uuid4())
    session = SimpleNamespace(add=lambda _: None, commit=AsyncMock(), scalar=AsyncMock(return_value=None))
    monkeypatch.setattr(service, "allowed_store_ids", AsyncMock(return_value={conversation.store_id}))
    monkeypatch.setattr(service, "find_conversation", AsyncMock(return_value=conversation))
    monkeypatch.setattr(service, "current_permissions", AsyncMock(return_value={"workspace.reply", "orders.view"}))
    memory = MemoryBatchStore()
    monkeypatch.setattr(service, "SqlBatchStore", lambda *_: memory)
    sender = AsyncMock(side_effect=AssertionError("不应调用平台发送"))
    monkeypatch.setattr(workspace, "send_agent_message", sender)
    monkeypatch.setattr(workspace, "send_agent_logistics_card", sender)
    monkeypatch.setattr(
        workspace,
        "get_logistics_card_preview",
        AsyncMock(return_value=[SimpleNamespace(card=SimpleNamespace(package_id="123"))]),
    )
    return session, actor, conversation, sender


@pytest.mark.asyncio
async def test_preview_verifies_current_buyer_card_but_never_sends(monkeypatch):
    session, actor, conv, sender = setup(monkeypatch)
    payload = ReplyBatchRequest(
        parts=[
            {"kind": "text", "content": "Delivered"},
            {"kind": "logistics_card", "order_id": "600001", "package_id": "123"},
        ]
    )
    result = await service.deliver_reviewed_batch(session, actor, conv.id, payload, "preview")
    assert result.status == "previewed" and all(part.status == "previewed" for part in result.parts)
    workspace.get_logistics_card_preview.assert_awaited_once_with(session, actor, conv.id, "600001")
    sender.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["store", "permission", "trigger", "package", "closed"])
async def test_scope_and_original_question_failure_never_sends(monkeypatch, failure):
    session, actor, conv, sender = setup(monkeypatch)
    payload = ReplyBatchRequest(
        parts=[
            {"kind": "text", "content": "Delivered"},
            {"kind": "logistics_card", "order_id": "600001", "package_id": "123"},
        ],
        preview_only=False,
        confirmed=True,
    )
    if failure == "store":
        monkeypatch.setattr(service, "find_conversation", AsyncMock(return_value=None))
    elif failure == "permission":
        monkeypatch.setattr(service, "current_permissions", AsyncMock(return_value={"workspace.reply"}))
    elif failure == "trigger":
        payload.trigger_message_id = uuid.uuid4()
    elif failure == "package":
        monkeypatch.setattr(workspace, "get_logistics_card_preview", AsyncMock(return_value=[]))
    else:
        conv.status = "closed"
    with pytest.raises(AppError):
        await service.deliver_reviewed_batch(session, actor, conv.id, payload, "blocked")
    sender.assert_not_awaited()


@pytest.mark.asyncio
async def test_other_unknown_message_blocks_before_write_with_retryable_typed_failure(monkeypatch):
    from app.tools.contracts import ToolResult
    from app.workspace.delivery_errors import DeliveryNotStarted

    actor = SimpleNamespace(id=uuid.uuid4())
    conv = SimpleNamespace(
        id=uuid.uuid4(), store_id=uuid.uuid4(), status="active", platform="tiktok", assigned_user_id=actor.id
    )
    session = SimpleNamespace(scalar=AsyncMock(return_value=None))
    monkeypatch.setattr(workspace, "find_conversation", AsyncMock(return_value=conv))
    monkeypatch.setattr(workspace, "allowed_store_ids", AsyncMock(return_value={conv.store_id}))
    monkeypatch.setattr(workspace, "_connected_send_channel", AsyncMock(return_value=object()))
    monkeypatch.setattr(workspace, "_message_send_mode", lambda *_: "real")
    executor = SimpleNamespace(
        execute=AsyncMock(
            return_value=ToolResult(
                tool_call_id=uuid.uuid4(), status="failed", error_code="TOOL_RECONCILIATION_REQUIRED"
            )
        )
    )
    monkeypatch.setattr(workspace, "SqlAlchemyToolExecutor", lambda _: executor)
    with pytest.raises(DeliveryNotStarted) as raised:
        await workspace.send_agent_message(session, actor, conv.id, "Reviewed", "attempt-1", confirmed=True)
    assert raised.value.status_code == 409
    session.scalar.assert_not_awaited()


@pytest.mark.asyncio
async def test_entire_store_access_revoked_after_claim_is_known_not_started(monkeypatch):
    from app.shared.exceptions.errors import ErrorCode

    session, actor, conv, sender = setup(monkeypatch)
    monkeypatch.setattr(
        service,
        "current_permissions",
        AsyncMock(side_effect=[{"workspace.reply"}, AppError(ErrorCode.RESOURCE_NOT_FOUND, "资源不存在", 404)]),
    )
    payload = ReplyBatchRequest(parts=[{"kind": "text", "content": "Reviewed"}], preview_only=False, confirmed=True)
    result = await service.deliver_reviewed_batch(session, actor, conv.id, payload, "revoked")
    assert result.status == "failed" and result.parts[0].message_id is None
    sender.assert_not_awaited()
