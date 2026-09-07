"""知识库公开接口与 AI 交接类型。"""

import math
import uuid
from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class KnowledgeStatementType(StrEnum):
    """知识正文的权威语义类型；不得由模型或向量化任务自行推断。"""

    POLICY = "policy"
    TECHNICAL_ARTIFACT = "technical_artifact"
    CUSTOMER_INSTANCE_FACT = "customer_instance_fact"
    NON_ASSERTIVE_PROPOSITION = "non_assertive_proposition"
    UNKNOWN = "unknown"


class KnowledgeCustomerScope(StrEnum):
    """知识是否指向具体客户实例。"""

    NONE = "none"
    GENERIC = "generic"
    SPECIFIC_CUSTOMER = "specific_customer"


class KnowledgePublicationApproval(StrEnum):
    """当前文档版本的人工审批级别。"""

    DRAFT = "draft"
    APPROVED_FOR_INTERNAL_REVIEW = "approved_for_internal_review"
    APPROVED_FOR_PUBLIC_REPLY = "approved_for_public_reply"


class KnowledgeSafetyMetadata(BaseModel):
    """从知识文档权威字段复制到检索命中的不可提升安全元数据。"""

    statement_type: KnowledgeStatementType = KnowledgeStatementType.UNKNOWN
    customer_scope: KnowledgeCustomerScope = KnowledgeCustomerScope.NONE
    publication_approval: KnowledgePublicationApproval = KnowledgePublicationApproval.DRAFT
    semantic_schema_version: Literal[1] = 1
    approved_by: uuid.UUID | None = None
    approved_at: datetime | None = None
    store_id: uuid.UUID
    document_version: int = Field(ge=1)
    approved_document_version: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_approval(self) -> "KnowledgeSafetyMetadata":
        """批准记录必须绑定审批人、时间、店铺和当前文档版本。"""
        approved = self.publication_approval != KnowledgePublicationApproval.DRAFT
        if approved != (self.approved_by is not None and self.approved_at is not None):
            raise ValueError("知识审批状态与审批人、审批时间不一致")
        if approved and self.statement_type == KnowledgeStatementType.UNKNOWN:
            raise ValueError("未知语义类型不能获得发布审批")
        if approved and self.document_version != self.approved_document_version:
            raise ValueError("知识审批只对当前文档版本有效")
        if (
            self.statement_type == KnowledgeStatementType.TECHNICAL_ARTIFACT
            and self.customer_scope != KnowledgeCustomerScope.NONE
        ):
            raise ValueError("技术资产不能绑定客户范围")
        if (
            self.statement_type
            in {
                KnowledgeStatementType.POLICY,
                KnowledgeStatementType.NON_ASSERTIVE_PROPOSITION,
            }
            and self.customer_scope == KnowledgeCustomerScope.SPECIFIC_CUSTOMER
        ):
            raise ValueError("政策或非断言命题不能绑定具体客户")
        return self

    @classmethod
    def unapproved(
        cls,
        *,
        store_id: uuid.UUID,
        document_version: int,
    ) -> "KnowledgeSafetyMetadata":
        """把缺失、损坏或旧格式元数据统一降级为不可使用状态。"""
        return cls(
            store_id=store_id,
            document_version=document_version,
            approved_document_version=document_version,
        )


class CategoryCreate(BaseModel):
    """创建 FAQ 分类。"""

    store_id: uuid.UUID
    parent_id: uuid.UUID | None = None
    name: str = Field(min_length=1, max_length=100)
    code: str = Field(pattern=r"^[A-Za-z0-9_-]+$", min_length=1, max_length=100)
    sort_order: int = Field(default=0, ge=0, le=100_000)


class CategoryUpdate(BaseModel):
    """更新分类的可编辑字段。"""

    parent_id: uuid.UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=100)
    sort_order: int | None = Field(default=None, ge=0, le=100_000)
    status: Literal["active", "disabled"] | None = None


class CategoryView(BaseModel):
    """分类展示结构。"""

    id: uuid.UUID
    store_id: uuid.UUID
    parent_id: uuid.UUID | None
    name: str
    code: str
    layer: str
    sort_order: int
    status: str

    model_config = {"from_attributes": True}


class KnowledgeEntryCreate(BaseModel):
    """创建 FAQ 条目。"""

    store_id: uuid.UUID
    category_id: uuid.UUID | None = None
    question: str = Field(min_length=1, max_length=4000)
    answer: str = Field(min_length=1, max_length=20_000)
    source: str | None = Field(default=None, max_length=200)
    tags: list[str] = Field(default_factory=list, max_length=30)
    statement_type: KnowledgeStatementType = KnowledgeStatementType.UNKNOWN
    customer_scope: KnowledgeCustomerScope = KnowledgeCustomerScope.NONE

    @model_validator(mode="after")
    def validate_semantic_scope(self) -> "KnowledgeEntryCreate":
        """创建时就拒绝与语义类型冲突的客户范围。"""
        KnowledgeSafetyMetadata(
            statement_type=self.statement_type,
            customer_scope=self.customer_scope,
            store_id=self.store_id,
            document_version=1,
            approved_document_version=1,
        )
        return self


class KnowledgeEntryUpdate(BaseModel):
    """更新 FAQ；正文变化会使旧向量立即失效。"""

    category_id: uuid.UUID | None = None
    question: str | None = Field(default=None, min_length=1, max_length=4000)
    answer: str | None = Field(default=None, min_length=1, max_length=20_000)
    source: str | None = Field(default=None, max_length=200)
    tags: list[str] | None = Field(default=None, max_length=30)
    statement_type: KnowledgeStatementType | None = None
    customer_scope: KnowledgeCustomerScope | None = None


class KnowledgeEntryView(BaseModel):
    """FAQ 条目展示结构。"""

    id: uuid.UUID
    store_id: uuid.UUID
    category_id: uuid.UUID | None
    question: str
    answer: str
    source: str | None
    tags: list[str]
    status: str
    vectorization_status: str
    document_version: int
    usage_count: int
    satisfaction_rate: float | None
    statement_type: KnowledgeStatementType
    customer_scope: KnowledgeCustomerScope
    publication_approval: KnowledgePublicationApproval
    semantic_schema_version: Literal[1]
    approved_by: uuid.UUID | None
    approved_at: datetime | None
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class KnowledgePage(BaseModel):
    """FAQ 稳定页码分页结果。"""

    items: list[KnowledgeEntryView]
    page: int
    page_size: int
    total: int


class VectorizationCounts(BaseModel):
    """店铺内已发布 FAQ 的向量化状态计数。"""

    pending: int = Field(default=0, ge=0)
    processing: int = Field(default=0, ge=0)
    ready: int = Field(default=0, ge=0)
    failed: int = Field(default=0, ge=0)


class KnowledgeVectorizationStatus(BaseModel):
    """供知识库运营页面展示的低敏向量化运行状态。"""

    store_id: uuid.UUID
    worker_enabled: bool
    provider: Literal["local_bge"]
    model: str
    dimensions: Literal[1024]
    counts: VectorizationCounts


class ImportAccepted(BaseModel):
    """异步导入受理结果。"""

    job_id: uuid.UUID
    status: Literal["pending"]


class ImportJobView(BaseModel):
    """导入任务进度；错误只包含行号和稳定错误码。"""

    id: uuid.UUID
    store_id: uuid.UUID
    original_filename: str
    status: str
    total_rows: int
    succeeded_rows: int
    failed_rows: int
    error_summary: list[dict[str, object]]
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class VectorChunkInput(BaseModel):
    """AI 工程师写入的已校验向量切片。"""

    chunk_index: int = Field(ge=0)
    content: str = Field(min_length=1, max_length=20_000)
    token_count: int = Field(ge=1)
    embedding: list[float]
    metadata: dict[str, object] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_dimension(self) -> "VectorChunkInput":
        """固定 BGE-M3 1024 维，避免新旧 Provider 向量混写。"""
        if len(self.embedding) != 1024:
            raise ValueError("embedding 必须为 1024 维")
        if any(not math.isfinite(value) for value in self.embedding):
            raise ValueError("embedding 不能包含 NaN 或 Infinity")
        return self


class KnowledgeRetrievalHit(BaseModel):
    """知识端口返回给 Agent 的租户安全引用结果。"""

    document_id: uuid.UUID
    chunk_id: uuid.UUID
    category_id: uuid.UUID | None
    document_version: int = Field(ge=1)
    chunk_index: int = Field(ge=0)
    content: str = Field(min_length=1, max_length=20_000)
    token_count: int = Field(ge=1)
    # score 保持为 0-1 Dense cosine 分数，继续供工作流置信度使用；
    # RRF 和 Reranker 原始分数只参与排序，未经评测不得冒充概率。
    score: float = Field(ge=0, le=1)
    dense_score: float = Field(default=0, ge=0, le=1)
    lexical_score: float = Field(default=0, ge=0, le=1)
    fusion_score: float = Field(default=0, ge=0, le=1)
    reranker_score: float | None = None
    source_label: str = Field(min_length=1, max_length=500)
    safety_metadata: KnowledgeSafetyMetadata
