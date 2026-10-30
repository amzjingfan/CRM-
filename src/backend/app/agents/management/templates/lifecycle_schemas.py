"""共享模板生命周期 HTTP 契约，与店铺应用契约分开。"""

import uuid
from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.agents.management.templates.schemas import KnowledgeSlot, TemplateConfig
from app.agents.tools.metadata import Operation, ToolGroup


class TemplateCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{1,99}$")
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    config: TemplateConfig = Field(
        default_factory=lambda: TemplateConfig(default_agent_name="草稿", suggested_code="draft")
    )

    @model_validator(mode="after")
    def default_creation_config(self) -> Self:
        if "config" not in self.model_fields_set:
            self.config = TemplateConfig(default_agent_name=self.name, suggested_code=self.code)
        return self


class TemplateRevision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=1, strict=True)


class TemplateUpdate(TemplateRevision):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    config: TemplateConfig | None = None

    @model_validator(mode="after")
    def non_null_changes(self) -> Self:
        if any(field in self.model_fields_set and getattr(self, field) is None for field in ("name", "config")):
            raise ValueError("名称和配置不能为null")
        return self


class TemplateFromAgent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{1,99}$")
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    source_agent_id: uuid.UUID
    source_version: int | None = Field(default=None, ge=1, strict=True)
    source_draft_revision: int | None = Field(default=None, ge=1, strict=True)
    knowledge_slots: list[KnowledgeSlot] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def exact_source(self) -> Self:
        if (self.source_version is None) == (self.source_draft_revision is None):
            raise ValueError("必须且只能选择一个源版本或草稿revision")
        if len({slot.key for slot in self.knowledge_slots}) != len(self.knowledge_slots):
            raise ValueError("知识需求槽键不能重复")
        return self


class TemplateView(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    description: str | None
    draft_revision: int | None
    published_version: int | None
    archived_at: datetime | None
    config: TemplateConfig | None
    published_config: TemplateConfig | None
    can_manage: bool
    linked_store_count: int
    update_count: int
    created_at: datetime
    updated_at: datetime


class TemplateListView(BaseModel):
    items: list[TemplateView]
    can_manage: bool


class TemplateVersionView(BaseModel):
    version: int
    config: TemplateConfig
    content_sha256: str
    published_at: datetime


class TemplatePromptSection(BaseModel):
    key: str
    title: str


class TemplateCatalogTool(BaseModel):
    name: str
    title: str
    description: str
    category: str
    operation: Operation
    requires_context: bool


class TemplateCatalogView(BaseModel):
    model_options: list[dict[str, str]]
    prompt_sections: list[TemplatePromptSection]
    groups: list[ToolGroup]
    tools: list[TemplateCatalogTool]
