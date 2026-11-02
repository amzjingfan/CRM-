"""调试只预演工具意图，不凭调用方计数触发兜底或保存内部业务记录。"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from pydantic import ValidationError

from app.agents.management.schemas import AgentDebugRequest


@pytest.mark.parametrize("field", ["unresolved_count", "fallback_due", "prior_reasons"])
def test_debug_request_rejects_caller_supplied_fallback_state(field):
    with pytest.raises(ValidationError):
        AgentDebugRequest.model_validate({"message": "请继续处理", field: 2})


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ["create_handoff_request", "add_internal_note"])
@pytest.mark.parametrize("preview_only", [False, True])
async def test_business_internal_tools_preview_intent_without_writing_and_formal_still_writes(
    monkeypatch, name, preview_only
):
    from app.agents.tools.business import AgentBusinessExecutor

    session = SimpleNamespace(add=Mock(), commit=AsyncMock(), rollback=AsyncMock())
    snapshot = SimpleNamespace(store_id=uuid.uuid4(), conversation_id=uuid.uuid4(), customer_id=uuid.uuid4())
    saved = AsyncMock(
        return_value=SimpleNamespace(kind="internal_note" if name == "add_internal_note" else "handoff_request")
    )
    monkeypatch.setattr("app.agents.tools.collaboration.save_collaboration", saved)
    service = AgentBusinessExecutor(
        session,
        SimpleNamespace(id=uuid.uuid4()),
        snapshot,
        uuid.uuid4(),
        frozenset({"workspace.reply"}),
        "test-debug",
        preview_only=preview_only,
    )
    monkeypatch.setattr(service, "authorize", AsyncMock(return_value=SimpleNamespace(platform="tiktok")))
    result = await service.invoke(name, {"content": "请人工核实买家问题。"})
    assert result["status"] == ("previewed" if preview_only else "succeeded")
    assert result["facts"]["record_saved"] is (not preview_only)
    assert result["facts"]["send_performed"] is False and result["facts"]["transfer_performed"] is False
    if preview_only:
        saved.assert_not_awaited()
        session.add.assert_not_called()
        session.commit.assert_not_called()
    else:
        saved.assert_awaited_once()
        assert session.add.call_args.args[0].action == "agent.tool.internal_write"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case", ["matched", "different_agent", "missing_policy", "missing_order", "missing_order_permission"]
)
async def test_selected_logistics_preview_reuses_verified_path_and_never_substitutes_agent(monkeypatch, case):
    from app.agents.management import debug
    from app.agents.management.schemas import AgentLogisticsPreviewRequest
    from app.agents.tools.logistics_updates.integration import ManualLogisticsPreview
    from app.shared.exceptions.errors import AppError

    store_id, agent_id, conversation_id, customer_id, order_id = (uuid.uuid4() for _ in range(5))
    policy = (
        None
        if case == "missing_policy"
        else SimpleNamespace(agent_id=uuid.uuid4() if case == "different_agent" else agent_id)
    )
    conversation = SimpleNamespace(id=conversation_id, customer_id=customer_id)
    order = None if case == "missing_order" else SimpleNamespace(id=order_id)
    session = SimpleNamespace(get=AsyncMock(return_value=policy), scalar=AsyncMock(side_effect=[conversation, order]))
    monkeypatch.setattr(debug, "get_config", AsyncMock(return_value=SimpleNamespace(id=agent_id, store_id=store_id)))
    monkeypatch.setattr(
        debug,
        "get_published_agent",
        AsyncMock(return_value=SimpleNamespace(agent_type="logistics_event", ready_for_v2=True)),
    )
    monkeypatch.setattr(
        debug, "get_settings", lambda: SimpleNamespace(agent_debug_enabled=True, agent_v2_debug_enabled=True)
    )
    monkeypatch.setattr(
        debug,
        "require_policy_access",
        AsyncMock(
            return_value={"workspace.reply"}
            if case == "missing_order_permission"
            else {"workspace.reply", "orders.view"}
        ),
    )
    verified = AsyncMock(
        return_value=ManualLogisticsPreview(
            status="previewed",
            preview_text="Latest verified node.",
            tool_calls=[{"name": "query_logistics", "status": "succeeded"}],
            citations=["synthetic-chunk"],
        )
    )
    monkeypatch.setattr(debug, "manual_preview", verified)
    request = AgentLogisticsPreviewRequest(
        conversation_id=conversation_id, external_order_id="771100", package_id="123"
    )
    if case != "matched":
        with pytest.raises(AppError):
            await debug.run_logistics_agent_preview(session, SimpleNamespace(id=uuid.uuid4()), agent_id, request)
        verified.assert_not_awaited()
    else:
        result = await debug.run_logistics_agent_preview(session, SimpleNamespace(id=uuid.uuid4()), agent_id, request)
        payload = verified.await_args.args[2]
        assert payload.store_id == store_id and payload.order_id == order_id and payload.package_id == "123"
        assert result.tool_calls[0]["name"] == "query_logistics" and result.citations == ["synthetic-chunk"]
    with pytest.raises(ValidationError):
        AgentLogisticsPreviewRequest.model_validate({**request.model_dump(), "event": {"description": "forged"}})
