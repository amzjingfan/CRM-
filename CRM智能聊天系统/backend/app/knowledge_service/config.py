"""独立知识服务配置及启动门禁。"""

from __future__ import annotations

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
    verification_keys_json: str = "{}"
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
    def verification_keys(self) -> dict[str, dict[str, str]]:
        """解析受控公钥集，私钥不属于本服务配置。"""
        parsed = json.loads(self.verification_keys_json)
        if not isinstance(parsed, dict):
            raise ValueError("verification key set must be an object")
        return parsed

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
            keys = self.verification_keys
        except (json.JSONDecodeError, ValueError) as error:
            raise ValueError("verification key set is invalid") from error
        if not keys:
            raise ValueError("verification key set is required")
        try:
            self._validate_verification_keys(keys)
        except (TypeError, ValueError) as error:
            raise ValueError("verification key set contains an invalid public key") from error
        return self

    @staticmethod
    def _validate_verification_keys(keys: dict[str, dict[str, str]]) -> None:
        """在启动时解析全部公钥，避免首次请求才发现配置损坏。"""
        for key_id, entry in keys.items():
            if not isinstance(key_id, str) or not key_id or not isinstance(entry, dict):
                raise ValueError("invalid key entry")
            algorithm = entry.get("alg")
            pem = entry.get("pem")
            if algorithm not in {"ES256", "EdDSA"} or not isinstance(pem, str):
                raise ValueError("unsupported verification key")
            public_key = serialization.load_pem_public_key(pem.encode("ascii"))
            if algorithm == "ES256":
                if not isinstance(public_key, ec.EllipticCurvePublicKey) or not isinstance(
                    public_key.curve,
                    ec.SECP256R1,
                ):
                    raise ValueError("ES256 requires a P-256 public key")
            elif not isinstance(public_key, (ed25519.Ed25519PublicKey, ed448.Ed448PublicKey)):
                raise ValueError("EdDSA requires an Ed25519 or Ed448 public key")
