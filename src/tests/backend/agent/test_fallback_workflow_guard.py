"""只有兜底 Agent 的已绑定内部能力进入工作流完成检查。"""

import time
import uuid
from datetime import UTC, datetime
from types import MappingProxyType, SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.agents.management.repository import PublishedAgent
from app.agents.orchestration.router import RoutedAgent
from app.agents.prompts.compiler import compile_prompt
from app.agents.prompts.sections import SECTION_TITLES
from app.agents.runtime.context import ModelLimits
from app.agents.runtime.snapshot import RunSnapshot
from app.agents.tools.catalog import AgentToolContext
from app.agents.tools.loop import ToolLoopResult


@pytest.mark.asyncio
@pytest.mark.parametrize("agent_type", ["service", "fallback"])
@pytest.mark.parametrize(
    "bound",
    [
        (),
        ("query_conversation_messages",),
        ("query_conversation_messages", "create_handoff_request", "add_internal_note", "query_order"),
    ],
)
async def test_specialist_requires_only_bound_fallback_workflow_tools(monkeypatch, agent_type, bound):
    from app.agents.runtime import worker

    store, conversation, customer, agent_id = (uuid.uuid4() for _ in range(4))
    sections = {key: "只按当前授权和证据处理。" for key, _ in SECTION_TITLES}
    prompt = compile_prompt(sections)
    agent = PublishedAgent(
        id=agent_id,
        store_id=store,
        config_version=1,
        name="Workflow",
        code="workflow",
        description="内部接管",
        agent_type=agent_type,
        model_provider="deepseek",
        model_name="deepseek-chat",
        prompt_sections=MappingProxyType(sections),
        prompt_hash=prompt.content_sha256,
        tool_names=bound,
        file_ids=(),
        ready_for_v2=True,
    )
    now = datetime.now(UTC)
    snapshot = RunSnapshot(
        store_id=store,
        conversation_id=conversation,
        customer_id=customer,
        trigger_message_id=uuid.uuid4(),
        trigger_created_at=now,
        message_ids=(),
        published_agents=(agent,),
        file_versions=(),
        memory_revision=0,
        frozen_at=now,
        snapshot_hash="workflow",
    )
    loop = AsyncMock(return_value=ToolLoopResult("A reviewed candidate.", None, (), 2, 1))
    monkeypatch.setattr(worker, "run_tool_loop", loop)
    deadline = time.monotonic() + 2
    result = await worker.run_specialist(
        snapshot=snapshot,
        agent=agent,
        selection=RoutedAgent(agent_id, "Please help", "en"),
        provider=SimpleNamespace(),
        executor=SimpleNamespace(execute=AsyncMock()),
        rag_service=None,
        session=AsyncMock(),
        tool_context=AgentToolContext(
            store, uuid.uuid4(), None, customer, frozenset({"workspace.reply", "workspace.view"}), "workflow"
        ),
        deadline=deadline,
        model_limits=ModelLimits(8000, 256, 256),
        max_output_tokens=256,
    )
    expected = (
        frozenset(bound) & {"query_conversation_messages", "create_handoff_request", "add_internal_note"}
        if agent_type == "fallback"
        else frozenset()
    )
    assert loop.await_args.kwargs["required_tools"] == expected
    assert loop.await_args.kwargs["deadline"] == deadline
    assert loop.await_args.kwargs["max_output_tokens"] == 256
    assert result.answer == "A reviewed candidate."
