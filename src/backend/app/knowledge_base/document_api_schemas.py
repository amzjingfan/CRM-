"""通用文件管理接口的低敏摘要和授权复核数据。"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.knowledge_base.document_schemas import DocumentIndexConfig
from app.knowledge_base.schemas import KnowledgeCustomerScope, KnowledgeStatementType


class DocumentVersionSummary(BaseModel):
    id: uuid.UUID
    version_number: int
    status: str
    error_code: str | None
    retry_count: int
    created_at: datetime
    completed_at: datetime | None
    is_active: bool
    chunk_count: int
    approval_status: str = "draft"
    statement_type: str = "unknown"
    customer_scope: str = "none"


class DocumentVersionApproval(BaseModel):
    statement_type: KnowledgeStatementType
    customer_scope: KnowledgeCustomerScope


class DocumentFileSummary(BaseModel):
    id: uuid.UUID
    store_id: uuid.UUID
    category_id: uuid.UUID | None
    filename: str
    active_version_number: int | None
    archived_at: datetime | None
    latest_version: DocumentVersionSummary


class DocumentFileCategoryUpdate(BaseModel):
    category_id: uuid.UUID


class DocumentFilePage(BaseModel):
    items: list[DocumentFileSummary]
    total: int
    page: int
    page_size: int


class DocumentFileDetail(DocumentFileSummary):
    versions: list[DocumentVersionSummary]


class DocumentUnitView(BaseModel):
    unit_index: int
    unit_kind: str
    source_locator: dict[str, int]
    raw_text: str
    cleaned_text: str
    issue_codes: list[str]
    needs_review: bool
    parse_mode: str
    reviewed_by: uuid.UUID | None
    reviewed_at: datetime | None


class DocumentVersionDetail(DocumentVersionSummary):
    file_id: uuid.UUID
    filename: str
    file_sha256: str
    config: DocumentIndexConfig
    parser_version: str | None
    cleaning_version: str
    units: list[DocumentUnitView]


class DocumentImportAccepted(BaseModel):
    file_id: uuid.UUID
    version_id: uuid.UUID
    version_number: int
    status: str


class DocumentUnitReview(BaseModel):
    corrected_text: str = Field(min_length=1, max_length=200_000)
    confirmed: Literal[True]
