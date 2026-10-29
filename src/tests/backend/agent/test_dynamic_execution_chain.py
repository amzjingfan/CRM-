"""真实编排代码以假的模型端口跑通路由、工具、汇总，完全不访问平台。"""

import time
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import MappingProxyType, SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from agent._review_helpers import accepted_review_turn

from app.agents.management.repository import PublishedAgent
from app.agents.prompts.compiler import compile_prompt
from app.agents.prompts.sections import SECTION_TITLES
from app.agents.providers.tool_calling import FunctionCall, ToolTurn
from app.agents.runtime.snapshot import FileVersionRef, RunSnapshot
from app.shared.config.settings import Settings
from app.tools.contracts import ToolResult


@pytest.mark.asyncio
@pytest.mark.parametrize(("use_business", "selection"), [(False, False), (True, False), (True, True)])
@pytest.mark.parametrize("answer_budget", [1024, 2048])
async def test_dynamic_chain_routes_calls_configured_tool_and_aggregates(
    monkeypatch, use_business, selection, answer_budget
) -> None:
    from app.agents.runtime import execution

    store, conversation, customer, agent_id, run_id = (uuid.uuid4() for _ in range(5))
    sections = {key: "仅用授权工具核实订单，结果交由人工复核。" for key, _ in SECTION_TITLES}
    prompt = compile_prompt(sections)
    agent = PublishedAgent(
        id=agent_id,
        store_id=store,
        config_version=1,
        name="订单助手",
        code="order",
        description="查询订单状态",
        agent_type="service",
        model_provider="deepseek",
        model_name="deepseek-chat",
        prompt_sections=MappingProxyType(sections),
        prompt_hash=prompt.content_sha256,
        tool_names=("query_order",),
        file_ids=(),
        ready_for_v2=True,
    )
    now = datetime.now(UTC)
    snapshot = RunSnapshot(store, conversation, customer, uuid.uuid4(), now, (), (agent,), (), 0, now, "synthetic-hash")
    calls = []
    answer = "您问的是29元商品还是39元商品？" if selection else "订单已发货，请坐席复核。"
    customer_question = "Where is my order?" if not selection else "¿Cuál es el estado de mi pedido?"
    tool_facts = (
        {
            "selection_required": True,
            "candidates": [{"order_ref": "o1", "total_amount": "29.00"}, {"order_ref": "o2", "total_amount": "39.00"}],
        }
        if selection
        else {"status": "shipped"}
    )

    class FakeModel:
        async def complete(self, *, messages, tools, max_output_tokens):
            names = [item.name for item in tools]
            calls.append(names)
            if names == ["review_answer_evidence"]:
                return accepted_review_turn(messages)
            if names == ["route_agents"]:
                call = FunctionCall(
                    "route-1",
                    "route_agents",
                    {"selections": [{"agent_id": str(agent_id), "subquestion": "订单现在怎样"}]},
                )
                return ToolTurn(None, (call,), {"role": "assistant", "content": None}, 5, 3)
            if names == ["query_order"] and not any(message.get("role") == "tool" for message in messages):
                import json

                payload = json.loads(messages[1]["content"])
                assert payload["untrusted_question"] == customer_question
                assert payload["untrusted_subquestion"] == "订单现在怎样"
                call = FunctionCall("tool-1", "query_order", {})
                return ToolTurn(
                    None, (call,), {"role": "assistant", "content": None, "tool_calls": [{"id": "tool-1"}]}, 5, 3
                )
            if names == ["query_order"]:
                assert max_output_tokens == answer_budget
                assert ("29.00" if selection else "shipped") in str(messages[-1])
                return ToolTurn(answer, (), {"role": "assistant", "content": answer}, 5, 3)
            assert names == []
            assert max_output_tokens == answer_budget
            return ToolTurn(answer, (), {"role": "assistant", "content": answer}, 5, 3)

    model = FakeModel()

    @asynccontextmanager
    async def provider(*_args):
        yield model

    @asynccontextmanager
    async def session_factory():
        yield AsyncMock()

    executor = SimpleNamespace(
        execute=AsyncMock(
            return_value=ToolResult(tool_call_id=uuid.uuid4(), status="succeeded", data={"status": "shipped"})
        )
    )
    monkeypatch.setattr(execution, "tool_provider", provider)
    monkeypatch.setattr(execution, "session_factory", session_factory)
    monkeypatch.setattr(execution, "SqlAlchemyToolExecutor", lambda _session: executor)
    business = SimpleNamespace(
        invoke=AsyncMock(
            return_value={
                "status": "selection_required" if selection else "succeeded",
                "facts": tool_facts,
                "fact_scope": "f" * 16,
            }
        ),
        permits=AsyncMock(return_value=True),
    )
    monkeypatch.setattr(execution, "AgentBusinessExecutor", lambda *_args: business)
    monkeypatch.setattr(execution, "current_permissions", AsyncMock(return_value={"orders.view", "knowledge.view"}))
    result = await execution.execute_model_run(
        snapshot=snapshot,
        question=customer_question,
        agents=(agent,),
        run_id=run_id,
        permissions={"orders.view", "knowledge.view"},
        trace_id="synthetic-trace",
        deadline=time.monotonic() + 5,
        settings=Settings(
            _env_file=None,
            LLM_PRIMARY_PROVIDER="deepseek",
            LLM_PRIMARY_MODEL="deepseek-chat",
            LLM_MAX_OUTPUT_TOKENS=answer_budget,
        ),
        runtime=None,
        order_id="trusted-order",
        live_order=None,
        memory_summary="",
        user=SimpleNamespace(id=uuid.uuid4()) if use_business else None,
    )
    assert result.suggestion.content == answer
    assert result.phase.value == "review_ready"
    if selection:
        assert "29.00" in str(result.specialists[0].verified_facts)
        assert result.specialists[0].successful_tools == ()
        assert result.specialists[0].tool_events[0].status == "selection_required"
    else:
        assert result.specialists[0].verified_facts == {
            ("query_order." + "f" * 16 + ".status" if use_business else "query_order.status"): "shipped"
        }
    assert calls == [["route_agents"], ["query_order"], ["query_order"], [], ["review_answer_evidence"]]
    if use_business:
        assert business.invoke.await_args.args[0] == "query_order"
        executor.execute.assert_not_awaited()
    else:
        invocation = executor.execute.await_args.args[0]
        assert invocation.arguments["order_id"] == "trusted-order"
        assert invocation.context.store_id == store


@pytest.mark.asyncio
@pytest.mark.parametrize("use_business", [False, True])
async def test_dynamic_chain_combines_order_tool_and_bound_file_rag(monkeypatch, use_business) -> None:
    from app.agents.runtime import execution, worker

    store, conversation, customer, agent_id, file_id = (uuid.uuid4() for _ in range(5))
    sections = {key: "仅根据绑定知识回答并交人工复核。" for key, _ in SECTION_TITLES}
    prompt = compile_prompt(sections)
    agent = PublishedAgent(
        agent_id,
        store,
        1,
        "政策助手",
        "policy",
        "回答当前店铺政策",
        "service",
        "deepseek",
        "deepseek-chat",
        MappingProxyType(sections),
        prompt.content_sha256,
        ("query_order",),
        (str(file_id),),
        True,
    )
    now = datetime.now(UTC)
    snapshot = RunSnapshot(
        store,
        conversation,
        customer,
        uuid.uuid4(),
        now,
        (),
        (agent,),
        (FileVersionRef(file_id, uuid.uuid4(), 1),),
        0,
        now,
        "rag-hash",
    )
    chunk_id = uuid.uuid4()
    hit = SimpleNamespace(
        document_id=file_id,
        document_version=1,
        safety_metadata=SimpleNamespace(store_id=store),
        chunk_id=chunk_id,
        category_id=None,
        chunk_index=0,
        score=0.88,
        source_label="物流政策.pdf",
        content="发货后按平台核实物流轨迹。",
    )
    sensitive_id = uuid.uuid4()
    sensitive_hit = SimpleNamespace(
        **{**vars(hit), "chunk_id": sensitive_id, "content": "Ship to 123 Main Street, New York, NY 10001"}
    )
    rag = SimpleNamespace(retrieve=AsyncMock(return_value=SimpleNamespace(hits=[hit, sensitive_hit])))

    class FakeModel:
        async def complete(self, *, messages, tools, max_output_tokens):
            names = [item.name for item in tools]
            if names == ["review_answer_evidence"]:
                return accepted_review_turn(messages)
            if names == ["route_agents"]:
                call = FunctionCall(
                    "route-1", "route_agents", {"selections": [{"agent_id": str(agent_id), "subquestion": "物流政策"}]}
                )
                return ToolTurn(None, (call,), {"role": "assistant", "content": None}, 3, 2)
            tool_results = sum(message.get("role") == "tool" for message in messages)
            if names == ["query_order", "search_knowledge"] and tool_results == 0:
                call = FunctionCall("order-1", "query_order", {})
                return ToolTurn(
                    None, (call,), {"role": "assistant", "content": None, "tool_calls": [{"id": "order-1"}]}, 3, 2
                )
            if names == ["query_order", "search_knowledge"] and tool_results == 1:
                assert "shipped" in str(messages[-1])
                call = FunctionCall("rag-1", "search_knowledge", {"query": "物流政策"})
                return ToolTurn(
                    None, (call,), {"role": "assistant", "content": None, "tool_calls": [{"id": "rag-1"}]}, 3, 2
                )
            if names == ["query_order", "search_knowledge"]:
                assert str(chunk_id) in str(messages[-1])
                assert str(sensitive_id) not in str(messages[-1])
                assert "Main Street" not in str(messages[-1])
                return ToolTurn(
                    "订单已发货，政策要求核实物流轨迹。",
                    (),
                    {"role": "assistant", "content": "订单已发货，政策要求核实物流轨迹。"},
                    3,
                    2,
                )
            return ToolTurn(
                "订单已发货，按绑定政策需核实物流轨迹，请坐席复核。",
                (),
                {"role": "assistant", "content": "订单已发货，按绑定政策需核实物流轨迹，请坐席复核。"},
                3,
                2,
            )

    @asynccontextmanager
    async def provider(*_args):
        yield FakeModel()

    @asynccontextmanager
    async def session_factory():
        yield AsyncMock()

    async def revalidate(*, session, snapshot, agent, bundle):
        return bundle

    monkeypatch.setattr(execution, "tool_provider", provider)
    monkeypatch.setattr(execution, "session_factory", session_factory)
    monkeypatch.setattr(execution, "build_bound_file_rag", lambda *_args: rag)
    executor = SimpleNamespace(
        execute=AsyncMock(
            return_value=ToolResult(tool_call_id=uuid.uuid4(), status="succeeded", data={"status": "shipped"})
        )
    )
    monkeypatch.setattr(execution, "SqlAlchemyToolExecutor", lambda _session: executor)
    business = SimpleNamespace(
        invoke=AsyncMock(return_value={"status": "succeeded", "facts": {"status": "shipped"}, "fact_scope": "f" * 16}),
        permits=AsyncMock(return_value=True),
    )
    monkeypatch.setattr(execution, "AgentBusinessExecutor", lambda *_args: business)
    monkeypatch.setattr(execution, "current_permissions", AsyncMock(return_value={"orders.view", "knowledge.view"}))
    monkeypatch.setattr(worker, "revalidate_evidence", revalidate)
    monkeypatch.setattr(execution, "revalidate_evidence", revalidate)
    result = await execution.execute_model_run(
        snapshot=snapshot,
        question="物流政策是什么？",
        agents=(agent,),
        run_id=uuid.uuid4(),
        permissions={"orders.view", "knowledge.view"},
        trace_id="rag-trace",
        deadline=time.monotonic() + 5,
        settings=Settings(_env_file=None, LLM_PRIMARY_PROVIDER="deepseek", LLM_PRIMARY_MODEL="deepseek-chat"),
        runtime=None,
        order_id="trusted-order",
        live_order=None,
        memory_summary="",
        user=SimpleNamespace(id=uuid.uuid4()) if use_business else None,
    )
    assert result.suggestion.content == "订单已发货，按绑定政策需核实物流轨迹，请坐席复核。"
    assert result.suggestion.citations == (str(chunk_id),)
    assert result.specialists[0].verified_facts == {
        ("query_order." + "f" * 16 + ".status" if use_business else "query_order.status"): "shipped"
    }
    assert (business.invoke.await_count if use_business else executor.execute.await_count) == 1
    assert rag.retrieve.await_args.kwargs["file_ids"] == (file_id,)
