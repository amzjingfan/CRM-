"""路由改写失败只回退到已通过原有输入门禁的客户原文。"""

import json
import time
import uuid
from datetime import UTC, datetime
from types import MappingProxyType, SimpleNamespace
from unittest.mock import AsyncMock, Mock, call

import pytest

from app.agents.management.repository import PublishedAgent
from app.agents.orchestration.router import RoutedAgent
from app.agents.prompts.compiler import compile_prompt
from app.agents.prompts.sections import SECTION_TITLES
from app.agents.providers.tool_calling import ToolTurn
from app.agents.runtime import worker
from app.agents.runtime.context import ModelLimits
from app.agents.runtime.snapshot import RunSnapshot
from app.agents.tools.catalog import AgentToolContext
from app.shared.exceptions.errors import AppError, ErrorCode

ORIGINAL_QUESTION = "Please check my order and explain the care policy."
REJECTED_QUESTION = "Ship to 123 Main Street, New York, NY 10001"


@pytest.fixture
def specialist_inputs():
    store, conversation, customer, agent_id = (uuid.uuid4() for _ in range(4))
    sections = {key: "仅根据授权工具和知识回答。" for key, _ in SECTION_TITLES}
    agent = PublishedAgent(
        agent_id,
        store,
        1,
        "订单助手",
        "order",
        "回答订单问题",
        "service",
        "deepseek",
        "deepseek-chat",
        MappingProxyType(sections),
        compile_prompt(sections).content_sha256,
        ("query_order",),
        (),
        True,
    )
    now = datetime.now(UTC)
    return {
        "snapshot": RunSnapshot(store, conversation, customer, uuid.uuid4(), now, (), (agent,), (), 0, now, "hash"),
        "agent": agent,
        "provider": SimpleNamespace(
            complete=AsyncMock(return_value=ToolTurn("Please confirm the order.", (), {}, 3, 2))
        ),
        "executor": SimpleNamespace(execute=AsyncMock()),
        "rag_service": None,
        "session": AsyncMock(),
        "tool_context": AgentToolContext(
            store, uuid.uuid4(), "trusted-order", customer, frozenset({"orders.view"}), "trace"
        ),
        "deadline": time.monotonic() + 5,
        "model_limits": ModelLimits(8192, 1024, 256),
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "routed_question,expected_subquestion",
    [("Check the order status.", "Check the order status."), (REJECTED_QUESTION, ORIGINAL_QUESTION)],
    ids=["keep-valid-route", "discard-rejected-route"],
)
async def test_specialist_validates_original_before_route_and_passes_only_safe_question(
    monkeypatch, specialist_inputs, routed_question, expected_subquestion
) -> None:
    prepare = Mock(wraps=worker.prepare_untrusted_text)
    monkeypatch.setattr(worker, "prepare_untrusted_text", prepare)
    result = await worker.run_specialist(
        **specialist_inputs,
        selection=RoutedAgent(specialist_inputs["agent"].id, routed_question),
        customer_question=ORIGINAL_QUESTION,
    )

    assert result.answer == "Please confirm the order."
    assert prepare.call_args_list == [
        call(ORIGINAL_QUESTION, source="user_message"),
        call(routed_question, source="user_message"),
    ]
    messages = specialist_inputs["provider"].complete.await_args.kwargs["messages"]
    question_data = json.loads(messages[1]["content"])
    assert question_data["untrusted_question"] == ORIGINAL_QUESTION
    assert question_data["untrusted_subquestion"] == expected_subquestion
    assert REJECTED_QUESTION not in str(messages)


@pytest.mark.asyncio
@pytest.mark.parametrize("original_question", [REJECTED_QUESTION, None], ids=["reject-original", "no-original"])
async def test_rejected_original_or_only_question_still_stops_before_model_and_tools(
    monkeypatch, specialist_inputs, original_question
) -> None:
    prepare = Mock(wraps=worker.prepare_untrusted_text)
    monkeypatch.setattr(worker, "prepare_untrusted_text", prepare)
    routed_question = "Check the order status." if original_question is not None else REJECTED_QUESTION
    with pytest.raises(AppError) as error:
        await worker.run_specialist(
            **specialist_inputs,
            selection=RoutedAgent(specialist_inputs["agent"].id, routed_question),
            customer_question=original_question,
        )

    assert error.value.code == ErrorCode.VALIDATION_ERROR
    prepare.assert_called_once_with(REJECTED_QUESTION, source="user_message")
    specialist_inputs["provider"].complete.assert_not_awaited()
    specialist_inputs["executor"].execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_identical_original_and_route_is_validated_once(monkeypatch, specialist_inputs) -> None:
    prepare = Mock(wraps=worker.prepare_untrusted_text)
    monkeypatch.setattr(worker, "prepare_untrusted_text", prepare)
    await worker.run_specialist(
        **specialist_inputs,
        selection=RoutedAgent(specialist_inputs["agent"].id, ORIGINAL_QUESTION),
        customer_question=ORIGINAL_QUESTION,
    )

    prepare.assert_called_once_with(ORIGINAL_QUESTION, source="user_message")


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [AppError(ErrorCode.PERMISSION_DENIED, "not allowed", 403), RuntimeError("failed")])
async def test_route_errors_other_than_validation_are_not_swallowed(monkeypatch, specialist_inputs, failure) -> None:
    prepare = Mock(side_effect=[worker.prepare_untrusted_text(ORIGINAL_QUESTION, source="user_message"), failure])
    monkeypatch.setattr(worker, "prepare_untrusted_text", prepare)
    with pytest.raises(type(failure)) as error:
        await worker.run_specialist(
            **specialist_inputs,
            selection=RoutedAgent(specialist_inputs["agent"].id, "Check the order status."),
            customer_question=ORIGINAL_QUESTION,
        )

    assert error.value is failure
    assert prepare.call_args_list[0] == call(ORIGINAL_QUESTION, source="user_message")
    specialist_inputs["provider"].complete.assert_not_awaited()
    specialist_inputs["executor"].execute.assert_not_awaited()
