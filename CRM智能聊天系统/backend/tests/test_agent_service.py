"""验证模型重试、降级、拒判和 Agent 运行记录。"""

import uuid
from collections import deque

import pytest

from app.agent.errors import LLMErrorCode, LLMProviderError
from app.agent.providers.base import LLMProvider, ProviderResult, StructuredRequest
from app.agent.repository import AgentRunRecorder, AgentRunStart
from app.agent.schemas import (
    AgentAction,
    AgentRunStatus,
    ClassificationCommand,
    ClassificationState,
    IntentClassificationResult,
    IntentModelOutput,
    IntentName,
)
from app.agent.service import IntentClassificationService


class ScriptedProvider(LLMProvider):
    """按测试脚本返回结果或异常，避免单元测试访问真实模型。"""

    def __init__(self, provider_name: str, model_name: str, outcomes: list[object]) -> None:
        self.provider_name = provider_name
        self.model_name = model_name
        self.outcomes = deque(outcomes)
        self.requests: list[StructuredRequest] = []

    async def generate_structured(
        self,
        request: StructuredRequest,
        response_schema: type[IntentModelOutput],
    ) -> ProviderResult[IntentModelOutput]:
        self.requests.append(request)
        outcome = self.outcomes.popleft()
        if isinstance(outcome, Exception):
            raise outcome
        return ProviderResult(
            provider=self.provider_name,
            model=self.model_name,
            parsed_output=response_schema.model_validate(outcome),
            input_tokens=20,
            output_tokens=8,
            latency_ms=15,
            provider_request_id=f"request-{self.provider_name}",
        )


class MemoryRunRecorder(AgentRunRecorder):
    """在内存中保存运行状态，用于验证事务外的领域行为。"""

    def __init__(self) -> None:
        self.run_id = uuid.uuid4()
        self.started: AgentRunStart | None = None
        self.succeeded: IntentClassificationResult | None = None
        self.failed: tuple[AgentRunStatus, AgentAction, str, str, str, int] | None = None

    async def start(self, values: AgentRunStart) -> uuid.UUID:
        self.started = values
        return self.run_id

    async def succeed(self, run_id: uuid.UUID, result: IntentClassificationResult) -> None:
        assert run_id == self.run_id
        self.succeeded = result

    async def fail(
        self,
        run_id: uuid.UUID,
        status: AgentRunStatus,
        action: AgentAction,
        error_code: str,
        provider_name: str,
        model_name: str,
        latency_ms: int,
    ) -> None:
        assert run_id == self.run_id
        self.failed = (status, action, error_code, provider_name, model_name, latency_ms)


def command() -> ClassificationCommand:
    """构造不含真实客户数据的分类命令。"""
    return ClassificationCommand(
        store_id=uuid.uuid4(),
        conversation_id=uuid.uuid4(),
        trigger_message_id=uuid.uuid4(),
        message="订单 AB123456789 到哪里了？联系 buyer@example.com",
        history=[],
        language="zh-CN",
        trace_id="trace-agent-service",
    )


@pytest.mark.asyncio
async def test_high_confidence_classification_is_saved_for_human_review() -> None:
    """高置信度分类成功也只能进入人工复核，不能越过 Phase 1 边界。"""
    provider = ScriptedProvider(
        "openai",
        "test-model",
        [
            IntentModelOutput(
                intent=IntentName.LOGISTICS_QUERY,
                confidence=0.93,
                classification_state=ClassificationState.CLASSIFIED,
            )
        ],
    )
    recorder = MemoryRunRecorder()

    result = await IntentClassificationService(provider, None, recorder, max_attempts=3).classify(command())

    assert result.action == AgentAction.HUMAN_REVIEW
    assert result.intent == IntentName.LOGISTICS_QUERY
    assert recorder.succeeded == result
    assert recorder.started is not None
    assert "buyer@example.com" not in provider.requests[0].user_prompt
    assert "AB123456789" not in provider.requests[0].user_prompt
    assert "buyer@example.com" not in recorder.started.input_summary
    assert "AB123456789" not in recorder.started.input_summary


@pytest.mark.asyncio
async def test_retryable_primary_errors_fall_back_within_three_attempts() -> None:
    """主模型两次可重试失败后只允许调用备用模型一次。"""
    error = LLMProviderError(LLMErrorCode.LLM_TIMEOUT, "模型调用超时", retriable=True)
    primary = ScriptedProvider("openai", "primary-model", [error, error])
    fallback = ScriptedProvider(
        "anthropic",
        "fallback-model",
        [
            IntentModelOutput(
                intent=IntentName.RETURN_POLICY,
                confidence=0.84,
                classification_state=ClassificationState.CLASSIFIED,
            )
        ],
    )
    recorder = MemoryRunRecorder()

    result = await IntentClassificationService(primary, fallback, recorder, max_attempts=3).classify(command())

    assert result.provider == "anthropic"
    assert len(primary.requests) == 2
    assert len(fallback.requests) == 1
    assert primary.requests[1].is_repair is False


@pytest.mark.asyncio
async def test_non_retryable_provider_error_stops_immediately_and_records_failure() -> None:
    """认证和参数错误不能通过反复调用模型放大故障与成本。"""
    error = LLMProviderError(LLMErrorCode.LLM_AUTHENTICATION_ERROR, "模型认证失败", retriable=False)
    primary = ScriptedProvider("openai", "primary-model", [error])
    fallback = ScriptedProvider("anthropic", "fallback-model", [])
    recorder = MemoryRunRecorder()

    with pytest.raises(LLMProviderError) as captured:
        await IntentClassificationService(primary, fallback, recorder, max_attempts=3).classify(command())

    assert captured.value.code == LLMErrorCode.LLM_AUTHENTICATION_ERROR
    assert len(primary.requests) == 1
    assert len(fallback.requests) == 0
    assert recorder.failed is not None
    assert recorder.failed[0] == AgentRunStatus.FAILED
    assert recorder.failed[1] == AgentAction.FAILED


@pytest.mark.asyncio
async def test_model_refusal_is_a_conservative_success_without_retry() -> None:
    """模型安全拒绝应转人工，不能换模型尝试绕过拒绝。"""
    refusal = LLMProviderError(LLMErrorCode.LLM_REFUSAL, "模型拒绝处理", retriable=False)
    primary = ScriptedProvider("openai", "primary-model", [refusal])
    fallback = ScriptedProvider("anthropic", "fallback-model", [])
    recorder = MemoryRunRecorder()

    result = await IntentClassificationService(primary, fallback, recorder, max_attempts=3).classify(command())

    assert result.intent is None
    assert result.classification_state == ClassificationState.MODEL_REFUSAL
    assert result.action == AgentAction.TRANSFER_HUMAN
    assert len(primary.requests) == 1
    assert len(fallback.requests) == 0
    assert recorder.succeeded == result


@pytest.mark.asyncio
async def test_invalid_structured_output_enables_repair_instruction() -> None:
    """只有结构校验失败后的下一次请求才携带结构重生成说明。"""
    invalid = {"intent": "logistics_query", "confidence": 2, "classification_state": "classified"}
    primary = ScriptedProvider(
        "openai",
        "primary-model",
        [
            invalid,
            IntentModelOutput(
                intent=IntentName.LOGISTICS_QUERY,
                confidence=0.82,
                classification_state=ClassificationState.CLASSIFIED,
            ),
        ],
    )
    recorder = MemoryRunRecorder()

    result = await IntentClassificationService(primary, None, recorder, max_attempts=2).classify(command())

    assert result.intent == IntentName.LOGISTICS_QUERY
    assert primary.requests[0].is_repair is False
    assert primary.requests[1].is_repair is True
