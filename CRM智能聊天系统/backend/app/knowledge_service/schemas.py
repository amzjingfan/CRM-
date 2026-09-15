"""内部证据检索 API 的版本化 Pydantic 契约。"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, HttpUrl, model_validator


class SearchStatus(StrEnum):
    OK = "ok"
    NO_EVIDENCE = "no_evidence"
    CONFLICT = "conflict"
    UNAVAILABLE = "unavailable"


class StableReasonCode(StrEnum):
    NO_CURRENT_APPROVED_EVIDENCE = "NO_CURRENT_APPROVED_EVIDENCE"
    NO_SCOPE_MATCH = "NO_SCOPE_MATCH"
    NO_ELIGIBLE_EVIDENCE = "NO_ELIGIBLE_EVIDENCE"
    ACTIVE_SOURCE_CONFLICT = "ACTIVE_SOURCE_CONFLICT"
    INDEX_GENERATION_UNAVAILABLE = "INDEX_GENERATION_UNAVAILABLE"
    INDEX_VERSION_DRIFT = "INDEX_VERSION_DRIFT"
    CONTENT_METADATA_INVALID = "CONTENT_METADATA_INVALID"
    EMBEDDING_UNAVAILABLE = "EMBEDDING_UNAVAILABLE"
    RERANKER_UNAVAILABLE = "RERANKER_UNAVAILABLE"
    DATABASE_UNAVAILABLE = "DATABASE_UNAVAILABLE"


class EvidenceSearchRequest(BaseModel):
    """查询范围只能缩小授权，不能授予权限。"""

    request_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9._:-]+$")
    query: str = Field(min_length=1, max_length=4000)
    platform_code: str = Field(min_length=1, max_length=32)
    market_code: str = Field(min_length=2, max_length=16)
    language_tag: str = Field(min_length=2, max_length=32)
    audience_code: str = Field(min_length=1, max_length=64)
    requested_space_codes: list[str] = Field(min_length=1, max_length=2)
    shop_ref: str | None = Field(default=None, min_length=1, max_length=128)
    top_k: int = Field(default=5, ge=1, le=20)

    @model_validator(mode="after")
    def validate_spaces(self) -> EvidenceSearchRequest:
        allowed = {"company_shared", "shop_private"}
        spaces = set(self.requested_space_codes)
        if len(spaces) != len(self.requested_space_codes) or not spaces <= allowed:
            raise ValueError("requested_space_codes contains duplicate or unsupported space")
        if spaces == {"company_shared"} and self.shop_ref is not None:
            raise ValueError("company_shared request must not include shop_ref")
        if spaces != {"company_shared"} and (spaces != {"shop_private"} or self.shop_ref is None):
            raise ValueError("shop_private request requires an exclusive shop_ref scope")
        return self


class UsagePolicy(BaseModel):
    rights_basis_ref: str
    allowed_app_refs: list[str]
    allowed_space_codes: list[str]
    external_model_allowed: bool
    automatic_delivery_allowed: bool
    forbidden_uses: list[str]


class EvidenceItem(BaseModel):
    content_version_id: str
    content_sha256: str = Field(pattern=r"^[a-fA-F0-9]{64}$")
    chunk_id: str
    text: str
    source_id: str
    source_url: HttpUrl
    platform_code: str
    market_code: str
    language_tag: str
    audience_code: str
    space_code: str
    shop_ref: str | None = None
    approval_ref: str
    effective_from: datetime
    effective_until: datetime | None = None
    index_generation_id: str
    dense_score: float
    lexical_score: float
    rrf_score: float
    reranker_score: float
    score_types: dict[str, str]
    usage_policy: UsagePolicy


class ConflictReference(BaseModel):
    """只提供低敏冲突组和人工处理引用，不返回胜者。"""

    conflict_ref: str
    review_ref: str


class EvidenceSearchResponse(BaseModel):
    status: SearchStatus
    request_id: str
    trace_id: str
    index_generation_id: str | None = None
    retrieval_profile_version: str | None = None
    evidence: list[EvidenceItem] = Field(default_factory=list)
    conflicts: list[ConflictReference] = Field(default_factory=list)
    reason_code: StableReasonCode | None = None
    retryable: bool | None = None

    @model_validator(mode="after")
    def validate_state_envelope(self) -> EvidenceSearchResponse:
        no_evidence_reasons = {
            StableReasonCode.NO_CURRENT_APPROVED_EVIDENCE,
            StableReasonCode.NO_SCOPE_MATCH,
            StableReasonCode.NO_ELIGIBLE_EVIDENCE,
        }
        technical_reasons = {
            StableReasonCode.INDEX_GENERATION_UNAVAILABLE,
            StableReasonCode.INDEX_VERSION_DRIFT,
            StableReasonCode.CONTENT_METADATA_INVALID,
            StableReasonCode.EMBEDDING_UNAVAILABLE,
            StableReasonCode.RERANKER_UNAVAILABLE,
            StableReasonCode.DATABASE_UNAVAILABLE,
        }
        if self.status is SearchStatus.OK:
            if (
                not self.evidence
                or not self.index_generation_id
                or not self.retrieval_profile_version
                or self.conflicts
                or self.reason_code is not None
                or self.retryable is not None
            ):
                raise ValueError("ok response requires versioned evidence only")
        elif self.status is SearchStatus.NO_EVIDENCE:
            if (
                self.reason_code not in no_evidence_reasons
                or self.evidence
                or self.conflicts
                or self.retryable is not None
            ):
                raise ValueError("no_evidence response has incompatible fields")
        elif self.status is SearchStatus.CONFLICT:
            if (
                self.reason_code is not StableReasonCode.ACTIVE_SOURCE_CONFLICT
                or not self.conflicts
                or self.evidence
                or self.retryable is not None
            ):
                raise ValueError("conflict response requires unresolved conflict references")
        elif self.reason_code not in technical_reasons or self.evidence or self.conflicts or self.retryable is None:
            raise ValueError("unavailable response requires a technical reason and retryable flag")
        return self


class ApiErrorBody(BaseModel):
    code: str
    message: str


class ApiErrorResponse(BaseModel):
    error: ApiErrorBody
    trace_id: str
