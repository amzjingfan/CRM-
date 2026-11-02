"""动态路由必须覆盖全部候选，并拒绝模型越权选择。"""

import json
import time
import uuid
from dataclasses import replace
from types import MappingProxyType

import pytest

from app.agents.management.repository import PublishedAgent
from app.agents.orchestration.router import RouteDecisionError, route_agents
from app.agents.providers.tool_calling import FunctionCall, ToolTurn


@pytest.mark.asyncio
async def test_router_receives_published_service_scope_and_frozen_session_context() -> None:
    agent = replace(_agent(uuid.uuid4(), ""), prompt_sections=MappingProxyType({"service_scope": "仅处理物流异常"}))

    class Model:
        async def complete(self, *, messages, tools, max_output_tokens):
            payload = json.loads(messages[-1]["content"])
            assert payload["candidates"][0]["service_scope"] == "仅处理物流异常"
            assert "此前在问包裹" in payload["untrusted_context"]
            return ToolTurn(None, (FunctionCall("route", "route_agents", {"selections": []}),), {}, 1, 1)

    await route_agents(
        question="那这个呢",
        agents=(agent,),
        provider=Model(),
        deadline=time.monotonic() + 2,
        max_catalog_tokens=1024,
        routing_context="此前在问包裹",
    )


def _agent(store_id: uuid.UUID, description: str) -> PublishedAgent:
    return PublishedAgent(
        id=uuid.uuid4(),
        store_id=store_id,
        config_version=1,
        name=description,
        code=str(uuid.uuid4()),
        description=description,
        agent_type="service",
        model_provider="deepseek",
        model_name="deepseek-chat",
        prompt_sections=MappingProxyType({}),
        prompt_hash="hash",
        tool_names=(),
        file_ids=(),
        ready_for_v2=True,
    )


class RouterModel:
    def __init__(self, selected: list[uuid.UUID], *, include_unlisted: bool = False) -> None:
        self.selected = selected
        self.include_unlisted = include_unlisted
        self.seen: list[list[str]] = []

    async def complete(self, *, messages, tools, max_output_tokens):
        assert len(tools) == 1 and tools[0].name == "route_agents"
        catalog = messages[-1]["content"]
        self.seen.append([str(item) for item in self.selected if self.include_unlisted or str(item) in catalog])
        call = FunctionCall(
            id=str(uuid.uuid4()),
            name="route_agents",
            arguments={"selections": [{"agent_id": item, "subquestion": "查询订单与物流"} for item in self.seen[-1]]},
        )
        return ToolTurn(None, (call,), {"role": "assistant", "content": None}, 10, 5)


@pytest.mark.asyncio
async def test_router_native_schema_limits_ids_to_the_current_capacity_batch():
    from langchain_core.utils.function_calling import convert_to_openai_tool

    agents = tuple(_agent(uuid.uuid4(), "商品") for _ in range(1))
    seen = []

    class Model:
        async def complete(self, *, messages, tools, max_output_tokens):
            catalog = json.loads(messages[-1]["content"])["candidates"]
            schema = convert_to_openai_tool(tools[0])["function"]["parameters"]
            ids = schema["properties"]["selections"]["items"]["properties"]["agent_id"]["enum"]
            assert ids == [item["agent_id"] for item in catalog]
            assert not {item["name"] for item in catalog} & set(ids)
            seen.extend(ids)
            return ToolTurn(
                None,
                (
                    FunctionCall(
                        "r",
                        "route_agents",
                        {"selections": [{"agent_id": ids[0], "subquestion": "商品规格"}], "question_language": "zh-CN"},
                    ),
                ),
                {},
                1,
                1,
            )

    plan = await route_agents(
        question="这个 English Product 的规格是什么？",
        agents=agents,
        provider=Model(),
        deadline=time.monotonic() + 3,
        max_catalog_tokens=1024,
    )
    assert {x.agent_id for x in plan.selections} == {x.id for x in agents}
    assert seen == [str(x.id) for x in agents]


@pytest.mark.asyncio
async def test_all_enabled_agents_are_covered_across_capacity_batches() -> None:
    store = uuid.uuid4()
    agents = tuple(_agent(store, f"专长 {i}" * 10) for i in range(7))
    model = RouterModel([item.id for item in agents])
    plan = await route_agents(
        question="我的订单物流在哪里",
        agents=agents,
        provider=model,
        deadline=time.monotonic() + 5,
        max_catalog_tokens=250,
    )
    assert {item.agent_id for item in plan.selections} == {item.id for item in agents}
    assert len(model.seen) > 1
    assert plan.examined_count == len(agents)


@pytest.mark.asyncio
async def test_router_rejects_unlisted_or_duplicate_agent() -> None:
    store = uuid.uuid4()
    agent = _agent(store, "订单")
    model = RouterModel([uuid.uuid4()], include_unlisted=True)
    with pytest.raises(RouteDecisionError, match="invalid_agent_id"):
        await route_agents(
            question="订单",
            agents=(agent,),
            provider=model,
            deadline=time.monotonic() + 5,
            max_catalog_tokens=1000,
        )


@pytest.mark.asyncio
async def test_router_rejects_cross_store_candidates_before_model_call() -> None:
    first = _agent(uuid.uuid4(), "订单")
    second = _agent(uuid.uuid4(), "物流")
    model = RouterModel([])
    with pytest.raises(RouteDecisionError, match="cross_store"):
        await route_agents(
            question="订单",
            agents=(first, second),
            provider=model,
            deadline=time.monotonic() + 5,
            max_catalog_tokens=1000,
        )
    assert model.seen == []


@pytest.mark.asyncio
async def test_model_question_language_is_frozen_independent_of_history_and_subquestion():
    agent = _agent(uuid.uuid4(), "订单物流")

    class Model:
        async def complete(self, *, messages, tools, max_output_tokens):
            assert json.loads(messages[-1]["content"])["question"] == "我的包裹到哪了？"
            return ToolTurn(
                None,
                (
                    FunctionCall(
                        "r",
                        "route_agents",
                        {
                            "question_language": "zh-CN",
                            "selections": [{"agent_id": str(agent.id), "subquestion": "Where is the parcel?"}],
                        },
                    ),
                ),
                {},
                1,
                1,
            )

    plan = await route_agents(
        question="我的包裹到哪了？",
        agents=(agent,),
        provider=Model(),
        deadline=time.monotonic() + 2,
        max_catalog_tokens=1024,
        routing_context="inbound: Where is my order?",
    )
    assert plan.question_language == "zh-CN"
    assert plan.selections[0].question_language == "zh-CN"
