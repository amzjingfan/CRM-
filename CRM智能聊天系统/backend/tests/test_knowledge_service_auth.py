"""知识服务非对称 JWT 验证测试。"""

import json
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from app.knowledge_service.auth import AuthenticationRejected, TokenVerifier
from app.knowledge_service.config import KnowledgeServiceSettings


@pytest.fixture
def signing_material() -> tuple[ec.EllipticCurvePrivateKey, TokenVerifier]:
    """每个测试动态生成短命测试密钥，不在仓库保存私钥。"""
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_pem = private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")
    settings = KnowledgeServiceSettings(
        environment="test",
        verification_keys_json=json.dumps(
            {"test-es256": {"alg": "ES256", "pem": public_pem}},
        ),
    )
    return private_key, TokenVerifier(settings)


def _application_token(
    private_key: ec.EllipticCurvePrivateKey,
    *,
    application_ref: str = "crm-assistant",
    key_id: str = "test-es256",
    typ: str = "service_access+jwt",
    token_type: str = "service_access",
    audience: str = "company-knowledge-service",
    lifetime: timedelta = timedelta(minutes=4),
) -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "iss": "company-service-identity",
            "aud": audience,
            "sub": application_ref,
            "application_ref": application_ref,
            "token_type": token_type,
            "iat": now,
            "nbf": now,
            "exp": now + lifetime,
            "jti": f"{application_ref}-jti-001",
        },
        private_key,
        algorithm="ES256",
        headers={"typ": typ, "kid": key_id},
    )


def test_application_token_requires_exact_profile(
    signing_material: tuple[ec.EllipticCurvePrivateKey, TokenVerifier],
) -> None:
    """合法应用 Token 只暴露低敏应用标识和 JTI 哈希。"""
    private_key, verifier = signing_material

    identity = verifier.verify_application(_application_token(private_key))

    assert identity.application_ref == "crm-assistant"
    assert identity.issuer == "company-service-identity"
    assert identity.jti_hash != "crm-assistant-jti-001"
    assert len(identity.jti_hash) == 64


@pytest.mark.parametrize(
    "token_kwargs",
    [
        {"typ": "JWT"},
        {"token_type": "shop_delegation"},
        {"audience": "crm-backend"},
        {"lifetime": timedelta(minutes=6)},
    ],
)
def test_application_token_rejects_wrong_profile(
    signing_material: tuple[ec.EllipticCurvePrivateKey, TokenVerifier],
    token_kwargs: dict[str, object],
) -> None:
    """typ、token_type、audience 或最长 TTL 任一不符都必须失败关闭。"""
    private_key, verifier = signing_material

    with pytest.raises(AuthenticationRejected):
        verifier.verify_application(_application_token(private_key, **token_kwargs))  # type: ignore[arg-type]


def test_delegation_token_requires_shop_and_shorter_ttl(
    signing_material: tuple[ec.EllipticCurvePrivateKey, TokenVerifier],
) -> None:
    """店铺委托 Token 仅允许两分钟，且必须携带允许空间。"""
    private_key, verifier = signing_material
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "iss": "company-business-delegation",
            "aud": "company-knowledge-service",
            "sub": "crm-assistant",
            "application_ref": "crm-assistant",
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
        headers={"typ": "shop_delegation+jwt", "kid": "test-es256"},
    )

    identity = verifier.verify_delegation(token)

    assert identity.shop_ref == "shop-ref-us-001"
    assert identity.allowed_space_codes == frozenset({"shop_private"})


def test_two_consumers_use_distinct_application_refs_and_signing_keys() -> None:
    """多系统复用不得通过共享 CRM 密钥或伪造相同应用身份实现。"""
    first_key = ec.generate_private_key(ec.SECP256R1())
    second_key = ec.generate_private_key(ec.SECP256R1())

    def public_pem(private_key: ec.EllipticCurvePrivateKey) -> str:
        return private_key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("ascii")

    verifier = TokenVerifier(
        KnowledgeServiceSettings(
            environment="test",
            verification_keys_json=json.dumps(
                {
                    "crm-key": {"alg": "ES256", "pem": public_pem(first_key)},
                    "ops-key": {"alg": "ES256", "pem": public_pem(second_key)},
                }
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
    assert crm.application_ref != operations.application_ref
