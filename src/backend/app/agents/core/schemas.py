"""定义意图识别的输入、模型输出和服务结果契约。"""

import uuid
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.agents.core.reply_policy import CustomerLanguage, SupportedLanguage
from app.agents.core.translation import TranslationBundleResult
from app.tools.contracts import ToolName


class IntentName(StrEnum):
    """MVP 阶段允许返回的五类客服意图。"""

    LOGISTICS_QUERY = "logistics_query"
    RETURN_POLICY = "return_policy"
    SIZE_GUIDE = "size_guide"
    PRICE_INQUIRY = "price_inquiry"
    GENERAL = "general"


class ClassificationState(StrEnum):
    """区分正常分类和主动拒判，避免把不确定问题塞入 general。"""

    CLASSIFIED = "classified"
    UNKNOWN = "unknown"
    MIXED = "mixed"
    INSUFFICIENT_CONTEXT = "insufficient_context"
    MODEL_REFUSAL = "model_refusal"


class AgentAction(StrEnum):
    """与架构设计一致的 Agent 最终动作。"""

    AUTO_REPLY = "auto_reply"
    HUMAN_REVIEW = "human_review"
    TRANSFER_HUMAN = "transfer_human"
    FAILED = "failed"


class AgentRunStatus(StrEnum):
    """Agent 运行记录的生命周期状态。"""

    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMEOUT = "timeout"


class WorkflowTerminalState(StrEnum):
    """Phase 2 工作流的可诊断终态；READY 不代表消息已经发送。"""

    AUTO_REPLY_READY = "AUTO_REPLY_READY"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    TRANSFERRED = "TRANSFERRED"
    FAILED = "FAILED"


class MessageContext(BaseModel):
    """传给分类器的最小历史消息。"""

    role: Literal["user", "assistant", "agent", "system"]
    content: str = Field(min_length=1, max_length=4000)


class ClassificationCommand(BaseModel):
    """由可信业务服务组装的意图分类命令。

    该命令只承载已经完成店铺隔离校验的上下文。Agent 不通过这些 ID
    反向查询或写入业务表，避免绕过全栈服务层。
    """

    store_id: uuid.UUID
    conversation_id: uuid.UUID
    trigger_message_id: uuid.UUID
    message: str = Field(min_length=1, max_length=4000)
    history: list[MessageContext] = Field(default_factory=list, max_length=10)
    language: str | None = Field(default=None, max_length=20)
    trace_id: str = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_context_budget(self) -> "ClassificationCommand":
        """限制模型上下文总字符数，防止异常输入放大成本和延迟。"""
        total_characters = len(self.message) + sum(len(item.content) for item in self.history)
        if total_characters > 12_000:
            raise ValueError("意图分类上下文不能超过 12000 字符")
        return self


class IntentModelOutput(BaseModel):
    """模型必须遵守的结构化意图输出。"""

    intent: IntentName | None
    confidence: float = Field(ge=0.0, le=1.0)
    classification_state: ClassificationState

    @model_validator(mode="after")
    def validate_intent_consistency(self) -> "IntentModelOutput":
        """保证正常分类与拒判状态不会产生互相矛盾的结果。"""
        if self.classification_state == ClassificationState.CLASSIFIED and self.intent is None:
            raise ValueError("classified 状态必须提供五类意图之一")
        if self.classification_state != ClassificationState.CLASSIFIED and self.intent is not None:
            raise ValueError("拒判状态不能携带被猜测的意图")
        return self


class IntentClassificationResult(BaseModel):
    """供后续 Agent 工作流消费的分类结果。"""

    agent_run_id: uuid.UUID
    intent: IntentName | None
    confidence: float = Field(ge=0.0, le=1.0)
    classification_state: ClassificationState
    action: AgentAction
    requires_human: bool
    provider: str
    model: str
    prompt_version: str
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    latency_ms: int = Field(ge=0)
    trace_id: str


class IntentInferenceResult(BaseModel):
    """不创建独立运行记录的内部分类结果。"""

    output: IntentModelOutput
    provider: str
    model: str
    prompt_version: str
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    latency_ms: int = Field(ge=0)


class AgentCitation(BaseModel):
    """返回给全栈层的引用元数据，不包含额外客户信息。"""

    document_id: uuid.UUID
    chunk_id: uuid.UUID
    category_id: uuid.UUID | None
    document_version: int = Field(ge=1)
    chunk_index: int = Field(ge=0)
    score: float = Field(ge=0, le=1)
    source_label: str = Field(min_length=1, max_length=500)


RequiredToolName = ToolName


class AgentToolCallView(BaseModel):
    """工作流向调用方暴露的低敏工具执行摘要。"""

    tool_call_id: uuid.UUID
    tool_name: ToolName
    status: Literal["succeeded", "failed", "timeout", "unknown"]
    error_code: str | None = None
    mocked: bool = False
    replayed: bool = False


class AgentWorkflowResult(BaseModel):
    """FAQ Agent 的内部结果契约；调用方仍需负责权限和业务副作用。"""

    agent_run_id: uuid.UUID
    terminal_state: WorkflowTerminalState
    intent: IntentName | None
    classification_state: ClassificationState
    citations: list[AgentCitation]
    draft_reply: str | None
    required_tools: list[RequiredToolName]
    tool_calls: list[AgentToolCallView] = Field(default_factory=list)
    intent_confidence: float = Field(ge=0, le=1)
    retrieval_score: float = Field(ge=0, le=1)
    grounding_confidence: float = Field(ge=0, le=1)
    final_confidence: float = Field(ge=0, le=1)
    action: AgentAction
    requires_human: bool
    transfer_performed: bool = False
    send_performed: Literal[False] = False
    detected_language: CustomerLanguage
    reply_language: SupportedLanguage
    customer_translation: TranslationBundleResult | None = None
    safety_reason_codes: list[str] = Field(default_factory=list, max_length=8)
    provider: str
    model: str
    embedding_provider: str | None = None
    embedding_model: str | None = None
    reranker_provider: str | None = None
    reranker_model: str | None = None
    reranker_revision: str | None = None
    retrieval_candidate_count: int = Field(default=0, ge=0, le=100)
    prompt_versions: dict[str, str]
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    latency_ms: int = Field(ge=0)
    trace_id: str = Field(min_length=1, max_length=100)
