"""Agent 运营管理公开类型。"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.agents.core.reply_policy import AgentReplyProfile
from app.agents.core.schemas import AgentCitation, AgentToolCallView
from app.agents.core.translation import TranslationBundleResult
from app.agents.tools.metadata import TOOL_METADATA

AgentType = Literal["service", "operations"]


class AgentConfigCreate(BaseModel):
    """创建店铺运营配置；AI 内部配置不属于可写字段。"""

    store_id: uuid.UUID
    name: str = Field(min_length=1, max_length=200)
    code: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{1,99}$")
    description: str | None = Field(default=None, max_length=1000)
    agent_type: AgentType = "service"
    enabled_tools: list[str] = Field(default_factory=list)
    model_provider: str | None = Field(default=None, max_length=50)
    model_name: str | None = Field(default=None, max_length=150)
    prompt_sections: dict[str, str] = Field(default_factory=dict)
    knowledge_scope: Literal["bound_files_only"] = "bound_files_only"
    knowledge_file_ids: list[uuid.UUID] = Field(default_factory=list, max_length=100)
    reply_profile: AgentReplyProfile | None = None

    model_config = {"extra": "forbid"}

    @field_validator("enabled_tools")
    @classmethod
    def known_tools(cls, value: list[str] | None) -> list[str] | None:
        if value is not None and any(name not in TOOL_METADATA for name in value):
            raise ValueError("工具名称未知")
        return value

    @field_validator("knowledge_scope", mode="before")
    @classmethod
    def normalize_legacy_scope(cls, value: object) -> object:
        return "bound_files_only" if value == "store_ready_faq" else value


class AgentConfigUpdate(BaseModel):
    """只允许运营人员修改展示信息和工具白名单。"""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    agent_type: AgentType | None = None
    enabled_tools: list[str] | None = None
    model_provider: str | None = Field(default=None, max_length=50)
    model_name: str | None = Field(default=None, max_length=150)
    prompt_sections: dict[str, str] | None = None
    knowledge_scope: Literal["bound_files_only"] | None = None
    knowledge_file_ids: list[uuid.UUID] | None = Field(default=None, max_length=100)
    reply_profile: AgentReplyProfile | None = None
    expected_revision: int | None = Field(default=None, ge=1)

    model_config = {"extra": "forbid"}

    @field_validator("enabled_tools")
    @classmethod
    def known_tools(cls, value: list[str] | None) -> list[str] | None:
        if value is not None and any(name not in TOOL_METADATA for name in value):
            raise ValueError("工具名称未知")
        return value

    @field_validator("knowledge_scope", mode="before")
    @classmethod
    def normalize_legacy_scope(cls, value: object) -> object:
        # 旧客户端字面值只作为输入别名，运行时没有整店 FAQ 读取能力。
        return "bound_files_only" if value == "store_ready_faq" else value


class AgentPublishRequest(BaseModel):
    """乐观锁发布当前草稿。"""

    expected_revision: int = Field(ge=1)

    model_config = {"extra": "forbid"}


class AgentRuntimeView(BaseModel):
    """从运行环境读取的 AI 配置，只读展示。"""

    available: bool
    llm_provider: str
    llm_model: str | None
    available_models: list[str] = Field(default_factory=list)
    model_options: list[dict[str, str]] = Field(default_factory=list)
    embedding_provider: str
    embedding_model: str
    reranker_model: str
    prompt_versions: dict[str, str]
    auto_reply_threshold: float
    human_review_threshold: float
    token_streaming: Literal[True] = True


class AgentDebugRequest(BaseModel):
    """输入只用于当前调试调用；会话 ID 仅提供可信只读工具上下文。"""

    message: str = Field(min_length=1, max_length=4000)
    conversation_id: uuid.UUID | None = None
    mode: Literal["single", "store"] = "single"

    model_config = {"extra": "forbid"}

    @field_validator("message")
    @classmethod
    def non_blank_message(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("调试消息不能为空")
        return stripped


class AgentDebugView(BaseModel):
    agent_run_id: uuid.UUID
    content: str | None
    action: str
    terminal_state: str
    citations: list[AgentCitation]
    tool_calls: list[AgentToolCallView]
    trace_id: str
    send_performed: Literal[False] = False
    routed_agents: list[dict[str, str]] = Field(default_factory=list)
    tool_events: list[dict[str, str]] = Field(default_factory=list)
    reason_code: str | None = None
    customer_translation: TranslationBundleResult | None = None
    customer_translation_error_code: str | None = None


class AgentConfigView(BaseModel):
    id: uuid.UUID
    store_id: uuid.UUID
    name: str
    code: str
    description: str | None
    agent_type: AgentType
    status: Literal["enabled", "disabled"]
    draft_revision: int = 1
    published_version: int | None = None
    template_id: uuid.UUID | None = None
    template_state_json: dict[str, object] | None = None
    published_template_source_json: dict[str, object] | None = None
    model_provider: str | None = None
    model_name: str | None = None
    prompt_sections: dict[str, str] = Field(default_factory=dict)
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
    parent_run_id: uuid.UUID | None = None
    config_version: int | None = None
    phase: str | None = None
    conversation_id: uuid.UUID | None
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
