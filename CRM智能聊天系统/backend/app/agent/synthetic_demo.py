"""使用固定合成场景验证真实模型建议，不接触店铺或客户数据。"""

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.agent.generation import StructuredGenerationService
from app.agent.providers.base import StructuredRequest
from app.agent.providers.factory import build_provider_pair
from app.agent.security import (
    SYNTHETIC_DEMO_PROMPT_VERSION,
    SYNTHETIC_DEMO_SCENARIOS,
    SYNTHETIC_DEMO_SYSTEM_PROMPT,
    build_synthetic_demo_payload,
)
from app.shared.config.settings import Settings


class SyntheticDemoOutput(BaseModel):
    """真实模型对固定演示场景的结构化回答。"""

    model_config = ConfigDict(extra="forbid")

    content: str = Field(min_length=1, max_length=1000)
    intent: Literal["logistics_query", "return_policy", "size_guide", "price_inquiry", "general"]
    confidence: float = Field(ge=0, le=1)
    requires_human: bool
    reason_code: Literal["faq_grounded", "tool_grounded", "insufficient_evidence", "high_risk_review"]


@dataclass(frozen=True, slots=True)
class SyntheticDemoResult:
    """向客服工作台返回的低敏模型结果和用量。"""

    scenario_id: str
    output: SyntheticDemoOutput
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: int


def resolve_synthetic_demo_scenario(external_conversation_id: str, message: str) -> str | None:
    """只接受种子脚本创建且正文未被修改的固定演示会话。"""
    prefix = "ai-demo-"
    if not external_conversation_id.startswith(prefix):
        return None
    scenario_id = external_conversation_id.removeprefix(prefix)
    scenario = SYNTHETIC_DEMO_SCENARIOS.get(scenario_id)
    if scenario is None or message != scenario["customer_message"]:
        return None
    return scenario_id


async def generate_synthetic_demo(
    settings: Settings,
    scenario_id: str,
    trace_id: str,
) -> SyntheticDemoResult:
    """调用真实 Provider 处理固定合成数据，结果始终只作为人工草稿。

    演示输入由服务端常量生成，浏览器不能提交任意客户正文。即使模型给出
    高置信度，本入口也不会执行工具、自动发送或改变会话状态。
    """
    primary_provider, fallback_provider = build_provider_pair(settings)
    result = await StructuredGenerationService(primary_provider, fallback_provider, max_attempts=2).generate(
        StructuredRequest(
            system_prompt=SYNTHETIC_DEMO_SYSTEM_PROMPT,
            user_prompt=build_synthetic_demo_payload(scenario_id),
            trace_id=trace_id,
            max_output_tokens=settings.llm_max_output_tokens,
        ),
        SyntheticDemoOutput,
    )
    return SyntheticDemoResult(
        scenario_id=scenario_id,
        output=result.parsed_output,
        provider=result.provider,
        model=result.model,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        latency_ms=result.latency_ms,
    )


__all__ = [
    "SYNTHETIC_DEMO_PROMPT_VERSION",
    "SyntheticDemoOutput",
    "SyntheticDemoResult",
    "generate_synthetic_demo",
    "resolve_synthetic_demo_scenario",
]
