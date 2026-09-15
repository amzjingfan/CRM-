"""知识证据 OpenAPI/Pydantic 契约测试。"""

import pytest
from pydantic import ValidationError

from app.knowledge_service.main import create_app
from app.knowledge_service.schemas import (
    ConflictReference,
    EvidenceItem,
    EvidenceSearchResponse,
    SearchStatus,
    StableReasonCode,
    UsagePolicy,
)


def test_openapi_exposes_versioned_evidence_path_and_both_security_headers() -> None:
    schema = create_app().openapi()
    operation = schema["paths"]["/internal/v1/evidence:search"]["post"]

    assert operation["responses"]["200"]["content"]["application/json"]["schema"]
    security_schemes = schema["components"]["securitySchemes"]
    assert "ApplicationBearer" in security_schemes
    assert security_schemes["ApplicationBearer"]["scheme"] == "bearer"
    assert security_schemes["ShopDelegation"]["name"] == "X-Shop-Delegation"


def test_ok_response_requires_versioned_evidence_and_usage_policy() -> None:
    item = EvidenceItem(
        content_version_id="kcv-001",
        content_sha256="a" * 64,
        chunk_id="chunk-001",
        text="Company-authored approved evidence.",
        source_id="src-001",
        source_url="https://seller-us.tiktok.com/university/example",
        platform_code="TK",
        market_code="US",
        language_tag="en-US",
        audience_code="internal_agent",
        space_code="company_shared",
        approval_ref="approval-001",
        effective_from="2026-09-15T00:00:00Z",
        index_generation_id="generation-001",
        dense_score=0.5,
        lexical_score=2.0,
        rrf_score=0.03,
        reranker_score=1.4,
        score_types={
            "dense": "cosine_similarity",
            "lexical": "ts_rank",
            "rrf": "reciprocal_rank_fusion",
            "reranker": "logit",
        },
        usage_policy=UsagePolicy(
            rights_basis_ref="RGT-TK-US-PUBLIC-001",
            allowed_app_refs=["crm-assistant"],
            allowed_space_codes=["company_shared"],
            external_model_allowed=False,
            automatic_delivery_allowed=False,
            forbidden_uses=["official_text_redistribution"],
        ),
    )

    response = EvidenceSearchResponse(
        status=SearchStatus.OK,
        request_id="req-001",
        trace_id="trace-001",
        index_generation_id="generation-001",
        retrieval_profile_version="retrieval-v1",
        evidence=[item],
    )

    assert response.evidence[0].usage_policy.automatic_delivery_allowed is False
    assert response.evidence[0].score_types["reranker"] == "logit"


@pytest.mark.parametrize(
    "invalid_response",
    [
        {"status": "ok", "request_id": "r", "trace_id": "t"},
        {"status": "conflict", "request_id": "r", "trace_id": "t", "reason_code": "ACTIVE_SOURCE_CONFLICT"},
        {"status": "no_evidence", "request_id": "r", "trace_id": "t", "reason_code": "DATABASE_UNAVAILABLE"},
    ],
)
def test_business_states_reject_incompatible_fields(invalid_response: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        EvidenceSearchResponse(**invalid_response)


def test_conflict_response_contains_no_winner() -> None:
    response = EvidenceSearchResponse(
        status=SearchStatus.CONFLICT,
        request_id="r",
        trace_id="t",
        reason_code=StableReasonCode.ACTIVE_SOURCE_CONFLICT,
        conflicts=[ConflictReference(conflict_ref="conflict-001", review_ref="review-queue-001")],
    )

    assert response.evidence == []
    assert not hasattr(response.conflicts[0], "winner")
