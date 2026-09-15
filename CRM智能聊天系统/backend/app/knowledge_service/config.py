"""独立知识服务配置及启动门禁。"""

from __future__ import annotations

import hashlib
import json
from typing import Literal
from urllib.parse import urlsplit

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed448, ed25519
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class KnowledgeServiceSettings(BaseSettings):
    """仅读取 ``KNOWLEDGE_`` 前缀配置，避免误用 CRM 运行时凭证。"""

    model_config = SettingsConfigDict(
        env_prefix="KNOWLEDGE_",
        env_file=None,
        extra="ignore",
        case_sensitive=False,
    )

    environment: Literal["local", "test", "staging", "production"] = "local"
    service_name: str = "company-knowledge-service"
    database_url: str = "postgresql+asyncpg://knowledge_runtime:local-only@localhost:5432/company_knowledge"
    object_store_endpoint: str = "localhost:9000"
    object_store_access_key: str = "knowledge-local"
    object_store_secret_key: str = "local-only-knowledge-secret"
    object_store_bucket: str = "company-knowledge"
    object_store_secure: bool = False
    jwt_application_issuer: str = "company-service-identity"
    jwt_delegation_issuer: str = "company-business-delegation"
    jwt_audience: str = "company-knowledge-service"
    application_verification_keys_json: str = "{}"
    delegation_verification_keys_json: str = "{}"
    authority_timeout_seconds: float = Field(default=2.0, gt=0.0, le=10.0)
    search_timeout_seconds: float = Field(default=5.0, gt=0.0, le=30.0)

    @property
    def database_name(self) -> str:
        """返回数据库路径中的最后一段，仅用于边界检查与健康输出。"""
        return urlsplit(self.database_url).path.rstrip("/").rsplit("/", maxsplit=1)[-1]

    @property
    def database_user(self) -> str | None:
        """部署入口的运行时连接必须使用最小权限角色。"""
        return urlsplit(self.database_url).username

    @property
    def application_verification_keys(self) -> dict[str, dict[str, str]]:
        """解析仅可签发应用身份的公钥集。"""
        return self._parse_verification_keys(self.application_verification_keys_json)

    @property
    def delegation_verification_keys(self) -> dict[str, dict[str, str]]:
        """解析仅可签发店铺委托的公钥集。"""
        return self._parse_verification_keys(self.delegation_verification_keys_json)

    @staticmethod
    def _parse_verification_keys(serialized: str) -> dict[str, dict[str, str]]:
        parsed = json.loads(serialized)
        if not isinstance(parsed, dict):
            raise ValueError("verification key set must be an object")
        return parsed

    def validate_operational_security(self) -> None:
        """部署入口在建连前验证两套分域验签权威。"""
        key_sets = (
            self.application_verification_keys,
            self.delegation_verification_keys,
        )
        if not all(key_sets):
            raise ValueError("application and delegation verification key sets are required")
        self._validate_verification_keys(
            self.application_verification_keys,
            require_application_ref=True,
        )
        self._validate_verification_keys(self.delegation_verification_keys)
        self._validate_distinct_key_domains(
            self.application_verification_keys,
            self.delegation_verification_keys,
        )

    @model_validator(mode="after")
    def reject_unsafe_non_local_configuration(self) -> KnowledgeServiceSettings:
        """预发和生产必须在建立任何连接前失败关闭。"""
        if self.environment in {"local", "test"}:
            return self
        if self.database_name != "company_knowledge":
            raise ValueError("database must be the independent company_knowledge database")
        if self.database_user != "knowledge_runtime":
            raise ValueError("database user must be the least-privilege knowledge_runtime role")
        if self.object_store_access_key.strip().lower() in {"minio", "root", "admin"}:
            raise ValueError("object store root credentials are forbidden")
        unsafe_secret_markers = ("change-me", "example", "local-only", "password")
        if any(marker in self.object_store_secret_key.lower() for marker in unsafe_secret_markers):
            raise ValueError("object store example secret is forbidden")
        if not self.jwt_audience.strip():
            raise ValueError("JWT audience is required")
        try:
            application_keys = self.application_verification_keys
            delegation_keys = self.delegation_verification_keys
        except (json.JSONDecodeError, ValueError) as error:
            raise ValueError("verification key set is invalid") from error
        if not application_keys or not delegation_keys:
            raise ValueError("application and delegation verification key sets are required")
        try:
            self._validate_verification_keys(application_keys, require_application_ref=True)
            self._validate_verification_keys(delegation_keys)
            self._validate_distinct_key_domains(application_keys, delegation_keys)
        except (TypeError, ValueError) as error:
            raise ValueError("verification key set contains an invalid public key") from error
        return self

    @staticmethod
    def _validate_verification_keys(
        keys: dict[str, dict[str, str]],
        *,
        require_application_ref: bool = False,
    ) -> None:
        """在启动时解析全部公钥，避免首次请求才发现配置损坏。"""
        for key_id, entry in keys.items():
            if not isinstance(key_id, str) or not key_id or not isinstance(entry, dict):
                raise ValueError("invalid key entry")
            algorithm = entry.get("alg")
            pem = entry.get("pem")
            application_ref = entry.get("application_ref")
            if algorithm not in {"ES256", "EdDSA"} or not isinstance(pem, str):
                raise ValueError("unsupported verification key")
            if require_application_ref and (not isinstance(application_ref, str) or not application_ref):
                raise ValueError("application verification key must bind one application_ref")
            public_key = serialization.load_pem_public_key(pem.encode("ascii"))
            if algorithm == "ES256":
                if not isinstance(public_key, ec.EllipticCurvePublicKey) or not isinstance(
                    public_key.curve,
                    ec.SECP256R1,
                ):
                    raise ValueError("ES256 requires a P-256 public key")
            elif not isinstance(public_key, (ed25519.Ed25519PublicKey, ed448.Ed448PublicKey)):
                raise ValueError("EdDSA requires an Ed25519 or Ed448 public key")

    @staticmethod
    def _validate_distinct_key_domains(
        application_keys: dict[str, dict[str, str]],
        delegation_keys: dict[str, dict[str, str]],
    ) -> None:
        """按公钥指纹拒绝改名后的跨域复用。"""

        if application_keys.keys() & delegation_keys.keys():
            raise ValueError("application and delegation key identifiers must be distinct")

        def fingerprints(keys: dict[str, dict[str, str]]) -> set[str]:
            values: set[str] = set()
            for entry in keys.values():
                public_key = serialization.load_pem_public_key(entry["pem"].encode("ascii"))
                der = public_key.public_bytes(
                    serialization.Encoding.DER,
                    serialization.PublicFormat.SubjectPublicKeyInfo,
                )
                values.add(hashlib.sha256(der).hexdigest())
            return values

        if fingerprints(application_keys) & fingerprints(delegation_keys):
            raise ValueError(
                "application and delegation verification keys must be cryptographically distinct"
            )
