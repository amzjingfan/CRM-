"""持久批次的 HTTP 边界；确认只接受冻结预览编号。"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, JsonValue, field_validator


class BatchConfirmation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    preview_id: uuid.UUID
    confirmation: Literal[True]

    @field_validator("confirmation", mode="before")
    @classmethod
    def exact_confirmation(cls, value: object) -> object:
        if value is not True:
            raise ValueError("必须明确确认")
        return value


class BatchPagination(BaseModel):
    page: int
    page_size: int
    total: int
    total_pages: int


class BatchItemView(BaseModel):
    id: uuid.UUID
    store_id: uuid.UUID | None
    store_name: str
    status: str
    action: str | None
    agent_id: uuid.UUID | None
    result_agent_id: uuid.UUID | None
    old_published_version: int | None = None
    result_version: int | None
    error_code: str | None
    retryable: bool
    started_at: datetime | None
    finished_at: datetime | None
    attempt_count: int
    preview: JsonValue = None


class BatchSummary(BaseModel):
    id: uuid.UUID
    template_id: uuid.UUID
    template_version: int
    parent_batch_id: uuid.UUID | None
    status: str
    cancel_requested: bool
    counts: dict[str, int]
    created_at: datetime
    confirmed_at: datetime | None
    finished_at: datetime | None
    processor_enabled: bool


class BatchView(BatchSummary):
    items: list[BatchItemView]
    pagination: BatchPagination


class BatchListView(BaseModel):
    items: list[BatchSummary]
    pagination: BatchPagination
