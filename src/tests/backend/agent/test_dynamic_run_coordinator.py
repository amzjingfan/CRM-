"""一次动态运行必须按路由、专家、汇总的同一快照与截止时间执行。"""

import time
import uuid
from dataclasses import replace
from datetime import UTC, datetime
from types import MappingProxyType, SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from agent._review_helpers import accepted_review_turn

from app.agents.management.repository import PublishedAgent
from app.agents.orchestration.coordinator import SpecialistResult
from app.agents.orchestration.service import RunProgress, execute_dynamic_run
from app.agents.providers.tool_calling import FunctionCall, ToolTurn
from app.agents.runtime.snapshot import RunSnapshot
from app.agents.tools.loop import ToolEvent


@pytest.mark.asyncio
@pytest.mark.parametrize("reply_plan", [False, True])
async def test_dynamic_run_routes_two_agents_and_returns_one_reviewed_suggestion(reply_plan) -> None:
    store, conversation, customer = (uuid.uuid4() for _ in range(3))
    agents = tuple(
        PublishedAgent(
            id=uuid.uuid4(),
            store_id=store,
            config_version=1,
            name=name,
            code=name,
            description=name,
            agent_type="service",
            model_provider="deepseek",
            model_name="deepseek-chat",
            prompt_sections=MappingProxyType(
                {"language_format": f"{name}: follow buyer language; plain text; match requested detail"}
            ),
            prompt_hash="hash",
            tool_names=(),
            file_ids=(),
            ready_for_v2=True,
        )
        for name in ("order", "logistics")
    )
    now = datetime.now(UTC)
    snapshot = RunSnapshot(store, conversation, customer, uuid.uuid4(), now, (), agents, (), 0, now, "hash")
    router = SimpleNamespace(
        complete=AsyncMock(
            return_value=ToolTurn(
                None,
                (
                    FunctionCall(
                        "route",
                        "route_agents",
                        {
                            "question_language": "zh-CN",
                            "selections": [{"agent_id": str(item.id), "subquestion": item.name} for item in agents],
                        },
                    ),
                ),
                {"role": "assistant", "content": None},
                2,
                2,
            )
        )
    )

    async def aggregate_model(*, messages, tools, max_output_tokens):
        if tools and tools[0].name == "review_answer_evidence":
            return accepted_review_turn(messages)
        import json

        payload = json.loads(messages[1]["content"])
        policies = payload["published_output_policies"]
        assert {agent.prompt_sections["language_format"] for agent in agents}.issubset(policies)
        assert any("zh-CN" in item for item in policies)
        if tools:
            assert tools[0].name == "submit_reply_parts"
            return ToolTurn(
                None,
                (FunctionCall("p", "submit_reply_parts", {"texts": ["已查询订单和物流，请坐席复核。"]}),),
                {},
                2,
                2,
            )
        return ToolTurn(
            "已查询订单和物流，请坐席复核。",
            (),
            {"role": "assistant", "content": "已查询订单和物流，请坐席复核。"},
            2,
            2,
        )

    aggregator = SimpleNamespace(complete=AsyncMock(side_effect=aggregate_model))
    seen = []

    async def worker(selection):
        assert selection.question_language == "zh-CN"
        seen.append(selection.agent_id)
        facts = (
            {"query_order.status": "shipped"}
            if selection.agent_id == agents[0].id
            else {"query_logistics.tracking_status": "in_transit"}
        )
        return SpecialistResult(selection.agent_id, f"{selection.subquestion}已查询", verified_facts=facts)

    run = await execute_dynamic_run(
        question="订单和物流",
        snapshot=snapshot,
        router=router,
        aggregator=aggregator,
        worker=worker,
        deadline=time.monotonic() + 2,
        max_catalog_tokens=1000,
        progress=RunProgress(reply_plan=reply_plan),
    )
    assert set(seen) == {item.id for item in agents}
    assert run.suggestion.content == "已查询订单和物流，请坐席复核。"
    assert run.phase == "review_ready"

    async def timed_out_worker(selection):
        return SpecialistResult(selection.agent_id, None, reason_code="rag_retrieval_timeout")

    timed_out = await execute_dynamic_run(
        question="订单和物流",
        snapshot=snapshot,
        router=router,
        aggregator=aggregator,
        worker=timed_out_worker,
        deadline=time.monotonic() + 2,
        max_catalog_tokens=1000,
    )
    assert timed_out.reason_code == "rag_retrieval_timeout"
    assert "知识检索超时" in (timed_out.suggestion.content or "")
    assert aggregator.complete.await_count == 2


@pytest.mark.asyncio
async def test_question_route_excludes_event_and_fallback_agents() -> None:
    store, conversation, customer = (uuid.uuid4() for _ in range(3))
    base = PublishedAgent(
        id=uuid.uuid4(),
        store_id=store,
        config_version=1,
        name="售前",
        code="presales",
        description="售前商品",
        agent_type="service",
        model_provider="deepseek",
        model_name="deepseek-chat",
        prompt_sections=MappingProxyType({}),
        prompt_hash="hash",
        tool_names=(),
        file_ids=(),
        ready_for_v2=True,
    )
    agents = (
        base,
        replace(base, id=uuid.uuid4(), code="order", agent_type="operations"),
        replace(base, id=uuid.uuid4(), code="event", agent_type="logistics_event"),
        replace(base, id=uuid.uuid4(), code="fallback", agent_type="fallback"),
    )
    now = datetime.now(UTC)
    snapshot = RunSnapshot(store, conversation, customer, uuid.uuid4(), now, (), agents, (), 0, now, "hash")

    async def route_model(*, messages, tools, max_output_tokens):
        import json

        catalog = json.loads(messages[1]["content"])["candidates"]
        assert {item["type"] for item in catalog} == {"service", "operations"}
        return ToolTurn(None, (FunctionCall("r", "route_agents", {"selections": []}),), {}, 1, 1)

    run = await execute_dynamic_run(
        question="这个商品如何使用？",
        snapshot=snapshot,
        router=SimpleNamespace(complete=route_model),
        aggregator=SimpleNamespace(complete=AsyncMock()),
        worker=AsyncMock(),
        deadline=time.monotonic() + 2,
        max_catalog_tokens=3000,
    )
    assert run.reason_code == "no_matching_agent"
    assert run.route.examined_count == 2


@pytest.mark.asyncio
async def test_first_unresolved_english_question_uses_english_clarification() -> None:
    store, conversation, customer = (uuid.uuid4() for _ in range(3))
    now = datetime.now(UTC)
    snapshot = RunSnapshot(store, conversation, customer, uuid.uuid4(), now, (), (), (), 0, now, "hash")
    run = await execute_dynamic_run(
        question="Can you confirm my order?",
        snapshot=snapshot,
        router=SimpleNamespace(complete=AsyncMock()),
        aggregator=SimpleNamespace(complete=AsyncMock()),
        worker=AsyncMock(),
        deadline=time.monotonic() + 2,
        max_catalog_tokens=3000,
    )
    assert run.reason_code == "no_matching_agent"
    assert run.suggestion.content is not None and run.suggestion.content.startswith("I cannot")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "language,expected",
    [
        ("en", "We have received your question."),
        ("zh-CN", "我们已收到您的问题。"),
    ],
)
async def test_third_unresolved_question_calls_fallback_and_uses_fixed_buyer_language(language, expected) -> None:
    store, conversation, customer = (uuid.uuid4() for _ in range(3))
    fallback = PublishedAgent(
        id=uuid.uuid4(),
        store_id=store,
        config_version=1,
        name="无解兜底",
        code="fallback",
        description="第三轮无解时记录人工接管",
        agent_type="fallback",
        model_provider="deepseek",
        model_name="deepseek-chat",
        prompt_sections=MappingProxyType({}),
        prompt_hash="hash",
        tool_names=("create_handoff_request",),
        file_ids=(),
        ready_for_v2=True,
    )
    now = datetime.now(UTC)
    snapshot = RunSnapshot(store, conversation, customer, uuid.uuid4(), now, (), (fallback,), (), 0, now, "hash")

    worker = AsyncMock(
        return_value=SpecialistResult(
            fallback.id,
            "不应使用模型自由生成的文案",
            tool_events=(ToolEvent("call", "create_handoff_request", "succeeded"),),
        )
    )
    run = await execute_dynamic_run(
        question="Where is my parcel?" if language == "en" else "我的包裹在哪？",
        snapshot=snapshot,
        router=SimpleNamespace(complete=AsyncMock()),
        aggregator=SimpleNamespace(complete=AsyncMock()),
        worker=worker,
        deadline=time.monotonic() + 2,
        max_catalog_tokens=3000,
        progress=RunProgress(fallback_due=True),
    )
    assert run.reason_code == "fallback_third_round"
    assert run.suggestion.content is not None and run.suggestion.content.startswith(expected)
    assert "不应使用模型自由生成的文案" not in run.suggestion.content
    worker.assert_awaited_once()
