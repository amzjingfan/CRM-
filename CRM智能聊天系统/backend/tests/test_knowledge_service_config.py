"""独立知识服务配置边界测试。"""

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from pydantic import ValidationError

from app.knowledge_service.config import KnowledgeServiceSettings


def _verification_keys_json() -> str:
    public_pem = ec.generate_private_key(ec.SECP256R1()).public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")
    return '{"application-key":{"alg":"ES256","pem":' + repr(public_pem).replace("'", '"') + "}}"


def test_local_settings_use_independent_database_and_bucket() -> None:
    """默认本地配置也不得回退到 CRM 数据库或 FAQ 对象桶。"""
    settings = KnowledgeServiceSettings()

    assert settings.database_url.rsplit("/", maxsplit=1)[-1] == "company_knowledge"
    assert settings.object_store_bucket == "company-knowledge"
    assert settings.jwt_audience == "company-knowledge-service"


@pytest.mark.parametrize(
    ("override", "expected_fragment"),
    [
        ({"database_url": "postgresql+asyncpg://runtime:secret@db:5432/crm"}, "company_knowledge"),
        (
            {
                "database_url": (
                    "postgresql+asyncpg://knowledge_migration:secret@db:5432/company_knowledge"
                )
            },
            "runtime",
        ),
        ({"object_store_access_key": "minio"}, "root"),
        ({"object_store_secret_key": "change-me-minio-password"}, "example"),
        ({"jwt_audience": ""}, "audience"),
        ({"verification_keys_json": "{}"}, "verification"),
        ({"verification_keys_json": '{"key":{"alg":"ES256","pem":"public"}}'}, "verification"),
    ],
)
def test_staging_settings_reject_unsafe_or_shared_configuration(
    override: dict[str, str], expected_fragment: str
) -> None:
    """预发与生产环境必须在启动前拒绝错库和示例凭证。"""
    values = {
        "environment": "staging",
        "database_url": "postgresql+asyncpg://knowledge_runtime:strong-secret@db:5432/company_knowledge",
        "object_store_access_key": "knowledge-runtime",
        "object_store_secret_key": "strong-object-secret",
        "jwt_audience": "company-knowledge-service",
        "verification_keys_json": _verification_keys_json(),
    }
    values.update(override)

    with pytest.raises(ValidationError) as error:
        KnowledgeServiceSettings(**values)

    assert expected_fragment in str(error.value).lower()


def test_settings_do_not_reuse_crm_environment_names(monkeypatch: pytest.MonkeyPatch) -> None:
    """CRM 的通用环境变量不能隐式改写知识服务配置。"""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://crm:crm@db:5432/crm")
    monkeypatch.setenv("MINIO_BUCKET", "crm-files")

    settings = KnowledgeServiceSettings()

    assert settings.database_url.rsplit("/", maxsplit=1)[-1] == "company_knowledge"
    assert settings.object_store_bucket == "company-knowledge"
