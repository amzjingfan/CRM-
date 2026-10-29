"""知识工具审计与真正送入模型的文件证据保持一致。"""

import json
import time
import uuid
from datetime import UTC, datetime
from types import MappingProxyType, SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.agents.management.repository import PublishedAgent
from app.agents.orchestration.aggregator import ReviewedSuggestion
from app.agents.orchestration.coordinator import SpecialistResult
from app.agents.orchestration.router import RoutedAgent, RoutePlan
from app.agents.orchestration.service import DynamicRunResult
from app.agents.prompts.compiler import compile_prompt
from app.agents.prompts.sections import SECTION_TITLES
from app.agents.providers.tool_calling import FunctionCall, ToolTurn
from app.agents.runtime.context import ModelLimits
from app.agents.runtime.execution import persist_dynamic_result
from app.agents.runtime.snapshot import FileVersionRef, RunSnapshot
from app.agents.runtime.state import RunPhase
from app.agents.runtime.worker import run_specialist
from app.agents.tools.catalog import AgentToolContext
from app.agents.tools.loop import ToolEvent


@pytest.fixture
def bound_scope():
    store, conversation, customer, agent_id, file_id = (uuid.uuid4() for _ in range(5))
    sections = {key: "仅根据绑定知识回答并交人工复核。" for key, _ in SECTION_TITLES}
    agent = PublishedAgent(
        agent_id,
        store,
        1,
        "护理助手",
        "care",
        "回答护理政策",
        "service",
        "deepseek",
        "deepseek-chat",
        MappingProxyType(sections),
        compile_prompt(sections).content_sha256,
        (),
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
        "rag-budget-snapshot",
    )
    return agent, snapshot, file_id


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "contents,retained_count,expected_status",
    [
        (["Use a dry cloth."], 1, "retrieved"),
        (['Use a "dry" cloth. ' * 350] * 3, 2, "retrieved"),
        (["Dry cloth. " * 1450], 0, "tool_result_too_large"),
    ],
    ids=["ordinary", "trim-whole-tail-chunks", "single-chunk-too-large"],
)
async def test_rag_cites_only_whole_chunks_delivered_within_tool_json_budget(
    bound_scope, contents, retained_count, expected_status
) -> None:
    agent, snapshot, file_id = bound_scope
    hits = [
        SimpleNamespace(
            document_id=file_id,
            document_version=1,
            safety_metadata=SimpleNamespace(store_id=snapshot.store_id),
            chunk_id=uuid.uuid4(),
            category_id=None,
            chunk_index=index,
            score=0.88,
            source_label="synthetic-care.md",
            content=content,
        )
        for index, content in enumerate(contents)
    ]
    provider = SimpleNamespace(
        complete=AsyncMock(
            side_effect=[
                ToolTurn(
                    None,
                    (FunctionCall("rag-1", "search_knowledge", {"query": "护理政策"}),),
                    {"role": "assistant", "content": None, "tool_calls": [{"id": "rag-1"}]},
                    3,
                    2,
                ),
                ToolTurn("请按护理说明处理。", (), {"role": "assistant", "content": "请按护理说明处理。"}, 3, 2),
            ]
        )
    )
    session = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(all=lambda: [(file_id, 1)])))
    result = await run_specialist(
        snapshot=snapshot,
        agent=agent,
        selection=RoutedAgent(agent.id, "护理政策是什么"),
        provider=provider,
        executor=SimpleNamespace(execute=AsyncMock()),
        rag_service=SimpleNamespace(retrieve=AsyncMock(return_value=SimpleNamespace(hits=hits))),
        session=session,
        tool_context=AgentToolContext(
            snapshot.store_id, uuid.uuid4(), None, snapshot.customer_id, frozenset({"knowledge.view"}), "rag-trace"
        ),
        deadline=time.monotonic() + 5,
        model_limits=ModelLimits(8192, 1024, 256),
    )

    sent_result = provider.complete.await_args_list[1].kwargs["messages"][-1]["content"]
    projected = json.loads(sent_result)
    retained_hits = hits[:retained_count]
    assert len(sent_result) <= 16_000
    assert projected["status"] == expected_status
    assert [item["content"] for item in projected.get("hits", [])] == [hit.content.strip() for hit in retained_hits]
    assert result.tool_events == (ToolEvent("rag-1", "search_knowledge", expected_status),)
    assert result.citations == tuple(str(hit.chunk_id) for hit in retained_hits)
    assert [citation.chunk_id for citation in result.citation_details] == [hit.chunk_id for hit in retained_hits]
    assert result.knowledge_hits == tuple(retained_hits)
    assert result.grounding_evidence == {str(hit.chunk_id): hit.content.strip() for hit in retained_hits}
    for hit in hits[retained_count:]:
        assert str(hit.chunk_id) not in sent_result


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "tool_name,semantic_status,audit_status",
    [
        ("search_knowledge", "retrieved", "succeeded"),
        ("search_knowledge", "no_hits", "succeeded"),
        ("search_knowledge", "tool_failed", "failed"),
        ("search_knowledge", "tool_result_too_large", "failed"),
        ("search_knowledge", "permission_denied", "failed"),
        ("query_order", "succeeded", "succeeded"),
        ("query_order", "retrieved", "failed"),
        ("query_order", "tool_failed", "failed"),
        ("query_order", "timeout", "timeout"),
        ("query_order", "unknown", "unknown"),
    ],
)
async def test_dynamic_tool_audit_maps_completed_knowledge_query_without_changing_business_statuses(
    bound_scope, tool_name, semantic_status, audit_status
) -> None:
    agent, snapshot, _file_id = bound_scope
    specialist = SpecialistResult(agent.id, "已查询。", tool_events=(ToolEvent("call-1", tool_name, semantic_status),))
    result = DynamicRunResult(
        RunPhase.REVIEW_READY,
        RoutePlan((RoutedAgent(agent.id, "护理政策"),), 1, 2, 1),
        (specialist,),
        ReviewedSuggestion("已查询。", "human_review", None, (agent.id,), ()),
        None,
    )
    session = SimpleNamespace(add=Mock(), flush=AsyncMock(), execute=AsyncMock(), commit=AsyncMock())
    await persist_dynamic_result(
        session,
        run=SimpleNamespace(id=uuid.uuid4(), trace_id="audit-trace"),
        result=result,
        snapshot=snapshot,
        agents=(agent,),
        mode="debug",
        elapsed_ms=10,
    )

    values = session.execute.await_args.args[0].compile().params
    assert values["tool_name"] == tool_name
    assert values["status"] == audit_status
    assert values["output_summary"]["succeeded"] is (audit_status == "succeeded")
    assert values["error_code"] == (None if audit_status == "succeeded" else "DYNAMIC_TOOL_" + audit_status.upper())
    if tool_name == "search_knowledge" and semantic_status in {"retrieved", "no_hits"}:
        assert values["output_summary"]["result_status"] == semantic_status
    session.commit.assert_awaited_once()
