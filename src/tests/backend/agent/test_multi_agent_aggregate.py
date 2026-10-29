"""多个专家并行处理后，冲突或超时必须可观察并交人工。"""

import asyncio
import time
import uuid

import pytest
from agent._review_helpers import accepted_review_turn

from app.agents.orchestration.aggregator import aggregate_results
from app.agents.orchestration.coordinator import SpecialistResult, run_selected
from app.agents.orchestration.router import RoutedAgent, RoutePlan
from app.agents.providers.tool_calling import ToolTurn


class AnswerModel:
    def __init__(self, answer: str) -> None:
        self.answer = answer
        self.calls = 0

    async def complete(self, *, messages, tools, max_output_tokens):
        self.calls += 1
        if tools:
            return accepted_review_turn(messages)
        return ToolTurn(self.answer, (), {"role": "assistant", "content": self.answer}, 20, 8)


@pytest.mark.asyncio
async def test_two_specialists_are_aggregated_into_one_reviewed_answer() -> None:
    first, second = uuid.uuid4(), uuid.uuid4()
    plan = RoutePlan((RoutedAgent(first, "订单"), RoutedAgent(second, "物流")), 2, 0, 0)

    async def worker(selection):
        await asyncio.sleep(0.01 if selection.agent_id == first else 0)
        if selection.agent_id == first:
            return SpecialistResult(first, "订单已发货", {"order_status": "shipped"}, successful_tools=("query_order",))
        return SpecialistResult(
            second, "物流运输中", {"logistics_status": "in_transit"}, successful_tools=("query_logistics",)
        )

    results = await run_selected(plan=plan, worker=worker, deadline=time.monotonic() + 2)
    assert [item.agent_id for item in results] == [first, second]
    model = AnswerModel("订单已发货，物流运输中。")
    answer = await aggregate_results(
        question="订单和物流如何",
        results=results,
        provider=model,
        deadline=time.monotonic() + 2,
        store_id=uuid.uuid4(),
    )
    assert answer.content == "订单已发货，物流运输中。"
    assert answer.action == "human_review"
    assert model.calls == 2


@pytest.mark.asyncio
async def test_conflicting_verified_facts_stop_aggregation() -> None:
    model = AnswerModel("已送达")
    result = await aggregate_results(
        question="物流状态",
        results=(
            SpecialistResult(uuid.uuid4(), "在途", verified_facts={"order_status": "in_transit"}),
            SpecialistResult(uuid.uuid4(), "已送达", verified_facts={"order_status": "delivered"}),
        ),
        provider=model,
        deadline=time.monotonic() + 2,
        store_id=uuid.uuid4(),
    )
    assert result.reason_code == "conflicting_verified_facts"
    assert result.content is None
    assert model.calls == 0


@pytest.mark.asyncio
async def test_unverified_specialist_draft_cannot_become_answer() -> None:
    model = AnswerModel("订单已经送达。")
    result = await aggregate_results(
        question="订单到了吗",
        results=(SpecialistResult(uuid.uuid4(), "订单已经送达。"),),
        provider=model,
        deadline=time.monotonic() + 2,
        store_id=uuid.uuid4(),
    )
    assert result.reason_code == "no_verified_evidence"
    assert "无法核实" in (result.content or "")
    assert model.calls == 0


@pytest.mark.asyncio
async def test_global_deadline_cancels_slow_workers() -> None:
    fast, slow = uuid.uuid4(), uuid.uuid4()
    cancelled = asyncio.Event()

    async def worker(selection):
        if selection.agent_id == fast:
            return SpecialistResult(fast, "已查订单")
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            cancelled.set()
            raise

    results = await run_selected(
        plan=RoutePlan((RoutedAgent(fast, "订单"), RoutedAgent(slow, "物流")), 2, 0, 0),
        worker=worker,
        deadline=time.monotonic() + 0.05,
    )
    assert cancelled.is_set()
    assert results[0].answer == "已查订单"
    assert results[1].reason_code == "deadline_exceeded"


@pytest.mark.asyncio
async def test_deadline_retains_worker_partial_tool_events_without_publishing_partial_facts() -> None:
    from app.agents.tools.loop import ToolEvent

    agent = uuid.uuid4()

    async def worker(selection):
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            return SpecialistResult(
                agent,
                None,
                verified_facts={"status": "shipped"},
                reason_code="cancelled",
                tool_events=(ToolEvent("read", "query_order", "succeeded"),),
                input_tokens=10,
                output_tokens=5,
            )

    result = (
        await run_selected(
            plan=RoutePlan((RoutedAgent(agent, "订单"),), 1, 0, 0), worker=worker, deadline=time.monotonic() + 0.01
        )
    )[0]
    assert result.reason_code == "deadline_exceeded"
    assert [(event.name, event.status) for event in result.tool_events] == [("query_order", "succeeded")]
    assert (result.input_tokens, result.output_tokens) == (10, 5)
    assert result.answer is None and not result.verified_facts
