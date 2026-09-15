"""知识证据内部 API 认证、授权、四态和审计测试。"""

import asyncio
import json
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

from app.knowledge_service.auth import TokenVerifier
from app.knowledge_service.authorization import ApplicationAuthority, ApplicationScope, KnowledgeAuthorizer
from app.knowledge_service.config import KnowledgeServiceSettings
from app.knowledge_service.main import create_app
from app.knowledge_service.schemas import EvidenceSearchResponse, SearchStatus, StableReasonCode
from app.knowledge_service.service import AuditRecord, EvidenceSearchRequestContext


class FakeAuthority:
    def __init__(self, *, enabled: bool = True, unavailable: bool = False) -> None:
        self.enabled = enabled
        self.unavailable = unavailable

    async def load_application(self, application_ref: str) -> ApplicationAuthority | None:
        if self.unavailable:
            raise RuntimeError("database unavailable")
        return ApplicationAuthority(
            application_ref=application_ref,
            enabled=self.enabled,
            allowed_scopes=frozenset(
                {ApplicationScope("TK", "US", "en-US", "internal_agent", "company_shared")}
            ),
        )

    async def is_credential_revoked(self, issuer: str, jti_hash: str) -> bool:
        del issuer, jti_hash
        return False

    async def has_shop_grant(self, application_ref: str, shop_ref: str, space_code: str) -> bool:
        del application_ref, shop_ref, space_code
        return False


class FixedSearcher:
    def __init__(self, response: EvidenceSearchResponse) -> None:
        self.response = response
        self.last_context: EvidenceSearchRequestContext | None = None

    async def search(self, context: EvidenceSearchRequestContext) -> EvidenceSearchResponse:
        self.last_context = context
        return self.response.model_copy(update={"request_id": context.request.request_id, "trace_id": context.trace_id})


class SlowSearcher:
    async def search(self, context: EvidenceSearchRequestContext) -> EvidenceSearchResponse:
        del context
        await asyncio.sleep(1)
        raise AssertionError("search timeout did not cancel the operation")


class CapturingAuditSink:
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    async def record(self, event: AuditRecord) -> None:
        self.records.append(event)


class FailingAuditSink:
    async def record(self, event: AuditRecord) -> None:
        del event
        raise RuntimeError("audit database unavailable")


@pytest.fixture
def api_identity() -> tuple[ec.EllipticCurvePrivateKey, TokenVerifier, str]:
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_pem = private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")
    settings = KnowledgeServiceSettings(
        environment="test",
        verification_keys_json=json.dumps({"api-test-key": {"alg": "ES256", "pem": public_pem}}),
    )
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "iss": settings.jwt_application_issuer,
            "aud": settings.jwt_audience,
            "sub": "crm-assistant",
            "application_ref": "crm-assistant",
            "token_type": "service_access",
            "iat": now,
            "nbf": now,
            "exp": now + timedelta(minutes=4),
            "jti": "api-application-jti",
        },
        private_key,
        algorithm="ES256",
        headers={"typ": "service_access+jwt", "kid": "api-test-key"},
    )
    return private_key, TokenVerifier(settings), token


def _request_body() -> dict[str, object]:
    return {
        "request_id": "req-k2-0001",
        "query": "What is the current fulfillment evidence?",
        "platform_code": "TK",
        "market_code": "US",
        "language_tag": "en-US",
        "audience_code": "internal_agent",
        "requested_space_codes": ["company_shared"],
        "top_k": 5,
    }


def test_authorized_request_returns_k2_fail_closed_state_and_low_sensitivity_audit(
    api_identity: tuple[ec.EllipticCurvePrivateKey, TokenVerifier, str],
) -> None:
    _, verifier, token = api_identity
    searcher = FixedSearcher(
        EvidenceSearchResponse(
            status=SearchStatus.UNAVAILABLE,
            request_id="placeholder",
            trace_id="placeholder",
            reason_code=StableReasonCode.INDEX_GENERATION_UNAVAILABLE,
            retryable=True,
        )
    )
    audit = CapturingAuditSink()
    app = create_app(
        verifier=verifier,
        authorizer=KnowledgeAuthorizer(FakeAuthority()),
        searcher=searcher,
        audit_sink=audit,
    )

    with TestClient(app) as client:
        response = client.post(
            "/internal/v1/evidence:search",
            headers={"Authorization": f"Bearer {token}"},
            json=_request_body(),
        )

    assert response.status_code == 200
    assert response.json()["status"] == "unavailable"
    assert response.json()["reason_code"] == "INDEX_GENERATION_UNAVAILABLE"
    assert searcher.last_context is not None
    assert searcher.last_context.authorization.application_ref == "crm-assistant"
    assert len(audit.records) == 1
    assert audit.records[0].request_id == "req-k2-0001"
    assert not hasattr(audit.records[0], "query")
    assert token not in repr(audit.records[0])


def test_missing_or_invalid_application_token_returns_401_without_business_envelope() -> None:
    app = create_app(
        authorizer=KnowledgeAuthorizer(FakeAuthority()),
        audit_sink=CapturingAuditSink(),
    )
    with TestClient(app) as client:
        response = client.post("/internal/v1/evidence:search", json=_request_body())

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "TOKEN_INVALID"
    assert "status" not in response.json()


def test_mandatory_audit_failure_returns_503_without_business_envelope() -> None:
    app = create_app(
        authorizer=KnowledgeAuthorizer(FakeAuthority()),
        audit_sink=FailingAuditSink(),
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post("/internal/v1/evidence:search", json=_request_body())

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "AUTHORITY_UNAVAILABLE"
    assert "status" not in response.json()


def test_search_timeout_is_a_retryable_business_unavailable_state(
    api_identity: tuple[ec.EllipticCurvePrivateKey, TokenVerifier, str],
) -> None:
    _, verifier, token = api_identity
    app = create_app(
        settings=KnowledgeServiceSettings(environment="test", search_timeout_seconds=0.01),
        verifier=verifier,
        authorizer=KnowledgeAuthorizer(FakeAuthority()),
        searcher=SlowSearcher(),
        audit_sink=CapturingAuditSink(),
    )
    with TestClient(app) as client:
        response = client.post(
            "/internal/v1/evidence:search",
            headers={"Authorization": f"Bearer {token}"},
            json=_request_body(),
        )

    assert response.status_code == 200
    assert response.json()["status"] == "unavailable"
    assert response.json()["reason_code"] == "INDEX_GENERATION_UNAVAILABLE"
    assert response.json()["retryable"] is True


@pytest.mark.parametrize(
    ("authority", "expected_status", "expected_code"),
    [
        (FakeAuthority(enabled=False), 403, "APPLICATION_NOT_ALLOWED"),
        (FakeAuthority(unavailable=True), 503, "AUTHORITY_UNAVAILABLE"),
    ],
)
def test_authority_decisions_remain_distinct_from_business_states(
    api_identity: tuple[ec.EllipticCurvePrivateKey, TokenVerifier, str],
    authority: FakeAuthority,
    expected_status: int,
    expected_code: str,
) -> None:
    _, verifier, token = api_identity
    app = create_app(
        verifier=verifier,
        authorizer=KnowledgeAuthorizer(authority),
        audit_sink=CapturingAuditSink(),
    )
    with TestClient(app) as client:
        response = client.post(
            "/internal/v1/evidence:search",
            headers={"Authorization": f"Bearer {token}"},
            json=_request_body(),
        )

    assert response.status_code == expected_status
    assert response.json()["error"]["code"] == expected_code
    assert "status" not in response.json()
