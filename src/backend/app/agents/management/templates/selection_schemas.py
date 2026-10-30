"""批量向导只暴露授权选择信息与来源摘要。"""

import uuid

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from app.agents.management.templates.batch_schemas import BatchPagination


class ApplicationAgentOption(BaseModel):
    id: uuid.UUID
    name: str
    code: str
    template_id: uuid.UUID | None
    draft_revision: int
    published_version: int | None
    status: str


class ApplicationStoreOption(BaseModel):
    id: uuid.UUID
    name: str
    code: str
    can_view_knowledge: bool
    agents: list[ApplicationAgentOption]


class ApplicationStorePage(BaseModel):
    items: list[ApplicationStoreOption]
    pagination: BatchPagination


class KnowledgeFileOption(BaseModel):
    id: uuid.UUID
    name: str
    active_version_number: int | None
    status: str | None
    publication_approval: str | None
    can_publish: bool


class KnowledgeFileOptionPage(BaseModel):
    items: list[KnowledgeFileOption]
    pagination: BatchPagination


class TemplateFieldSource(BaseModel):
    field: str
    local_override: bool
    applied_template_version: int | None
    last_reviewed_template_version: int | None
    aligned: bool
    pending_review: bool


class DraftTemplateSource(BaseModel):
    template_id: uuid.UUID
    name: str
    archived: bool
    target_template_version: int
    draft_revision: int
    fields: list[TemplateFieldSource]
    aligned_count: int
    local_override_count: int
    pending_review_count: int


class PublishedTemplateSource(BaseModel):
    version: int
    template_source_json: dict[str, JsonValue] | None


class AgentTemplateSourceView(BaseModel):
    agent_id: uuid.UUID
    store_id: uuid.UUID
    draft: DraftTemplateSource | None
    published: PublishedTemplateSource | None


class DetachTemplateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1, strict=True)
