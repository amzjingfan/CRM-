"""Agent 运营管理公开类型。"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.agent.reply_policy import AgentReplyProfile

ToolName = Literal[
    "query_order",
    "query_logistics",
    "query_customer_profile",
    "update_shipping_address",
    "send_coupon",
    "transfer_to_human",
    "send_platform_message",
]
AgentType = Literal["service", "operations"]


class AgentConfigCreate(BaseModel):
    """创建店铺运营配置；AI 内部配置不属于可写字段。"""

    store_id: uuid.UUID
    name: str = Field(min_length=1, max_length=200)
    code: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{1,99}$")
    description: str | None = Field(default=None, max_length=1000)
    agent_type: AgentType = "service"
    enabled_tools: list[ToolName] = Field(default_factory=list, max_length=7)
    knowledge_scope: Literal["store_ready_faq"] = "store_ready_faq"
    knowledge_file_ids: list[uuid.UUID] = Field(default_factory=list, max_length=100)
    reply_profile: AgentReplyProfile | None = None

    model_config = {"extra": "forbid"}


class AgentConfigUpdate(BaseModel):
    """只允许运营人员修改展示信息和工具白名单。"""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    agent_type: AgentType | None = None
    enabled_tools: list[ToolName] | None = Field(default=None, max_length=7)
    knowledge_scope: Literal["store_ready_faq"] | None = None
    knowledge_file_ids: list[uuid.UUID] | None = Field(default=None, max_length=100)
    reply_profile: AgentReplyProfile | None = None

    model_config = {"extra": "forbid"}


class AgentRuntimeView(BaseModel):
    """从运行环境读取的 AI 配置，只读展示。"""

    available: bool
    llm_provider: str
    llm_model: str | None
    available_models: list[str] = Field(default_factory=list)
    embedding_provider: str
    embedding_model: str
    reranker_model: str
    prompt_versions: dict[str, str]
    auto_reply_threshold: float
    human_review_threshold: float
    token_streaming: Literal[False] = False


class AgentConfigView(BaseModel):
    id: uuid.UUID
    store_id: uuid.UUID
    name: str
    code: str
    description: str | None
    agent_type: AgentType
    status: Literal["enabled", "disabled"]
    enabled_tools: list[str]
    knowledge_file_ids: list[uuid.UUID]
    knowledge_scope: dict[str, object]
    reply_profile: AgentReplyProfile
    runtime: AgentRuntimeView
    created_at: datetime
    updated_at: datetime


class ToolCallLogView(BaseModel):
    id: uuid.UUID
    tool_name: str
    status: str
    error_code: str | None
    latency_ms: int | None
    mocked: bool


class AgentRunLogView(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    status: str
    action: str
    intent: str | None
    intent_confidence: float | None
    retrieval_score: float | None
    final_confidence: float | None
    model_provider: str
    model_name: str
    prompt_version: str | None
    latency_ms: int | None
    input_tokens: int | None
    output_tokens: int | None
    error_code: str | None
    trace_id: str | None
    legacy_unassigned: bool
    tool_calls: list[ToolCallLogView]
    created_at: datetime


class AgentRunLogPage(BaseModel):
    items: list[AgentRunLogView]
    page: int
    page_size: int
    total: int
