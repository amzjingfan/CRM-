"""定义意图识别的输入、模型输出和服务结果契约。"""

import uuid
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.agent.business_claims import BusinessClaimInventory
from app.agent.reply_policy import AgentReplyProfile, CustomerLanguage, SupportedLanguage
from app.agent.translation import TranslationBundleResult
from app.tools.contracts import ToolName, WriteToolName, validate_tool_arguments


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


class ApprovedToolAction(BaseModel):
    """可信业务层对单次外部写操作的显式批准。

    客户自然语言和模型输出都不能创建该对象。调用方必须先完成认证、店铺
    授权、业务确认和频控，再把固定参数与幂等键交给 Agent 使用。
    """

    tool_name: WriteToolName
    idempotency_key: str = Field(min_length=1, max_length=200)
    arguments: dict[str, object]

    @model_validator(mode="after")
    def validate_approved_arguments(self) -> "ApprovedToolAction":
        """按具体工具 Schema 拒绝缺失、越界和额外参数。"""
        self.arguments = validate_tool_arguments(self.tool_name, self.arguments)
        return self


class AgentToolRuntimeContext(BaseModel):
    """全栈服务提供给 Agent 的最小工具执行上下文。

    `order_id`、`customer_id`、可用工具和权限都必须来自可信业务查询，Agent
    不会从客户消息提取资源 ID，也不会扩大该集合。
    """

    order_id: str | None = Field(default=None, min_length=1, max_length=200)
    customer_id: uuid.UUID | None = None
    available_tools: set[ToolName] = Field(default_factory=set)
    permissions: set[str] = Field(default_factory=set)
    approved_actions: list[ApprovedToolAction] = Field(default_factory=list, max_length=4)

    @model_validator(mode="after")
    def validate_unique_approvals(self) -> "AgentToolRuntimeContext":
        """同一工具只能有一个批准对象，避免参数选择歧义。"""
        names = [item.tool_name for item in self.approved_actions]
        if len(names) != len(set(names)):
            raise ValueError("同一写工具不能重复批准")
        return self


class AgentWorkflowCommand(ClassificationCommand):
    """由可信业务服务传入 FAQ Agent 的完整命令。"""

    tool_context: AgentToolRuntimeContext | None = None
    reply_profile: AgentReplyProfile = Field(default_factory=AgentReplyProfile)
    knowledge_file_ids: list[uuid.UUID] = Field(default_factory=list, max_length=100)
    debug_mode: bool = False
    agent_config_id: uuid.UUID | None = None


class FaqAnswerModelOutput(BaseModel):
    """FAQ 回答模型必须返回的结构化草稿。"""

    answer: str = Field(min_length=1, max_length=2000)
    citation_chunk_ids: list[uuid.UUID] = Field(min_length=1, max_length=5)
    grounding_confidence: float = Field(ge=0, le=1)
    answer_language: SupportedLanguage
    needs_human: bool
    business_claims: BusinessClaimInventory

    @model_validator(mode="after")
    def validate_unique_citations(self) -> "FaqAnswerModelOutput":
        """重复引用不增加证据强度，必须在模型边界拒绝。"""
        if len(set(self.citation_chunk_ids)) != len(self.citation_chunk_ids):
            raise ValueError("FAQ 引用不能重复")
        return self


class ConciseFaqAnswerModelOutput(FaqAnswerModelOutput):
    """调试文件草稿在模型 Schema 层限制逗号串列，避免误触位置 DLP。"""

    answer: str = Field(min_length=1, max_length=2000, pattern=r"^[^,，、;；\r\n]*$")


class GroundingReviewOutput(BaseModel):
    """独立复核节点对答案安全性和知识一致性的判断。"""

    is_safe: bool
    is_grounded: bool
    business_claims_consistent: bool
    confidence: float = Field(ge=0, le=1)
    reason_codes: list[str] = Field(default_factory=list, max_length=5)


class TrustedFaqReviewOutput(GroundingReviewOutput):
    """独立复核人工审批 FAQ 原文，并声明其业务命题。"""

    model_config = ConfigDict(extra="forbid")

    answers_question: bool
    needs_human: bool
    business_claims: BusinessClaimInventory
    reason_codes: list[str] = Field(max_length=5)


class ToolAnswerModelOutput(BaseModel):
    """工具结果解释节点必须返回的结构化草稿。"""

    answer: str = Field(min_length=1, max_length=2000)
    tool_call_ids: list[uuid.UUID] = Field(min_length=1, max_length=3)
    grounding_confidence: float = Field(ge=0, le=1)
    answer_language: SupportedLanguage
    needs_human: bool
    business_claims: BusinessClaimInventory

    @model_validator(mode="after")
    def validate_unique_tool_calls(self) -> "ToolAnswerModelOutput":
        """重复工具 ID 不增加事实依据，必须在模型边界拒绝。"""
        if len(self.tool_call_ids) != len(set(self.tool_call_ids)):
            raise ValueError("工具调用引用不能重复")
        return self


class ToolGroundingReviewOutput(BaseModel):
    """工具答案复核节点对事实、安全和完成声明的判断。"""

    is_safe: bool
    is_grounded: bool
    completion_claim_valid: bool
    business_claims_consistent: bool
    confidence: float = Field(ge=0, le=1)
    reason_codes: list[str] = Field(default_factory=list, max_length=5)


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
