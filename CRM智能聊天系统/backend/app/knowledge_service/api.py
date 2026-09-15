"""知识证据内部 HTTP API。"""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import Annotated

from fastapi import FastAPI, Request, Security
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

from app.knowledge_service.auth import AuthenticationRejected, TokenVerifier
from app.knowledge_service.authorization import AuthorityUnavailable, AuthorizationRejected, KnowledgeAuthorizer
from app.knowledge_service.config import KnowledgeServiceSettings
from app.knowledge_service.errors import error_response
from app.knowledge_service.schemas import (
    ApiErrorResponse,
    EvidenceSearchRequest,
    EvidenceSearchResponse,
    SearchStatus,
    StableReasonCode,
)
from app.knowledge_service.service import (
    AuditRecord,
    AuditSink,
    EvidenceSearcher,
    EvidenceSearchRequestContext,
    hash_shop_ref,
)

application_bearer = HTTPBearer(auto_error=False, scheme_name="ApplicationBearer")
shop_delegation = APIKeyHeader(name="X-Shop-Delegation", auto_error=False, scheme_name="ShopDelegation")
ApplicationCredential = Annotated[
    HTTPAuthorizationCredentials | None,
    Security(application_bearer),
]
DelegationCredential = Annotated[str | None, Security(shop_delegation)]


def install_evidence_api(
    application: FastAPI,
    *,
    settings: KnowledgeServiceSettings,
    verifier: TokenVerifier,
    authorizer: KnowledgeAuthorizer,
    searcher: EvidenceSearcher,
    audit_sink: AuditSink,
) -> None:
    """将可注入的身份、授权、检索和审计端口挂载到独立应用。"""

    @application.exception_handler(AuthorityUnavailable)
    async def authority_unavailable_handler(request: Request, error: AuthorityUnavailable) -> JSONResponse:
        del request, error
        return error_response(
            503,
            "AUTHORITY_UNAVAILABLE",
            "authorization or mandatory audit authority unavailable",
            str(uuid.uuid4()),
        )

    @application.post(
        "/internal/v1/evidence:search",
        response_model=EvidenceSearchResponse,
        responses={
            401: {"model": ApiErrorResponse},
            403: {"model": ApiErrorResponse},
            503: {"model": ApiErrorResponse},
        },
    )
    async def search_evidence(
        request: EvidenceSearchRequest,
        application_credential: ApplicationCredential,
        delegation_header: DelegationCredential,
    ) -> EvidenceSearchResponse:
        trace_id = str(uuid.uuid4())
        started = time.perf_counter()
        if application_credential is None or application_credential.scheme.lower() != "bearer":
            await _record_or_raise(
                audit_sink,
                _audit_record(request, trace_id, started, "rejected", "TOKEN_INVALID"),
                trace_id,
            )
            return error_response(401, "TOKEN_INVALID", "application credential is required", trace_id)  # type: ignore[return-value]
        try:
            identity = verifier.verify_application(application_credential.credentials)
            delegation = None
            if delegation_header is not None:
                delegation = verifier.verify_delegation(_extract_bearer(delegation_header))
        except AuthenticationRejected as error:
            await _record_or_raise(
                audit_sink,
                _audit_record(request, trace_id, started, "rejected", error.reason_code),
                trace_id,
            )
            return error_response(401, error.reason_code, "credential rejected", trace_id)  # type: ignore[return-value]

        try:
            authorization = await asyncio.wait_for(
                authorizer.authorize(
                    application_identity=identity,
                    delegation_identity=delegation,
                    requested_space_codes=frozenset(request.requested_space_codes),
                    shop_ref=request.shop_ref,
                    platform_code=request.platform_code,
                    market_code=request.market_code,
                    language_tag=request.language_tag,
                    audience_code=request.audience_code,
                ),
                timeout=settings.authority_timeout_seconds,
            )
        except AuthorizationRejected as error:
            await _record_or_raise(
                audit_sink,
                _audit_record(
                    request,
                    trace_id,
                    started,
                    "rejected",
                    error.reason_code,
                    application_ref=identity.application_ref,
                    jti_hash=identity.jti_hash,
                ),
                trace_id,
            )
            return error_response(error.http_status, error.reason_code, "request is not authorized", trace_id)  # type: ignore[return-value]
        except (AuthorityUnavailable, TimeoutError):
            await _record_or_raise(
                audit_sink,
                _audit_record(
                    request,
                    trace_id,
                    started,
                    "unavailable",
                    "AUTHORITY_UNAVAILABLE",
                    application_ref=identity.application_ref,
                    jti_hash=identity.jti_hash,
                ),
                trace_id,
            )
            return error_response(503, "AUTHORITY_UNAVAILABLE", "authorization authority unavailable", trace_id)  # type: ignore[return-value]

        context = EvidenceSearchRequestContext(request=request, authorization=authorization, trace_id=trace_id)
        try:
            response = await asyncio.wait_for(
                searcher.search(context),
                timeout=settings.search_timeout_seconds,
            )
        except TimeoutError:
            response = EvidenceSearchResponse(
                status=SearchStatus.UNAVAILABLE,
                request_id=request.request_id,
                trace_id=trace_id,
                reason_code=StableReasonCode.INDEX_GENERATION_UNAVAILABLE,
                retryable=True,
            )
        except Exception:
            response = EvidenceSearchResponse(
                status=SearchStatus.UNAVAILABLE,
                request_id=request.request_id,
                trace_id=trace_id,
                reason_code=StableReasonCode.DATABASE_UNAVAILABLE,
                retryable=True,
            )
        await _record_or_raise(
            audit_sink,
            _audit_record(
                request,
                trace_id,
                started,
                response.status.value,
                response.reason_code.value if response.reason_code else None,
                application_ref=identity.application_ref,
                jti_hash=identity.jti_hash,
                evidence_count=len(response.evidence),
            ),
            trace_id,
        )
        return response


def _extract_bearer(header: str) -> str:
    scheme, separator, credential = header.partition(" ")
    if separator != " " or scheme.lower() != "bearer" or not credential:
        raise AuthenticationRejected()
    return credential


def _audit_record(
    request: EvidenceSearchRequest,
    trace_id: str,
    started: float,
    decision: str,
    reason_code: str | None,
    *,
    application_ref: str | None = None,
    jti_hash: str | None = None,
    evidence_count: int = 0,
) -> AuditRecord:
    del trace_id
    return AuditRecord(
        request_id=request.request_id,
        application_ref=application_ref,
        shop_ref_hash=hash_shop_ref(request.shop_ref),
        requested_space_codes=tuple(request.requested_space_codes),
        decision=decision,
        reason_code=reason_code,
        jti_hash=jti_hash,
        evidence_count=evidence_count,
        latency_ms=max(0, int((time.perf_counter() - started) * 1000)),
    )


async def _record_or_raise(audit_sink: AuditSink, event: AuditRecord, trace_id: str) -> None:
    try:
        await audit_sink.record(event)
    except Exception as error:
        raise AuthorityUnavailable("mandatory audit unavailable") from error
