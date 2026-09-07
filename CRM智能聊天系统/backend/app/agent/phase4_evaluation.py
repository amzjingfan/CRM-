"""聚合 Phase 4 离线评测与线上运行导出的统一指标。"""

import math
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator

AgentMetricAction = Literal["auto_reply", "human_review", "transfer_human", "failed"]


class AgentMetricSample(BaseModel):
    """单次 Agent 运行的低敏指标样本。

    样本只包含标签、计数和时延，不包含客户消息、知识正文、工具原始结果
    或供应商响应。线上样本可从 ``agent_runs``、``tool_calls`` 和 SSE 压测
    摘要组合，离线评测也使用同一契约。
    """

    case_id: str = Field(min_length=1, max_length=100)
    expected_intent: str | None = Field(default=None, max_length=100)
    predicted_intent: str | None = Field(default=None, max_length=100)
    requires_rag: bool = False
    rag_hit: bool = False
    tool_call_count: int = Field(default=0, ge=0)
    tool_success_count: int = Field(default=0, ge=0)
    expected_action: AgentMetricAction | None = None
    actual_action: AgentMetricAction
    first_output_latency_ms: int = Field(ge=0)
    total_latency_ms: int = Field(ge=0)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_counts(self) -> "AgentMetricSample":
        """工具成功数不能超过调用数，首输出也不能晚于总完成时间。"""
        if self.tool_success_count > self.tool_call_count:
            raise ValueError("工具成功数不能超过调用数")
        if self.first_output_latency_ms > self.total_latency_ms:
            raise ValueError("首输出时延不能大于总时延")
        return self


class Phase4Metrics(BaseModel):
    """Phase 4 质量、可靠性、延迟和成本聚合结果。"""

    sample_count: int = Field(ge=0)
    intent_accuracy: float = Field(ge=0, le=1)
    rag_hit_rate: float = Field(ge=0, le=1)
    tool_success_rate: float = Field(ge=0, le=1)
    transfer_rate: float = Field(ge=0, le=1)
    action_accuracy: float = Field(ge=0, le=1)
    p95_first_output_latency_ms: int = Field(ge=0)
    average_latency_ms: float = Field(ge=0)
    total_input_tokens: int = Field(ge=0)
    total_output_tokens: int = Field(ge=0)
    estimated_cost_usd: Decimal = Field(ge=0)


def calculate_phase4_metrics(
    samples: list[AgentMetricSample],
    *,
    input_cost_per_million: Decimal = Decimal("0"),
    output_cost_per_million: Decimal = Decimal("0"),
) -> Phase4Metrics:
    """计算统一指标；模型价格由运行方显式传入，代码不硬编码易变价格。"""
    if input_cost_per_million < 0 or output_cost_per_million < 0:
        raise ValueError("Token 单价不能为负数")
    intent_samples = [item for item in samples if item.expected_intent is not None]
    rag_samples = [item for item in samples if item.requires_rag]
    action_samples = [item for item in samples if item.expected_action is not None]
    total_tool_calls = sum(item.tool_call_count for item in samples)
    total_tool_successes = sum(item.tool_success_count for item in samples)
    total_input_tokens = sum(item.input_tokens for item in samples)
    total_output_tokens = sum(item.output_tokens for item in samples)
    sorted_first_output = sorted(item.first_output_latency_ms for item in samples)
    p95_index = max(0, math.ceil(len(sorted_first_output) * 0.95) - 1) if sorted_first_output else 0
    million = Decimal("1000000")
    estimated_cost = (
        Decimal(total_input_tokens) * input_cost_per_million + Decimal(total_output_tokens) * output_cost_per_million
    ) / million
    return Phase4Metrics(
        sample_count=len(samples),
        intent_accuracy=(
            sum(item.expected_intent == item.predicted_intent for item in intent_samples) / len(intent_samples)
            if intent_samples
            else 0.0
        ),
        rag_hit_rate=sum(item.rag_hit for item in rag_samples) / len(rag_samples) if rag_samples else 0.0,
        tool_success_rate=total_tool_successes / total_tool_calls if total_tool_calls else 0.0,
        transfer_rate=(
            sum(item.actual_action == "transfer_human" for item in samples) / len(samples) if samples else 0.0
        ),
        action_accuracy=(
            sum(item.expected_action == item.actual_action for item in action_samples) / len(action_samples)
            if action_samples
            else 0.0
        ),
        p95_first_output_latency_ms=sorted_first_output[p95_index] if sorted_first_output else 0,
        average_latency_ms=sum(item.total_latency_ms for item in samples) / len(samples) if samples else 0.0,
        total_input_tokens=total_input_tokens,
        total_output_tokens=total_output_tokens,
        estimated_cost_usd=estimated_cost.quantize(Decimal("0.000001")),
    )
