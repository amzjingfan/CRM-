"""验证 Agent 运行记录独立提交和失败终态持久化。"""

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.models import AgentRun
from app.agent.repository import AgentRunStart, AgentWorkflowRunCompletion, SqlAlchemyAgentRunRecorder
from app.agent.schemas import AgentAction, AgentRunStatus, ClassificationState, IntentName


@pytest.mark.asyncio
async def test_running_record_is_committed_before_external_call() -> None:
    """running 记录必须立即提交，后续模型超时不能将其一并回滚。"""
    session = Mock(spec=AsyncSession)
    session.commit = AsyncMock()
    recorder = SqlAlchemyAgentRunRecorder(session)
    values = AgentRunStart(
        store_id=uuid.uuid4(),
        conversation_id=uuid.uuid4(),
        trigger_message_id=uuid.uuid4(),
        provider_name="openai",
        model_name="test-model",
        prompt_version="intent-classifier-v1.0.0",
        input_summary="messages=1;chars=4;sha256=test",
        trace_id="trace-repository",
    )

    run_id = await recorder.start(values)

    session.add.assert_called_once()
    session.commit.assert_awaited_once()
    assert isinstance(run_id, uuid.UUID)


@pytest.mark.asyncio
async def test_failure_terminal_state_is_committed_without_raw_model_output() -> None:
    """失败记录只保存稳定错误码，不保存 SDK 异常或模型正文。"""
    run = AgentRun(
        id=uuid.uuid4(),
        store_id=uuid.uuid4(),
        conversation_id=uuid.uuid4(),
        trigger_message_id=uuid.uuid4(),
        model_provider="openai",
        model_name="primary-model",
        action=AgentAction.HUMAN_REVIEW.value,
        status=AgentRunStatus.RUNNING.value,
    )
    session = Mock(spec=AsyncSession)
    session.get = AsyncMock(return_value=run)
    session.commit = AsyncMock()
    recorder = SqlAlchemyAgentRunRecorder(session)

    await recorder.fail(
        run.id,
        AgentRunStatus.TIMEOUT,
        AgentAction.FAILED,
        "LLM_TIMEOUT",
        "anthropic",
        "fallback-model",
        15001,
    )

    assert run.status == AgentRunStatus.TIMEOUT.value
    assert run.action == AgentAction.FAILED.value
    assert run.error_code == "LLM_TIMEOUT"
    assert run.output_summary == "error_code=LLM_TIMEOUT"
    assert run.model_provider == "anthropic"
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_workflow_completion_records_scores_and_safe_trace_only() -> None:
    """完整工作流只保存节点、引用 ID 和统计，不保存回复或知识正文。"""
    run = AgentRun(
        id=uuid.uuid4(),
        store_id=uuid.uuid4(),
        conversation_id=uuid.uuid4(),
        model_provider="deepseek",
        model_name="intent-model",
        action=AgentAction.HUMAN_REVIEW.value,
        status=AgentRunStatus.RUNNING.value,
    )
    session = Mock(spec=AsyncSession)
    session.get = AsyncMock(return_value=run)
    session.commit = AsyncMock()
    recorder = SqlAlchemyAgentRunRecorder(session)
    citation_id = uuid.uuid4()

    await recorder.complete_workflow(
        run.id,
        AgentWorkflowRunCompletion(
            provider_name="deepseek",
            model_name="answer-model",
            prompt_version="faq-agent-workflow-v1.0.0",
            intent=IntentName.RETURN_POLICY,
            classification_state=ClassificationState.CLASSIFIED,
            intent_confidence=0.9,
            retrieval_score=0.85,
            final_confidence=0.8,
            action=AgentAction.AUTO_REPLY,
            input_tokens=100,
            output_tokens=20,
            latency_ms=300,
            state_path=["RECEIVED", "KNOWLEDGE_RETRIEVED", "AUTO_REPLY_READY"],
            citation_ids=[citation_id],
            required_tools=[],
            prompt_versions={"answer": "faq-answer-v1.0.0"},
        ),
    )

    assert run.retrieval_score == Decimal("0.8500")
    assert run.final_confidence == Decimal("0.8000")
    assert str(citation_id) in (run.output_summary or "")
    assert "签收后" not in (run.output_summary or "")
    assert run.status == AgentRunStatus.SUCCEEDED.value
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_workflow_completion_records_only_low_sensitive_tool_trace() -> None:
    """工具追踪只保存调用元数据，不能混入地址、消息或工具返回正文。"""
    run = AgentRun(
        id=uuid.uuid4(),
        store_id=uuid.uuid4(),
        conversation_id=uuid.uuid4(),
        model_provider="deepseek",
        model_name="intent-model",
        action=AgentAction.HUMAN_REVIEW.value,
        status=AgentRunStatus.RUNNING.value,
    )
    session = Mock(spec=AsyncSession)
    session.get = AsyncMock(return_value=run)
    session.commit = AsyncMock()
    recorder = SqlAlchemyAgentRunRecorder(session)
    tool_call_id = uuid.uuid4()

    await recorder.complete_workflow(
        run.id,
        AgentWorkflowRunCompletion(
            provider_name="deepseek",
            model_name="tool-answer-model",
            prompt_version="faq-agent-workflow-v1.1.0",
            intent=IntentName.LOGISTICS_QUERY,
            classification_state=ClassificationState.CLASSIFIED,
            intent_confidence=0.9,
            retrieval_score=0.0,
            final_confidence=0.0,
            action=AgentAction.TRANSFER_HUMAN,
            input_tokens=80,
            output_tokens=10,
            latency_ms=200,
            state_path=["RECEIVED", "TOOL_EXECUTED", "TRANSFERRED"],
            citation_ids=[],
            required_tools=["query_logistics", "transfer_to_human"],
            prompt_versions={"tool_answer": "tool-answer-v1.0.0"},
            tool_call_summaries=[
                f"{tool_call_id}:query_logistics:timeout:TOOL_TIMEOUT",
            ],
            business_claim_summaries=[
                f"logistics:report_status:tool_call:{tool_call_id}",
            ],
        ),
    )

    summary = run.output_summary or ""
    assert str(tool_call_id) in summary
    assert "query_logistics:timeout:TOOL_TIMEOUT" in summary
    assert f"logistics:report_status:tool_call:{tool_call_id}" in summary
    assert "上海市浦东新区" not in summary
    assert "ORDER-2026-001" not in summary
    assert "TRACK-SECRET-001" not in summary
    assert "客户消息正文" not in summary
    session.commit.assert_awaited_once()
