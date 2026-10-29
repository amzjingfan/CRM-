"""一次动态运行必须按路由、专家、汇总的同一快照与截止时间执行。"""

import time
import uuid
from datetime import UTC, datetime
from types import MappingProxyType, SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from agent._review_helpers import accepted_review_turn

from app.agents.management.repository import PublishedAgent
from app.agents.orchestration.coordinator import SpecialistResult
from app.agents.orchestration.service import execute_dynamic_run
from app.agents.providers.tool_calling import FunctionCall, ToolTurn
from app.agents.runtime.snapshot import RunSnapshot


@pytest.mark.asyncio
async def test_dynamic_run_routes_two_agents_and_returns_one_reviewed_suggestion() -> None:
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
                        {"selections": [{"agent_id": str(item.id), "subquestion": item.name} for item in agents]},
                    ),
                ),
                {"role": "assistant", "content": None},
                2,
                2,
            )
        )
    )

    async def aggregate_model(*, messages, tools, max_output_tokens):
        if tools:
            return accepted_review_turn(messages)
        import json

        payload = json.loads(messages[1]["content"])
        assert set(payload["published_output_policies"]) == {
            agent.prompt_sections["language_format"] for agent in agents
        }
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
