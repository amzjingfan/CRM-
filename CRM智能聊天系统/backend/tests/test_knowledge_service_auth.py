"""知识服务分域非对称 JWT 验证测试。"""

import json
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from app.knowledge_service.auth import AuthenticationRejected, TokenVerifier
from app.knowledge_service.config import KnowledgeServiceSettings


def _public_pem(private_key: ec.EllipticCurvePrivateKey) -> str:
    return private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")


@pytest.fixture
def signing_material() -> tuple[
    ec.EllipticCurvePrivateKey,
    ec.EllipticCurvePrivateKey,
    TokenVerifier,
]:
    """应用与委托域使用不同测试私钥，私钥不落盘。"""
    application_key = ec.generate_private_key(ec.SECP256R1())
    delegation_key = ec.generate_private_key(ec.SECP256R1())
    settings = KnowledgeServiceSettings(
        environment="test",
        application_verification_keys_json=json.dumps(
            {
                "app-es256": {
                    "alg": "ES256",
                    "pem": _public_pem(application_key),
                    "application_ref": "crm-assistant",
                }
            }
        ),
        delegation_verification_keys_json=json.dumps(
            {"delegation-es256": {"alg": "ES256", "pem": _public_pem(delegation_key)}}
        ),
    )
    return application_key, delegation_key, TokenVerifier(settings)


def _application_token(
    private_key: ec.EllipticCurvePrivateKey,
    *,
    application_ref: str = "crm-assistant",
    key_id: str = "app-es256",
    typ: str = "service_access+jwt",
    token_type: str = "service_access",
    issuer: str = "company-service-identity",
    audience: str = "company-knowledge-service",
    lifetime: timedelta = timedelta(minutes=4),
    not_before_offset: timedelta = timedelta(0),
) -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "iss": issuer,
            "aud": audience,
            "sub": application_ref,
            "application_ref": application_ref,
            "token_type": token_type,
            "iat": now,
            "nbf": now + not_before_offset,
            "exp": now + lifetime,
            "jti": f"{application_ref}-jti-001",
        },
        private_key,
        algorithm="ES256",
        headers={"typ": typ, "kid": key_id},
    )


def _delegation_token(
    private_key: ec.EllipticCurvePrivateKey,
    *,
    key_id: str = "delegation-es256",
    delegated_subject_ref: str = "employee-ref-001",
    application_ref: str = "crm-assistant",
) -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "iss": "company-business-delegation",
            "aud": "company-knowledge-service",
            "sub": delegated_subject_ref,
            "application_ref": application_ref,
            "shop_ref": "shop-ref-us-001",
            "allowed_space_codes": ["shop_private"],
            "token_type": "shop_delegation",
            "iat": now,
            "nbf": now,
            "exp": now + timedelta(minutes=2),
            "jti": "delegation-jti-001",
        },
        private_key,
        algorithm="ES256",
        headers={"typ": "shop_delegation+jwt", "kid": key_id},
    )


def test_application_token_requires_exact_profile(
    signing_material: tuple[ec.EllipticCurvePrivateKey, ec.EllipticCurvePrivateKey, TokenVerifier],
) -> None:
    application_key, _, verifier = signing_material

    identity = verifier.verify_application(_application_token(application_key))

    assert identity.application_ref == "crm-assistant"
    assert identity.issuer == "company-service-identity"
    assert identity.jti_hash != "crm-assistant-jti-001"
    assert len(identity.jti_hash) == 64


@pytest.mark.parametrize(
    "token_kwargs",
    [
        {"typ": "JWT"},
        {"token_type": "shop_delegation"},
        {"issuer": "company-business-delegation"},
        {"audience": "crm-backend"},
        {"lifetime": timedelta(minutes=6)},
        {"lifetime": timedelta(seconds=-1)},
        {"not_before_offset": timedelta(minutes=2)},
        {"key_id": "unknown-key"},
    ],
)
def test_application_token_rejects_wrong_profile(
    signing_material: tuple[ec.EllipticCurvePrivateKey, ec.EllipticCurvePrivateKey, TokenVerifier],
    token_kwargs: dict[str, object],
) -> None:
    application_key, _, verifier = signing_material

    with pytest.raises(AuthenticationRejected):
        verifier.verify_application(_application_token(application_key, **token_kwargs))  # type: ignore[arg-type]


def test_application_key_is_bound_to_application_ref(
    signing_material: tuple[ec.EllipticCurvePrivateKey, ec.EllipticCurvePrivateKey, TokenVerifier],
) -> None:
    application_key, _, verifier = signing_material

    with pytest.raises(AuthenticationRejected):
        verifier.verify_application(_application_token(application_key, application_ref="operations-console"))


def test_application_and_delegation_key_domains_cannot_be_exchanged(
    signing_material: tuple[ec.EllipticCurvePrivateKey, ec.EllipticCurvePrivateKey, TokenVerifier],
) -> None:
    application_key, delegation_key, verifier = signing_material

    with pytest.raises(AuthenticationRejected):
        verifier.verify_delegation(_delegation_token(application_key, key_id="app-es256"))
    with pytest.raises(AuthenticationRejected):
        verifier.verify_application(_application_token(delegation_key, key_id="delegation-es256"))


def test_symmetric_algorithm_is_rejected_before_key_lookup(
    signing_material: tuple[ec.EllipticCurvePrivateKey, ec.EllipticCurvePrivateKey, TokenVerifier],
) -> None:
    _, _, verifier = signing_material
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "iss": "company-service-identity",
            "aud": "company-knowledge-service",
            "sub": "crm-assistant",
            "application_ref": "crm-assistant",
            "token_type": "service_access",
            "iat": now,
            "nbf": now,
            "exp": now + timedelta(minutes=4),
            "jti": "symmetric-jti",
        },
        "unit-test-only-symmetric-key-32-bytes",
        algorithm="HS256",
        headers={"typ": "service_access+jwt", "kid": "app-es256"},
    )

    with pytest.raises(AuthenticationRejected):
        verifier.verify_application(token)


def test_delegation_token_preserves_distinct_delegated_subject(
    signing_material: tuple[ec.EllipticCurvePrivateKey, ec.EllipticCurvePrivateKey, TokenVerifier],
) -> None:
    _, delegation_key, verifier = signing_material

    identity = verifier.verify_delegation(_delegation_token(delegation_key))

    assert identity.delegated_subject_ref == "employee-ref-001"
    assert identity.application_ref == "crm-assistant"
    assert identity.shop_ref == "shop-ref-us-001"
    assert identity.allowed_space_codes == frozenset({"shop_private"})


def test_two_consumers_use_distinct_application_refs_and_signing_keys() -> None:
    first_key = ec.generate_private_key(ec.SECP256R1())
    second_key = ec.generate_private_key(ec.SECP256R1())
    delegation_key = ec.generate_private_key(ec.SECP256R1())
    verifier = TokenVerifier(
        KnowledgeServiceSettings(
            environment="test",
            application_verification_keys_json=json.dumps(
                {
                    "crm-key": {
                        "alg": "ES256",
                        "pem": _public_pem(first_key),
                        "application_ref": "crm-assistant",
                    },
                    "ops-key": {
                        "alg": "ES256",
                        "pem": _public_pem(second_key),
                        "application_ref": "operations-console",
                    },
                }
            ),
            delegation_verification_keys_json=json.dumps(
                {"delegation-key": {"alg": "ES256", "pem": _public_pem(delegation_key)}}
            ),
        )
    )

    crm = verifier.verify_application(
        _application_token(first_key, application_ref="crm-assistant", key_id="crm-key")
    )
    operations = verifier.verify_application(
        _application_token(second_key, application_ref="operations-console", key_id="ops-key")
    )

    assert crm.application_ref == "crm-assistant"
    assert operations.application_ref == "operations-console"
