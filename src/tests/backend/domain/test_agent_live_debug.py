"""Agent 页面真实调试的店铺、能力和审计边界。"""

import asyncio
import uuid
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.agent.schemas import AgentAction, WorkflowTerminalState
from app.agent_management import debug
from app.agent_management.schemas import AgentDebugRequest
from app.shared.config.settings import Settings
from app.shared.exceptions.errors import AppError
from app.tools.contracts import (
    QueryLogisticsArguments,
    QueryOrderArguments,
    ToolExecutionContext,
    ToolInvocation,
    validate_tool_output,
)
from app.workspace.sidebar import SidebarOrder


def _user(*permissions: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        roles=[SimpleNamespace(code="operator", permissions=[SimpleNamespace(code=p) for p in permissions])],
    )


def _config() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        store_id=uuid.uuid4(),
        status="disabled",
        knowledge_scope={"agent_type": "service", "file_ids": [str(uuid.uuid4())]},
        enabled_tools=["query_order", "query_logistics", "transfer_to_human", "send_platform_message"],
    )


@pytest.mark.asyncio
async def test_disabled_agent_debug_uses_bound_files_without_customer_side_effects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config()
    captured = []
    result = SimpleNamespace(
        agent_run_id=uuid.uuid4(),
        draft_reply="根据已审批知识，请联系坐席确认。",
        action=AgentAction.HUMAN_REVIEW,
        terminal_state=WorkflowTerminalState.HUMAN_REVIEW,
        citations=[],
        tool_calls=[],
        trace_id="trace-debug",
    )
    monkeypatch.setattr(
        debug,
        "get_settings",
        lambda: SimpleNamespace(agent_debug_enabled=True, embedding_enabled=True, agent_debug_timeout_seconds=2),
    )
    monkeypatch.setattr(debug, "get_config", AsyncMock(return_value=config))
    monkeypatch.setattr(debug, "validate_knowledge_file_ids", AsyncMock())

    async def run(_session, command):  # type: ignore[no-untyped-def]
        captured.append(command)
        return result

    monkeypatch.setattr(debug, "build_agent_workflow", lambda *_args, **_kwargs: SimpleNamespace(run=run))
    audits = []
    session = SimpleNamespace(get=AsyncMock(return_value=None), add=audits.append, commit=AsyncMock())
    response = await debug.run_agent_debug(
        session,
        _user("agent.manage", "knowledge.view"),
        config.id,
        AgentDebugRequest(message="物流政策是什么？"),
        "trace-debug",
        object(),  # type: ignore[arg-type]
    )
    assert response.content == result.draft_reply
    assert captured[0].debug_mode is True
    assert captured[0].agent_config_id == config.id
    assert captured[0].knowledge_file_ids == [uuid.UUID(config.knowledge_scope["file_ids"][0])]
    assert captured[0].tool_context.available_tools == set()
    assert captured[0].tool_context.approved_actions == []
    assert config.status == "disabled"
    assert audits[0].action == "agent.debug.run"
    assert audits[0].after_data == {"has_conversation": False, "bound_file_count": 1}


@pytest.mark.asyncio
async def test_agent_debug_requires_explicit_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        debug, "get_settings", lambda: SimpleNamespace(agent_debug_enabled=False, embedding_enabled=True)
    )
    with pytest.raises(AppError) as error:
        await debug.run_agent_debug(
            AsyncMock(), _user("agent.manage"), uuid.uuid4(), AgentDebugRequest(message="你好"), "trace", None
        )  # type: ignore[arg-type]
    assert error.value.status_code == 503


@pytest.mark.asyncio
async def test_agent_debug_without_bound_files_does_not_fall_back_to_store_faq(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config()
    config.knowledge_scope["file_ids"] = []
    captured = []
    monkeypatch.setattr(
        debug,
        "get_settings",
        lambda: SimpleNamespace(agent_debug_enabled=True, embedding_enabled=True, agent_debug_timeout_seconds=2),
    )
    monkeypatch.setattr(debug, "get_config", AsyncMock(return_value=config))

    async def run(_session, command):  # type: ignore[no-untyped-def]
        captured.append(command)
        return SimpleNamespace(
            agent_run_id=uuid.uuid4(),
            draft_reply=None,
            action=AgentAction.HUMAN_REVIEW,
            terminal_state=WorkflowTerminalState.HUMAN_REVIEW,
            citations=[],
            tool_calls=[],
            trace_id="trace",
        )

    monkeypatch.setattr(debug, "build_agent_workflow", lambda *_args, **_kwargs: SimpleNamespace(run=run))
    session = SimpleNamespace(get=AsyncMock(return_value=None), add=lambda _: None, commit=AsyncMock())
    response = await debug.run_agent_debug(
        session,
        _user("agent.manage"),
        config.id,
        AgentDebugRequest(message="你好"),
        "trace",
        object(),  # type: ignore[arg-type]
    )
    assert response.action == AgentAction.HUMAN_REVIEW.value
    assert captured[0].knowledge_file_ids == []
    assert captured[0].debug_mode is True


@pytest.mark.asyncio
async def test_agent_debug_rejects_cross_store_conversation(monkeypatch: pytest.MonkeyPatch) -> None:
    config = _config()
    monkeypatch.setattr(
        debug, "get_settings", lambda: SimpleNamespace(agent_debug_enabled=True, embedding_enabled=True)
    )
    monkeypatch.setattr(debug, "get_config", AsyncMock(return_value=config))
    monkeypatch.setattr(debug, "validate_knowledge_file_ids", AsyncMock())
    session = SimpleNamespace(scalar=AsyncMock(return_value=None))
    with pytest.raises(AppError) as error:
        await debug.run_agent_debug(
            session,
            _user("agent.manage", "knowledge.view", "workspace.view"),
            config.id,
            AgentDebugRequest(message="订单在哪？", conversation_id=uuid.uuid4()),
            "trace",
            object(),  # type: ignore[arg-type]
        )
    assert error.value.status_code == 404
    assert "conversations.store_id" in str(session.scalar.call_args.args[0])


@pytest.mark.asyncio
async def test_agent_debug_context_needs_workspace_permission(monkeypatch: pytest.MonkeyPatch) -> None:
    config = _config()
    monkeypatch.setattr(
        debug, "get_settings", lambda: SimpleNamespace(agent_debug_enabled=True, embedding_enabled=True)
    )
    monkeypatch.setattr(debug, "get_config", AsyncMock(return_value=config))
    monkeypatch.setattr(debug, "validate_knowledge_file_ids", AsyncMock())
    with pytest.raises(AppError) as error:
        await debug.run_agent_debug(
            AsyncMock(),
            _user("agent.manage", "knowledge.view"),
            config.id,
            AgentDebugRequest(message="订单在哪？", conversation_id=uuid.uuid4()),
            "trace",
            object(),  # type: ignore[arg-type]
        )
    assert error.value.status_code == 403


@pytest.mark.asyncio
async def test_agent_debug_only_grants_configured_read_tools_for_authorized_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config()
    conversation = SimpleNamespace(id=uuid.uuid4(), store_id=config.store_id, customer_id=uuid.uuid4())
    order = SimpleNamespace(id=uuid.uuid4())
    session = SimpleNamespace(
        scalar=AsyncMock(side_effect=[conversation, order]),
        get=AsyncMock(return_value=None),
        add=lambda _: None,
        commit=AsyncMock(),
    )
    captured = []
    monkeypatch.setattr(
        debug,
        "get_settings",
        lambda: SimpleNamespace(agent_debug_enabled=True, embedding_enabled=True, agent_debug_timeout_seconds=2),
    )
    monkeypatch.setattr(debug, "get_config", AsyncMock(return_value=config))
    monkeypatch.setattr(debug, "validate_knowledge_file_ids", AsyncMock())

    async def run(_session, command):  # type: ignore[no-untyped-def]
        captured.append(command)
        return SimpleNamespace(
            agent_run_id=uuid.uuid4(),
            draft_reply=None,
            action=AgentAction.HUMAN_REVIEW,
            terminal_state=WorkflowTerminalState.HUMAN_REVIEW,
            citations=[],
            tool_calls=[],
            trace_id="trace",
        )

    monkeypatch.setattr(debug, "build_agent_workflow", lambda *_args, **_kwargs: SimpleNamespace(run=run))
    await debug.run_agent_debug(
        session,
        _user("agent.manage", "knowledge.view", "workspace.view"),
        config.id,
        AgentDebugRequest(message="订单在哪？", conversation_id=conversation.id),
        "trace",
        object(),  # type: ignore[arg-type]
    )
    context = captured[0].tool_context
    assert context.customer_id == conversation.customer_id
    assert context.order_id == str(order.id)
    assert context.available_tools == {"query_order", "query_logistics"}
    assert "transfer_to_human" not in context.available_tools
    assert "send_platform_message" not in context.available_tools


@pytest.mark.asyncio
async def test_agent_debug_uses_verified_live_buyer_order_without_persisting_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """本地未同步订单时仅借用已验证平台订单的只读投影。"""
    config = _config()
    config.knowledge_scope["file_ids"] = []
    conversation = SimpleNamespace(
        id=uuid.uuid4(), store_id=config.store_id, customer_id=uuid.uuid4(), platform="tiktok"
    )
    order = SidebarOrder(
        id=uuid.uuid4(),
        external_order_id="123456789",
        status="SHIPPED",
        payment_status=None,
        currency="USD",
        total_amount=Decimal("12.00"),
        payment_breakdown={},
        ordered_at=None,
        tracking_number="synthetic-tracking",
        tracking_status=None,
        items=[],
        live_detail_available=True,
    )
    session = SimpleNamespace(
        scalar=AsyncMock(side_effect=[conversation, None]),
        get=AsyncMock(return_value=None),
        add=lambda _: None,
        commit=AsyncMock(),
    )
    captured = []
    monkeypatch.setattr(
        debug,
        "get_settings",
        lambda: SimpleNamespace(
            agent_debug_enabled=True,
            embedding_enabled=True,
            real_tiktok_read_enabled=True,
            agent_debug_timeout_seconds=10,
        ),
    )
    monkeypatch.setattr(debug, "get_config", AsyncMock(return_value=config))
    monkeypatch.setattr(debug, "latest_verified_live_order", AsyncMock(return_value=order))

    async def run(_session, command):  # type: ignore[no-untyped-def]
        captured.append(command)
        return SimpleNamespace(
            agent_run_id=uuid.uuid4(),
            draft_reply=None,
            action=AgentAction.HUMAN_REVIEW,
            terminal_state=WorkflowTerminalState.HUMAN_REVIEW,
            citations=[],
            tool_calls=[],
            trace_id="trace",
        )

    def workflow(_session, _settings, **kwargs):  # type: ignore[no-untyped-def]
        captured.append(kwargs["tool_executor"])
        return SimpleNamespace(run=run)

    monkeypatch.setattr(debug, "build_agent_workflow", workflow)
    await debug.run_agent_debug(
        session,
        _user("agent.manage", "workspace.view"),
        config.id,
        AgentDebugRequest(message="我的包裹到哪里了？", conversation_id=conversation.id),
        "trace",
        object(),
    )

    assert captured[0].store_id == config.store_id
    assert captured[1].tool_context.order_id == str(order.id)
    assert captured[1].tool_context.available_tools == {"query_order", "query_logistics"}
    assert session.commit.await_count == 1


@pytest.mark.asyncio
async def test_agent_debug_live_order_tool_only_returns_scoped_minimal_fields() -> None:
    store_id = uuid.uuid4()
    order = SidebarOrder(
        id=uuid.uuid4(),
        external_order_id="123456789",
        status="SHIPPED",
        payment_status=None,
        currency="USD",
        total_amount=Decimal("12.00"),
        payment_breakdown={},
        ordered_at=None,
        tracking_number="synthetic-tracking",
        tracking_status=None,
        items=[],
        live_detail_available=True,
    )
    executor = debug.AgentDebugLiveOrderExecutor(AsyncMock(), store_id, order)
    invocation = ToolInvocation(
        tool_name="query_order",
        idempotency_key="test-only",
        arguments={"order_id": str(order.id)},
        context=ToolExecutionContext(store_id=store_id, actor_type="agent", permissions={"orders.view"}),
    )
    order_result = await executor._query_order(invocation, QueryOrderArguments(order_id=str(order.id)))
    logistics_result = await executor._query_logistics(invocation, QueryLogisticsArguments(order_id=str(order.id)))

    assert validate_tool_output("query_order", order_result.data or {})["status"] == "SHIPPED"
    assert (
        validate_tool_output("query_logistics", logistics_result.data or {})["tracking_number"] == "synthetic-tracking"
    )
    assert logistics_result.data["tracking_status"] is None
    assert "synthetic-tracking" not in str(logistics_result.output_summary)


@pytest.mark.asyncio
async def test_agent_debug_live_order_lookup_shares_overall_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    config = _config()
    config.knowledge_scope["file_ids"] = []
    conversation = SimpleNamespace(
        id=uuid.uuid4(), store_id=config.store_id, customer_id=uuid.uuid4(), platform="tiktok"
    )
    session = SimpleNamespace(scalar=AsyncMock(side_effect=[conversation, None]))
    monkeypatch.setattr(
        debug,
        "get_settings",
        lambda: SimpleNamespace(
            agent_debug_enabled=True,
            embedding_enabled=True,
            real_tiktok_read_enabled=True,
            agent_debug_timeout_seconds=0.01,
        ),
    )
    monkeypatch.setattr(debug, "get_config", AsyncMock(return_value=config))

    async def slow_lookup(*_args):  # type: ignore[no-untyped-def]
        await asyncio.sleep(0.1)

    monkeypatch.setattr(debug, "latest_verified_live_order", slow_lookup)
    with pytest.raises(AppError) as error:
        await debug.run_agent_debug(
            session,
            _user("agent.manage", "workspace.view"),
            config.id,
            AgentDebugRequest(message="我的包裹到哪里了？", conversation_id=conversation.id),
            "trace",
            object(),
        )
    assert error.value.status_code == 504


@pytest.mark.asyncio
async def test_agent_debug_timeout_returns_safe_error(monkeypatch: pytest.MonkeyPatch) -> None:
    config = _config()
    monkeypatch.setattr(
        debug,
        "get_settings",
        lambda: SimpleNamespace(agent_debug_enabled=True, embedding_enabled=True, agent_debug_timeout_seconds=0.01),
    )
    monkeypatch.setattr(debug, "get_config", AsyncMock(return_value=config))
    monkeypatch.setattr(debug, "validate_knowledge_file_ids", AsyncMock())

    async def run(_session, _command):  # type: ignore[no-untyped-def]
        await asyncio.sleep(1)

    monkeypatch.setattr(debug, "build_agent_workflow", lambda *_args, **_kwargs: SimpleNamespace(run=run))
    with pytest.raises(AppError) as error:
        await debug.run_agent_debug(
            SimpleNamespace(add=lambda _: None, commit=AsyncMock()),
            _user("agent.manage", "knowledge.view"),
            config.id,
            AgentDebugRequest(message="你好"),
            "trace",
            object(),  # type: ignore[arg-type]
        )
    assert error.value.status_code == 504


def test_debug_runtime_keeps_general_llm_disabled() -> None:
    settings = Settings(
        _env_file=None,
        APP_ENV="test",
        AGENT_DEBUG_ENABLED=True,
        EMBEDDING_ENABLED=True,
        LLM_PRIMARY_PROVIDER="deepseek",
        LLM_PRIMARY_MODEL="deepseek-chat",
        DEEPSEEK_API_KEY="test-key",
        RETRIEVAL_MODEL_SERVICE_TOKEN="x" * 32,
        LLM_FALLBACK_MODEL="",
    )
    assert settings.agent_debug_enabled is True
    assert settings.llm_enabled is False
