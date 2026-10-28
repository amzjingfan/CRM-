"""定义不依赖具体供应商 SDK 的统一模型接口。"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Generic, TypeVar

from pydantic import BaseModel

from app.agents.core.errors import LLMErrorCode, LLMProviderError
from app.agents.core.prompt_registry import BusinessPromptId, get_business_prompt
from app.agents.core.security import (
    PROMPT_DLP_POLICY_VERSION,
    PromptSafetyDecision,
    PromptSafetyState,
    RealModelEvaluationSafetyContext,
    evaluate_prompt_safety,
    evaluate_system_prompt_safety,
)

logger = logging.getLogger(__name__)

OutputT = TypeVar("OutputT", bound=BaseModel)


@dataclass(frozen=True, slots=True)
class StructuredRequest:
    """一次受控结构化模型请求。"""

    system_prompt: str
    user_prompt: str
    trace_id: str
    max_output_tokens: int
    is_repair: bool = False
    temperature: float | None = None
    real_model_evaluation_context: RealModelEvaluationSafetyContext | None = field(default=None, repr=False)
    business_prompt_id: BusinessPromptId | None = None
    prompt_safety_state: PromptSafetyState = field(init=False)
    prompt_safety_reason_code: str = field(init=False)
    prompt_safety_policy_version: str = field(init=False)

    def __post_init__(self) -> None:
        """在所有外部 Provider 的共同边界检查完整文本信封。"""
        if self.temperature is not None and not 0 <= self.temperature <= 2:
            raise ValueError("模型 temperature 必须在 0 到 2 之间")
        user_decision = evaluate_prompt_safety(
            self.user_prompt,
            real_model_evaluation_context=self.real_model_evaluation_context,
            business_prompt_id=self.business_prompt_id,
        )
        system_decision = evaluate_system_prompt_safety(
            self.system_prompt,
            business_prompt_id=self.business_prompt_id,
        )
        object.__setattr__(self, "user_prompt", user_decision.sanitized_text)
        object.__setattr__(self, "system_prompt", system_decision.sanitized_text)
        envelope_decision = self._resolve_envelope_decision(user_decision, system_decision)
        object.__setattr__(self, "prompt_safety_state", envelope_decision.state)
        object.__setattr__(self, "prompt_safety_reason_code", envelope_decision.reason_code)
        object.__setattr__(self, "prompt_safety_policy_version", PROMPT_DLP_POLICY_VERSION)

    @staticmethod
    def _resolve_envelope_decision(
        user_decision: PromptSafetyDecision,
        system_decision: PromptSafetyDecision,
    ) -> PromptSafetyDecision:
        """按 blocked、uncertain、allowed 的顺序合并完整信封结论。"""
        for state in (PromptSafetyState.BLOCKED, PromptSafetyState.UNCERTAIN):
            for decision in (user_decision, system_decision):
                if decision.state == state:
                    return decision
        return PromptSafetyDecision(
            state=PromptSafetyState.ALLOWED,
            sanitized_text="",
            reason_code="TRUSTED_PROMPT_ENVELOPE_ALLOWED",
        )

    def ensure_safe_for_external_provider(self, *, response_schema_name: str | None = None) -> None:
        """只允许 ``allowed`` 请求触达供应商 SDK，其余状态稳定转人工。

        日志只记录枚举状态、稳定原因码和既有 Trace ID，不记录 Prompt、地址或
        其他客户正文，便于定位安全门禁命中而不制造第二条数据泄漏路径。
        """
        reason_code = self.prompt_safety_reason_code
        if self.business_prompt_id is not None:
            registration = get_business_prompt(self.business_prompt_id)
            if response_schema_name != registration.response_schema_name:
                reason_code = "BUSINESS_PROMPT_RESPONSE_SCHEMA_MISMATCH"
        if self.prompt_safety_state == PromptSafetyState.ALLOWED and reason_code == self.prompt_safety_reason_code:
            return
        logger.warning(
            "llm_input_blocked",
            extra={
                "event": "llm_input_blocked",
                "trace_id": self.trace_id,
                "prompt_safety_state": self.prompt_safety_state.value,
                "prompt_safety_reason_code": reason_code,
                "prompt_safety_policy_version": self.prompt_safety_policy_version,
            },
        )
        raise LLMProviderError(
            LLMErrorCode.LLM_REFUSAL,
            "模型输入未通过本地隐私安全门禁",
            retriable=False,
        )


@dataclass(frozen=True, slots=True)
class ProviderResult(Generic[OutputT]):
    """供应商无关的结构化响应和资源统计。"""

    provider: str
    model: str
    parsed_output: OutputT
    input_tokens: int
    output_tokens: int
    latency_ms: int
    provider_request_id: str | None


class LLMProvider(ABC):
    """所有模型供应商必须实现的最小异步契约。"""

    provider_name: str
    model_name: str

    @abstractmethod
    async def generate_structured(
        self,
        request: StructuredRequest,
        response_schema: type[OutputT],
    ) -> ProviderResult[OutputT]:
        """生成并验证结构化结果，不返回未经校验的模型文本。"""
