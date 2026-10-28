"""编排意图分类、有限重试、备用模型和运行追踪。"""

import hashlib
import logging
import time
import uuid

from pydantic import ValidationError

from app.agents.core.errors import LLMErrorCode, LLMProviderError
from app.agents.core.prompt import INTENT_CLASSIFIER_SYSTEM_PROMPT, PROMPT_VERSION, build_intent_user_prompt
from app.agents.core.prompt_registry import BusinessPromptId
from app.agents.core.providers.base import LLMProvider, StructuredRequest
from app.agents.core.repository import AgentRunRecorder, AgentRunStart
from app.agents.core.schemas import (
    AgentAction,
    AgentRunStatus,
    ClassificationCommand,
    ClassificationState,
    IntentClassificationResult,
    IntentInferenceResult,
    IntentModelOutput,
)

logger = logging.getLogger(__name__)


def decide_phase1_action(output: IntentModelOutput) -> AgentAction:
    """根据拒判状态和置信度生成 Phase 1 保守动作。

    Phase 1 尚未具备 RAG、回复审核和平台发送能力，因此即使置信度很高，
    也只能进入人工复核，不能返回会被误解为已经发送的 auto_reply。
    """
    if output.classification_state != ClassificationState.CLASSIFIED or output.confidence < 0.6:
        return AgentAction.TRANSFER_HUMAN
    return AgentAction.HUMAN_REVIEW


def build_input_summary(command: ClassificationCommand) -> str:
    """生成不可逆摘要，满足追踪需要且不保存原始客户内容。"""
    joined_content = "\n".join([*(item.content for item in command.history), command.message])
    content_hash = hashlib.sha256(joined_content.encode("utf-8")).hexdigest()
    return f"messages={len(command.history) + 1};chars={len(joined_content)};sha256={content_hash}"


class IntentClassificationService:
    """执行一次可追踪、可降级且不会写业务表的意图分类。"""

    def __init__(
        self,
        primary_provider: LLMProvider,
        fallback_provider: LLMProvider | None,
        run_recorder: AgentRunRecorder,
        *,
        max_attempts: int,
        max_output_tokens: int = 256,
    ) -> None:
        """初始化分类服务并校验成本边界。"""
        if not 1 <= max_attempts <= 3:
            raise ValueError("模型总尝试次数必须在 1 到 3 之间")
        self.primary_provider = primary_provider
        self.fallback_provider = fallback_provider
        self.run_recorder = run_recorder
        self.max_attempts = max_attempts
        self.max_output_tokens = max_output_tokens

    @property
    def provider_name(self) -> str:
        """返回主分类 Provider 名称，供完整工作流预创建运行记录。"""
        return self.primary_provider.provider_name

    @property
    def model_name(self) -> str:
        """返回主分类模型名称，失败前也能写入可诊断运行记录。"""
        return self.primary_provider.model_name

    async def classify(self, command: ClassificationCommand) -> IntentClassificationResult:
        """分类客户消息，并在任何模型调用前创建运行记录。"""
        run_id = await self.run_recorder.start(
            AgentRunStart(
                store_id=command.store_id,
                conversation_id=command.conversation_id,
                trigger_message_id=command.trigger_message_id,
                provider_name=self.primary_provider.provider_name,
                model_name=self.primary_provider.model_name,
                prompt_version=PROMPT_VERSION,
                input_summary=build_input_summary(command),
                trace_id=command.trace_id,
            )
        )
        started_at = time.perf_counter()
        try:
            inference = await self.infer(command, agent_run_id=run_id)
        except LLMProviderError as error:
            provider = self.primary_provider
            if error.code == LLMErrorCode.LLM_REFUSAL:
                return await self._record_refusal(run_id, command, provider, started_at)
            await self._record_failure(run_id, command, provider, error, started_at)
            raise

        output = inference.output
        result = IntentClassificationResult(
            agent_run_id=run_id,
            intent=output.intent,
            confidence=output.confidence,
            classification_state=output.classification_state,
            action=decide_phase1_action(output),
            requires_human=True,
            provider=inference.provider,
            model=inference.model,
            prompt_version=inference.prompt_version,
            input_tokens=inference.input_tokens,
            output_tokens=inference.output_tokens,
            latency_ms=max(0, int((time.perf_counter() - started_at) * 1000)),
            trace_id=command.trace_id,
        )
        await self.run_recorder.succeed(run_id, result)
        logger.info(
            "intent_classified",
            extra={
                "trace_id": command.trace_id,
                "agent_run_id": str(run_id),
                "provider": result.provider,
                "model": result.model,
                "intent": result.intent.value if result.intent else None,
                "classification_state": result.classification_state.value,
                "action": result.action.value,
                "latency_ms": result.latency_ms,
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
            },
        )
        return result

    async def infer(
        self,
        command: ClassificationCommand,
        *,
        agent_run_id: uuid.UUID | None = None,
    ) -> IntentInferenceResult:
        """执行不创建独立运行记录的分类，供完整 Agent 工作流复用。"""
        started_at = time.perf_counter()
        providers = self._attempt_providers()
        last_error: LLMProviderError | None = None
        repair_next_attempt = False

        for attempt_index, provider in enumerate(providers):
            request = StructuredRequest(
                system_prompt=INTENT_CLASSIFIER_SYSTEM_PROMPT,
                user_prompt=build_intent_user_prompt(command, is_repair=repair_next_attempt),
                trace_id=command.trace_id,
                max_output_tokens=self.max_output_tokens,
                is_repair=repair_next_attempt,
                business_prompt_id=BusinessPromptId.INTENT_CLASSIFIER,
            )
            repair_next_attempt = False
            logger.info(
                "llm_call_started",
                extra={
                    "trace_id": command.trace_id,
                    "agent_run_id": str(agent_run_id) if agent_run_id else None,
                    "provider": provider.provider_name,
                    "model": provider.model_name,
                    "attempt": attempt_index + 1,
                },
            )
            try:
                provider_result = await provider.generate_structured(request, IntentModelOutput)
                output = IntentModelOutput.model_validate(provider_result.parsed_output)
            except ValidationError as error:
                last_error = LLMProviderError(
                    LLMErrorCode.LLM_OUTPUT_INVALID,
                    "模型输出未通过结构校验",
                    retriable=True,
                )
                logger.warning(
                    "llm_output_invalid",
                    extra={"trace_id": command.trace_id, "provider": provider.provider_name},
                )
                if attempt_index + 1 < len(providers):
                    repair_next_attempt = True
                    continue
                raise last_error from error
            except LLMProviderError as error:
                last_error = error
                logger.warning(
                    "llm_call_failed",
                    extra={
                        "trace_id": command.trace_id,
                        "agent_run_id": str(agent_run_id) if agent_run_id else None,
                        "provider": provider.provider_name,
                        "error_code": error.code.value,
                        "retriable": error.retriable,
                    },
                )
                if error.retriable and attempt_index + 1 < len(providers):
                    repair_next_attempt = error.code == LLMErrorCode.LLM_OUTPUT_INVALID
                    continue
                raise

            return IntentInferenceResult(
                output=output,
                provider=provider_result.provider,
                model=provider_result.model,
                prompt_version=PROMPT_VERSION,
                input_tokens=provider_result.input_tokens,
                output_tokens=provider_result.output_tokens,
                latency_ms=max(0, int((time.perf_counter() - started_at) * 1000)),
            )

        # 构造函数保证至少存在一次尝试，此分支仅防止未来修改破坏该不变量。
        if last_error is None:
            raise RuntimeError("模型尝试序列为空")
        raise last_error

    def _attempt_providers(self) -> list[LLMProvider]:
        """构造“主模型两次、备用模型一次”的有界尝试序列。"""
        providers = [self.primary_provider]
        if self.max_attempts >= 2:
            providers.append(self.primary_provider)
        if self.max_attempts >= 3 and self.fallback_provider is not None:
            providers.append(self.fallback_provider)
        return providers

    async def _record_refusal(
        self,
        run_id: uuid.UUID,
        command: ClassificationCommand,
        provider: LLMProvider,
        started_at: float,
    ) -> IntentClassificationResult:
        """把安全拒绝记录为可控转人工，而不是模型系统故障。"""
        result = IntentClassificationResult(
            agent_run_id=run_id,
            intent=None,
            confidence=0.0,
            classification_state=ClassificationState.MODEL_REFUSAL,
            action=AgentAction.TRANSFER_HUMAN,
            requires_human=True,
            provider=provider.provider_name,
            model=provider.model_name,
            prompt_version=PROMPT_VERSION,
            input_tokens=0,
            output_tokens=0,
            latency_ms=max(0, int((time.perf_counter() - started_at) * 1000)),
            trace_id=command.trace_id,
        )
        await self.run_recorder.succeed(run_id, result)
        return result

    async def _record_failure(
        self,
        run_id: uuid.UUID,
        command: ClassificationCommand,
        provider: LLMProvider,
        error: LLMProviderError,
        started_at: float,
    ) -> None:
        """保存失败终态，保证外部依赖故障不会抹去已开始的运行。"""
        status = AgentRunStatus.TIMEOUT if error.code == LLMErrorCode.LLM_TIMEOUT else AgentRunStatus.FAILED
        await self.run_recorder.fail(
            run_id,
            status,
            AgentAction.FAILED,
            error.code.value,
            provider.provider_name,
            provider.model_name,
            max(0, int((time.perf_counter() - started_at) * 1000)),
        )
