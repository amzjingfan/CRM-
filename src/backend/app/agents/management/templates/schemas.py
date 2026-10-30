"""模板仅接收通用配置，店铺文件、凭证及运行策略不进入此边界。"""

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator, model_serializer, model_validator

from app.agents.management.schemas import AgentType
from app.agents.prompts.sections import SECTION_TITLES
from app.agents.tools.metadata import TOOL_METADATA


class KnowledgeSlot(BaseModel):
    """稳定槽键用于逐店映射，不携带实际文件或审批结果。"""

    model_config = ConfigDict(extra="forbid", strict=True)

    key: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    name: str = Field(min_length=1, max_length=200)
    purpose: str = Field(min_length=1, max_length=1000)
    required: bool = False


class TemplateConfig(BaseModel):
    """草稿允许未填写模型和七段；发布阶段另做完整编译及语义复核。"""

    model_config = ConfigDict(extra="forbid", strict=True)

    default_agent_name: str = Field(min_length=1, max_length=200)
    suggested_code: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{1,99}$")
    agent_type: AgentType = "service"
    description: str | None = Field(default=None, max_length=1000)
    model_provider: str | None = Field(default=None, max_length=50)
    model_name: str | None = Field(default=None, max_length=150)
    prompt_sections: dict[str, str] = Field(default_factory=dict)
    tool_names: list[str] = Field(default_factory=list)
    knowledge_slots: list[KnowledgeSlot] = Field(default_factory=list, max_length=100)

    @field_validator("prompt_sections")
    @classmethod
    def known_prompt_sections(cls, value: dict[str, str]) -> dict[str, str]:
        if set(value) - {key for key, _ in SECTION_TITLES}:
            raise ValueError("系统提示词包含未知段落")
        if any(len(section) > 4000 for section in value.values()):
            raise ValueError("系统提示词段落超过长度限制")
        return value

    @field_validator("tool_names")
    @classmethod
    def known_tools(cls, value: list[str]) -> list[str]:
        if any(name not in TOOL_METADATA for name in value):
            raise ValueError("工具名称未知")
        return value

    @field_validator("knowledge_slots")
    @classmethod
    def unique_slot_keys(cls, value: list[KnowledgeSlot]) -> list[KnowledgeSlot]:
        if len({slot.key for slot in value}) != len(value):
            raise ValueError("知识需求槽键不能重复")
        return value


DiffStatus = Literal["unchanged", "template_changed", "local_changed", "converged", "conflict"]
DiffChoice = Literal["skip", "template", "local", "resolve"]


class FieldDiff(BaseModel):
    """三方值及默认建议；建议不替代用户的准确确认。"""

    model_config = ConfigDict(extra="forbid", strict=True)

    field: str
    baseline: JsonValue
    local: JsonValue
    target: JsonValue
    status: DiffStatus
    default_choice: DiffChoice


class FieldDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    choice: Literal["template", "local", "manual"]
    value: JsonValue = None

    @model_serializer
    def serialize_decision(self) -> dict[str, JsonValue]:
        # 可持久化往返；非手工选择不输出会被输入边界拒绝的 value:null。
        result: dict[str, JsonValue] = {"choice": self.choice}
        if self.choice == "manual":
            result["value"] = self.value
        return result

    @model_validator(mode="after")
    def explicit_manual_value(self) -> "FieldDecision":
        if self.choice == "manual" and "value" not in self.model_fields_set:
            raise ValueError("手工选择必须提供完整字段值")
        if self.choice != "manual" and "value" in self.model_fields_set:
            raise ValueError("仅手工选择接收字段值")
        return self


class ApplicationItemRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    store_id: uuid.UUID
    action: Literal["create", "adopt", "update"]
    agent_id: uuid.UUID | None = None
    expected_revision: int | None = Field(default=None, ge=1, strict=True)
    fields: dict[str, FieldDecision] | None = None
    knowledge_mappings: dict[str, list[uuid.UUID]] = Field(default_factory=dict, max_length=100)
    unbind_removed_file_ids: list[uuid.UUID] = Field(default_factory=list, max_length=100)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    code: str | None = Field(default=None, pattern=r"^[a-z0-9][a-z0-9_-]{1,99}$")
    include_existing_draft: bool = False
    publish: bool = False
    enable_after_publish: bool = False

    @field_validator("fields")
    @classmethod
    def known_fields(cls, value: dict[str, FieldDecision] | None) -> dict[str, FieldDecision] | None:
        keys = {"agent_type", "description", "model", "tool_names", "knowledge_slots"} | {
            f"prompt_sections.{key}" for key, _ in SECTION_TITLES
        }
        if value is not None and set(value) - keys:
            raise ValueError("未知管理字段")
        return value

    @model_validator(mode="after")
    def action_target(self) -> "ApplicationItemRequest":
        if self.action == "create" and (self.agent_id is not None or self.expected_revision is not None):
            raise ValueError("创建不能指定已有 Agent")
        if self.action != "create" and (self.agent_id is None or self.expected_revision is None):
            raise ValueError("关联或更新必须指定 Agent 及准确 revision")
        if self.action != "create" and (self.name is not None or self.code is not None):
            raise ValueError("名称与编码只用于创建")
        if self.enable_after_publish and (self.action != "create" or not self.publish):
            raise ValueError("仅显式发布新 Agent 时可以启用")
        return self


class ApplicationPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    template_version: int = Field(ge=1, strict=True)
    items: list[ApplicationItemRequest] = Field(min_length=1)
    parent_batch_id: uuid.UUID | None = None

    @field_validator("items")
    @classmethod
    def unique_stores(cls, value: list[ApplicationItemRequest]) -> list[ApplicationItemRequest]:
        if len({item.store_id for item in value}) != len(value):
            raise ValueError("每店只能有一个应用项目")
        return value


class ApplicationIssue(BaseModel):
    code: str
    message: str
    field: str | None = None


class ApplicationItemView(BaseModel):
    id: uuid.UUID
    store_id: uuid.UUID
    store_name: str
    agent_id: uuid.UUID | None
    action: Literal["create", "adopt", "update"]
    valid: bool
    issues: list[ApplicationIssue]
    warnings: list[ApplicationIssue]
    diffs: list[FieldDiff]
    published_snapshot: dict[str, JsonValue] | None
    full_target: dict[str, JsonValue]
    knowledge_slots: list[KnowledgeSlot]
    mappings: dict[str, list[str]]
    has_existing_draft: bool
    field_choices: dict[str, FieldDecision]
    flags: dict[str, bool]
    request: ApplicationItemRequest | None = None


class ApplicationPreviewView(BaseModel):
    preview_id: uuid.UUID
    preview_hash: str
    template_id: uuid.UUID
    template_version: int
    items: list[ApplicationItemView]
