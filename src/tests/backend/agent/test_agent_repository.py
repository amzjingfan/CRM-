"""验证 Agent 运行记录独立提交和失败终态持久化。"""

import uuid
from dataclasses import replace
from decimal import Decimal
from typing import cast
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.core.errors import LLMFailureStage, LLMOutputFailureKind, LLMOutputSchemaIssue
from app.agents.core.repository import (
    AgentDecisionReason,
    AgentRunStart,
    AgentWorkflowRunCompletion,
    SqlAlchemyAgentRunRecorder,
)
from app.agents.core.schemas import AgentAction, AgentRunStatus, ClassificationState, IntentName
from app.agents.runtime.models import AgentRun


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
async def test_invalid_model_output_records_only_fixed_failure_stage_and_kind() -> None:
    """G5 故障摘要只接受受控枚举，不回写任何模型正文或异常。"""
    run = AgentRun(
        id=uuid.uuid4(),
        store_id=uuid.uuid4(),
        conversation_id=uuid.uuid4(),
        model_provider="deepseek",
        model_name="test-model",
        action=AgentAction.HUMAN_REVIEW.value,
        status=AgentRunStatus.RUNNING.value,
    )
    session = Mock(spec=AsyncSession)
    session.get = AsyncMock(return_value=run)
    session.commit = AsyncMock()
    recorder = SqlAlchemyAgentRunRecorder(session)

    await recorder.fail(
        run.id,
        AgentRunStatus.FAILED,
        AgentAction.FAILED,
        "LLM_OUTPUT_INVALID",
        "deepseek",
        "test-model",
        42,
        failure_stage=LLMFailureStage.FAQ_DRAFT,
        output_failure_kind="invalid_schema",
    )

    assert (
        run.output_summary == "error_code=LLM_OUTPUT_INVALID;failure_stage=faq_draft;output_failure_kind=invalid_schema"
    )
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_schema_failure_summary_limits_and_validates_issue_pairs() -> None:
    """仅 Schema 失败可保存最多八组已列举的字段路径和错误类型。"""
    run = AgentRun(
        id=uuid.uuid4(),
        store_id=uuid.uuid4(),
        conversation_id=uuid.uuid4(),
        model_provider="deepseek",
        model_name="test-model",
        action=AgentAction.HUMAN_REVIEW.value,
        status=AgentRunStatus.RUNNING.value,
    )
    session = Mock(spec=AsyncSession)
    session.get = AsyncMock(return_value=run)
    session.commit = AsyncMock()
    recorder = SqlAlchemyAgentRunRecorder(session)
    valid: LLMOutputSchemaIssue = ("content", "missing")
    unsafe = cast(LLMOutputSchemaIssue, ("private model text", "raw exception"))
    issues = (valid, unsafe, *(("reason_code", "literal_error"),) * 10)

    await recorder.fail(
        run.id,
        AgentRunStatus.FAILED,
        AgentAction.FAILED,
        "LLM_OUTPUT_INVALID",
        "deepseek",
        "test-model",
        42,
        output_failure_kind="invalid_schema",
        output_schema_issues=issues,
    )

    assert run.output_summary == (
        "error_code=LLM_OUTPUT_INVALID;output_failure_kind=invalid_schema;"
        "output_schema_issues=content:missing,reason_code:literal_error"
    )
    assert "private model text" not in run.output_summary

    await recorder.fail(
        run.id,
        AgentRunStatus.FAILED,
        AgentAction.FAILED,
        "LLM_OUTPUT_INVALID",
        "deepseek",
        "test-model",
        42,
        output_failure_kind="invalid_json",
        output_schema_issues=(valid,),
    )
    assert run.output_summary == "error_code=LLM_OUTPUT_INVALID;output_failure_kind=invalid_json"


@pytest.mark.asyncio
async def test_schema_failure_summary_persists_only_fixed_claim_invariant_code() -> None:
    """声明语义诊断可定位不变量，但不能将模型提供的错误文字写入摘要。"""
    run = AgentRun(
        id=uuid.uuid4(),
        store_id=uuid.uuid4(),
        conversation_id=uuid.uuid4(),
        model_provider="deepseek",
        model_name="test-model",
        action=AgentAction.HUMAN_REVIEW.value,
        status=AgentRunStatus.RUNNING.value,
    )
    session = Mock(spec=AsyncSession)
    session.get = AsyncMock(return_value=run)
    session.commit = AsyncMock()

    await SqlAlchemyAgentRunRecorder(session).fail(
        run.id,
        AgentRunStatus.FAILED,
        AgentAction.FAILED,
        "LLM_OUTPUT_INVALID",
        "deepseek",
        "test-model",
        42,
        failure_stage=LLMFailureStage.FAQ_DRAFT,
        output_failure_kind="invalid_schema",
        output_schema_issues=(
            ("business_claims", "claim_scope_duplicate"),
            cast(LLMOutputSchemaIssue, ("business_claims", "private-sentinel-never-log")),
        ),
    )

    assert run.output_summary == (
        "error_code=LLM_OUTPUT_INVALID;failure_stage=faq_draft;output_failure_kind=invalid_schema;"
        "output_schema_issues=business_claims:claim_scope_duplicate"
    )
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_schema_failure_summary_caps_eight_issues_and_ignores_malformed_input() -> None:
    """记录端口重复校验上游诊断，异常形状也不能污染或中断失败记录。"""
    run = AgentRun(
        id=uuid.uuid4(),
        store_id=uuid.uuid4(),
        conversation_id=uuid.uuid4(),
        model_provider="deepseek",
        model_name="test-model",
        action=AgentAction.HUMAN_REVIEW.value,
        status=AgentRunStatus.RUNNING.value,
    )
    session = Mock(spec=AsyncSession)
    session.get = AsyncMock(return_value=run)
    session.commit = AsyncMock()
    paths = (
        "root",
        "decision",
        "content",
        "language",
        "reason_code",
        "business_claims",
        "send_performed",
        "business_claims[].action",
        "business_claims[].tense",
    )
    issues = (cast(LLMOutputSchemaIssue, (["private text"], "missing")),) + tuple(
        cast(LLMOutputSchemaIssue, (path, "missing")) for path in paths
    )

    await SqlAlchemyAgentRunRecorder(session).fail(
        run.id,
        AgentRunStatus.FAILED,
        AgentAction.FAILED,
        "LLM_OUTPUT_INVALID",
        "deepseek",
        "test-model",
        42,
        output_failure_kind="invalid_schema",
        output_schema_issues=issues,
    )

    assert run.output_summary == (
        "error_code=LLM_OUTPUT_INVALID;output_failure_kind=invalid_schema;"
        "output_schema_issues=" + ",".join(f"{path}:missing" for path in paths[:8])
    )
    assert "private text" not in run.output_summary
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_failure_summary_rejects_unlisted_values_and_non_output_errors() -> None:
    """即使调用者误传动态字段，也只能留下已有稳定错误码。"""
    run = AgentRun(
        id=uuid.uuid4(),
        store_id=uuid.uuid4(),
        conversation_id=uuid.uuid4(),
        model_provider="deepseek",
        model_name="test-model",
        action=AgentAction.HUMAN_REVIEW.value,
        status=AgentRunStatus.RUNNING.value,
    )
    session = Mock(spec=AsyncSession)
    session.get = AsyncMock(return_value=run)
    session.commit = AsyncMock()
    recorder = SqlAlchemyAgentRunRecorder(session)
    await recorder.fail(
        run.id,
        AgentRunStatus.FAILED,
        AgentAction.FAILED,
        "LLM_OUTPUT_INVALID",
        "deepseek",
        "test-model",
        42,
        failure_stage=cast(LLMFailureStage, "raw private prompt"),
        output_failure_kind=cast(LLMOutputFailureKind, "raw model answer"),
    )
    assert run.output_summary == "error_code=LLM_OUTPUT_INVALID"

    await recorder.fail(
        run.id,
        AgentRunStatus.TIMEOUT,
        AgentAction.FAILED,
        "LLM_TIMEOUT",
        "deepseek",
        "test-model",
        42,
        failure_stage=LLMFailureStage.FAQ_DRAFT,
        output_failure_kind="invalid_json",
        output_schema_issues=(("content", "missing"),),
    )
    assert run.output_summary == "error_code=LLM_TIMEOUT"


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

    completion = AgentWorkflowRunCompletion(
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
        decision_reason="faq_review_confidence_low",
    )
    await recorder.complete_workflow(run.id, completion)

    assert run.retrieval_score == Decimal("0.8500")
    assert run.final_confidence == Decimal("0.8000")
    assert str(citation_id) in (run.output_summary or "")
    assert "decision_reason=faq_review_confidence_low" in (run.output_summary or "")
    assert "签收后" not in (run.output_summary or "")
    assert run.status == AgentRunStatus.SUCCEEDED.value
    session.commit.assert_awaited_once()

    await recorder.complete_workflow(
        run.id,
        replace(completion, decision_reason=cast(AgentDecisionReason, "raw private model text")),
    )
    assert "decision_reason=unknown" in (run.output_summary or "")
    assert "raw private model text" not in (run.output_summary or "")

    await recorder.complete_workflow(
        run.id,
        replace(
            completion,
            node_timings_ms=[
                ("classification", 12),
                ("retrieval", 17),
                ("faq_draft", 24),
                ("safety_review", 31),
                ("translation", 2),
                ("retrieval_embedding_wait", 11),
                ("retrieval_search", 17),
                ("retrieval_search_acquire", 7),
                ("retrieval_search_query", 8),
                ("raw private model text", 999),
                ("retrieval", 5),
                ("classification", -1),
                ("retrieval_search", -1),
            ],
        ),
    )
    assert "node_timings_ms=classification:12,retrieval:17,faq_draft:24,safety_review:31,translation:2" in (
        run.output_summary or ""
    )
    assert "retrieval_embedding_wait:11,retrieval_search:17" in (run.output_summary or "")
    assert "retrieval_search_acquire:7,retrieval_search_query:8" in (run.output_summary or "")
    assert "raw private model text" not in (run.output_summary or "")
    assert "retrieval:5" not in (run.output_summary or "")
    assert "classification:-1" not in (run.output_summary or "")


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
