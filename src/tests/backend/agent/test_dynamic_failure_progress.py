"""模型失败和入口超时只保留安全进度，不发布迟到答案或派生事实。"""

import asyncio
import time
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.agents.core.errors import LLMErrorCode, LLMProviderError
from app.agents.orchestration import service
from app.agents.orchestration.coordinator import SpecialistResult
from app.agents.orchestration.router import RoutedAgent, RoutePlan
from app.agents.providers.tool_calling import ToolTurn
from app.agents.tools.loop import ToolEvent
from app.shared.exceptions.errors import AppError


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["aggregate", "review"])
@pytest.mark.parametrize("failure", ["provider", "sdk", "timeout"])
async def test_failed_aggregate_or_review_keeps_specialists_and_known_usage(monkeypatch, stage, failure):
    agent = uuid.uuid4()
    route = RoutePlan((RoutedAgent(agent, "订单"),), 1, 3, 2)
    monkeypatch.setattr(service, "route_agents", AsyncMock(return_value=route))
    error = (
        LLMProviderError(LLMErrorCode.LLM_OUTPUT_INVALID, "invalid", retriable=False)
        if failure == "provider"
        else TimeoutError()
        if failure == "timeout"
        else RuntimeError("never expose this SDK body")
    )
    turns = [error] if stage == "aggregate" else [ToolTurn("订单已发货。", (), {}, 20, 8), error]
    result = await service.execute_dynamic_run(
        question="订单怎样",
        snapshot=SimpleNamespace(store_id=uuid.uuid4(), published_agents=()),
        router=SimpleNamespace(),
        aggregator=SimpleNamespace(complete=AsyncMock(side_effect=turns)),
        worker=AsyncMock(
            return_value=SpecialistResult(
                agent,
                "订单已发货。",
                verified_facts={"status": "shipped"},
                tool_events=(ToolEvent("read", "query_order", "succeeded"),),
                input_tokens=11,
                output_tokens=4,
            )
        ),
        deadline=time.monotonic() + 2,
        max_catalog_tokens=1000,
    )
    assert result.suggestion.content is None
    assert result.phase.value in {"review_required", "timeout"}
    assert result.specialists[0].tool_events[0].status == "succeeded"
    assert (result.specialists[0].input_tokens, result.specialists[0].output_tokens) == (11, 4)
    assert (result.suggestion.input_tokens, result.suggestion.output_tokens) == (
        (20, 8) if stage == "review" else (0, 0)
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["debug", "formal"])
async def test_entry_outer_deadline_persists_partial_tool_metadata(monkeypatch, mode):
    from app.agents.management import debug
    from app.agents.management.schemas import AgentDebugRequest
    from app.agents.runtime import formal

    module = debug if mode == "debug" else formal
    store, agent_id, conversation_id, customer, trigger_id = (uuid.uuid4() for _ in range(5))
    agent = SimpleNamespace(
        id=agent_id, config_version=1, name="合成 Agent", agent_type="service", file_ids=(), ready_for_v2=True
    )
    conversation = SimpleNamespace(id=conversation_id, store_id=store, customer_id=customer)
    snapshot = SimpleNamespace(
        store_id=store, published_agents=(agent,), snapshot_hash="test", low_sensitive_reference=lambda: {}
    )
    settings = SimpleNamespace(
        agent_debug_enabled=True,
        agent_v2_formal_enabled=True,
        llm_enabled=True,
        embedding_enabled=False,
        agent_debug_timeout_seconds=0.03,
        llm_primary_provider="deepseek",
        llm_primary_model="deepseek-chat",
    )
    monkeypatch.setattr(module, "get_settings", lambda: settings)
    monkeypatch.setattr(module, "validate_tool_model", lambda *_: None)
    monkeypatch.setattr(
        module,
        "load_memory",
        AsyncMock(return_value=SimpleNamespace(summary="", facts=(), source_message_ids=())),
    )
    monkeypatch.setattr(
        service, "route_agents", AsyncMock(return_value=RoutePlan((RoutedAgent(agent_id, "订单"),), 1, 3, 2))
    )
    stopped = asyncio.Event()

    async def worker(_selection):
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            stopped.set()
            return SpecialistResult(
                agent_id,
                "late private answer",
                verified_facts={"unsafe": "late"},
                tool_events=(ToolEvent("read", "query_order", "succeeded"),),
                input_tokens=11,
                output_tokens=4,
            )

    async def execute(**kwargs):
        return await service.execute_dynamic_run(
            question="订单",
            snapshot=snapshot,
            router=SimpleNamespace(),
            aggregator=SimpleNamespace(),
            worker=worker,
            # 此例专测入口外层取消，避免内外同一时刻到期导致竞态改走正常超时返回。
            deadline=kwargs["deadline"] + 1,
            max_catalog_tokens=1000,
            progress=kwargs["progress"],
        )

    monkeypatch.setattr(module, "execute_model_run", execute)
    persist = AsyncMock()
    monkeypatch.setattr(module, "persist_dynamic_result", persist)
    session = SimpleNamespace(scalar=AsyncMock(return_value=0), add=Mock(), commit=AsyncMock())
    if mode == "debug":
        monkeypatch.setattr(debug, "get_config", AsyncMock(return_value=SimpleNamespace(id=agent_id, store_id=store)))
        monkeypatch.setattr(debug, "get_published_agent", AsyncMock(return_value=agent))
        monkeypatch.setattr(debug, "user_permissions", lambda _: set())
        monkeypatch.setattr(debug, "require_knowledge_view_for_binding", lambda *_: None)
        monkeypatch.setattr(debug, "freeze_debug_context", AsyncMock(return_value=snapshot))
        call = debug.run_agent_debug_v2(
            session, SimpleNamespace(id=uuid.uuid4()), agent_id, AgentDebugRequest(message="订单"), "test", None
        )
    else:
        monkeypatch.setattr(formal, "list_enabled_agents", AsyncMock(return_value=(agent,)))
        monkeypatch.setattr(formal, "freeze_run_context", AsyncMock(return_value=snapshot))
        call = formal.run_formal_suggestion(
            session,
            conversation=conversation,
            trigger=SimpleNamespace(id=trigger_id, content="订单", message_type="text"),
            trace_id="test",
            permissions=set(),
            runtime=None,
        )
    with pytest.raises(AppError) as caught:
        await call
    assert caught.value.status_code == 504
    assert stopped.is_set()
    saved = persist.await_args.kwargs["result"]
    assert saved.phase.value == "timeout"
    assert (saved.route.input_tokens, saved.route.output_tokens) == (3, 2)
    partial = saved.specialists[0]
    assert [(e.name, e.status) for e in partial.tool_events] == [("query_order", "succeeded")]
    assert (partial.input_tokens, partial.output_tokens) == (11, 4)
    assert partial.answer is None and not partial.verified_facts and not partial.observations
    assert saved.suggestion.content is None


@pytest.mark.asyncio
async def test_active_request_cancellation_propagates_and_retains_diagnostics(monkeypatch):
    from app.agents.orchestration.service import RunProgress

    agent = uuid.uuid4()
    started = asyncio.Event()
    progress = RunProgress()
    monkeypatch.setattr(
        service, "route_agents", AsyncMock(return_value=RoutePlan((RoutedAgent(agent, "订单"),), 1, 3, 2))
    )

    async def worker(_):
        started.set()
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            return SpecialistResult(agent, "late", tool_events=(ToolEvent("read", "query_order", "succeeded"),))

    task = asyncio.create_task(
        service.execute_dynamic_run(
            question="订单",
            snapshot=SimpleNamespace(store_id=uuid.uuid4(), published_agents=()),
            router=SimpleNamespace(),
            aggregator=SimpleNamespace(),
            worker=worker,
            deadline=time.monotonic() + 20,
            max_catalog_tokens=1000,
            progress=progress,
        )
    )
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert progress.specialists[0].tool_events[0].status == "succeeded"
    assert progress.specialists[0].answer is None
