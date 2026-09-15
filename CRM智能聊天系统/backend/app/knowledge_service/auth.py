"""知识服务应用身份与店铺委托 JWT 验证。"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

import jwt

from app.knowledge_service.config import KnowledgeServiceSettings


class AuthenticationRejected(Exception):
    """凭证不符合已批准的 JWT profile。"""

    def __init__(self, reason_code: str = "TOKEN_INVALID") -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


@dataclass(frozen=True, slots=True)
class ApplicationIdentity:
    """已验签的内部应用身份。"""

    application_ref: str
    issuer: str
    jti_hash: str


@dataclass(frozen=True, slots=True)
class DelegationIdentity:
    """已验签的店铺范围委托身份。"""

    delegated_subject_ref: str
    application_ref: str
    shop_ref: str
    allowed_space_codes: frozenset[str]
    issuer: str
    jti_hash: str


class TokenVerifier:
    """按 kid 选择公钥，并严格验证两类 Token profile。"""

    _allowed_algorithms = frozenset({"ES256", "EdDSA"})

    def __init__(self, settings: KnowledgeServiceSettings) -> None:
        self._settings = settings

    def verify_application(self, token: str) -> ApplicationIdentity:
        claims = self._decode(
            token,
            verification_keys=self._settings.application_verification_keys,
            expected_typ="service_access+jwt",
            expected_token_type="service_access",
            expected_issuer=self._settings.jwt_application_issuer,
            maximum_lifetime_seconds=300,
            extra_required=(),
        )
        self._require_subject_match(claims)
        key_entry = self._settings.application_verification_keys[claims["_verified_kid"]]
        if key_entry.get("application_ref") != claims["application_ref"]:
            raise AuthenticationRejected()
        return ApplicationIdentity(
            application_ref=claims["application_ref"],
            issuer=claims["iss"],
            jti_hash=_hash_identifier(claims["jti"]),
        )

    def verify_delegation(self, token: str) -> DelegationIdentity:
        claims = self._decode(
            token,
            verification_keys=self._settings.delegation_verification_keys,
            expected_typ="shop_delegation+jwt",
            expected_token_type="shop_delegation",
            expected_issuer=self._settings.jwt_delegation_issuer,
            maximum_lifetime_seconds=120,
            extra_required=("shop_ref", "allowed_space_codes"),
        )
        delegated_subject_ref = claims.get("sub")
        if (
            not isinstance(delegated_subject_ref, str)
            or not delegated_subject_ref
            or not isinstance(claims.get("application_ref"), str)
            or not claims["application_ref"]
        ):
            raise AuthenticationRejected()
        allowed_spaces = claims["allowed_space_codes"]
        if not isinstance(allowed_spaces, list) or not allowed_spaces or not all(
            isinstance(space, str) and space for space in allowed_spaces
        ):
            raise AuthenticationRejected()
        if not isinstance(claims["shop_ref"], str) or not claims["shop_ref"]:
            raise AuthenticationRejected()
        return DelegationIdentity(
            delegated_subject_ref=delegated_subject_ref,
            application_ref=claims["application_ref"],
            shop_ref=claims["shop_ref"],
            allowed_space_codes=frozenset(allowed_spaces),
            issuer=claims["iss"],
            jti_hash=_hash_identifier(claims["jti"]),
        )

    def _decode(
        self,
        token: str,
        *,
        verification_keys: dict[str, dict[str, str]],
        expected_typ: str,
        expected_token_type: str,
        expected_issuer: str,
        maximum_lifetime_seconds: int,
        extra_required: tuple[str, ...],
    ) -> dict[str, Any]:
        try:
            header = jwt.get_unverified_header(token)
            algorithm = header.get("alg")
            key_id = header.get("kid")
            if header.get("typ") != expected_typ or algorithm not in self._allowed_algorithms:
                raise AuthenticationRejected()
            if not isinstance(key_id, str) or not key_id:
                raise AuthenticationRejected()
            key_entry = verification_keys.get(key_id)
            if not isinstance(key_entry, dict) or key_entry.get("alg") != algorithm:
                raise AuthenticationRejected("KEY_NOT_AVAILABLE")
            public_key = key_entry.get("pem")
            if not isinstance(public_key, str) or not public_key:
                raise AuthenticationRejected("KEY_NOT_AVAILABLE")
            required = [
                "iss",
                "aud",
                "sub",
                "application_ref",
                "token_type",
                "iat",
                "nbf",
                "exp",
                "jti",
                *extra_required,
            ]
            claims = jwt.decode(
                token,
                public_key,
                algorithms=[algorithm],
                audience=self._settings.jwt_audience,
                issuer=expected_issuer,
                leeway=30,
                options={"require": required},
            )
        except AuthenticationRejected:
            raise
        except (jwt.PyJWTError, ValueError, TypeError, KeyError) as error:
            raise AuthenticationRejected() from error

        if claims.get("token_type") != expected_token_type:
            raise AuthenticationRejected()
        issued_at = claims.get("iat")
        expires_at = claims.get("exp")
        if not isinstance(issued_at, (int, float)) or not isinstance(expires_at, (int, float)):
            raise AuthenticationRejected()
        if expires_at <= issued_at or expires_at - issued_at > maximum_lifetime_seconds:
            raise AuthenticationRejected("TOKEN_LIFETIME_INVALID")
        if not isinstance(claims.get("jti"), str) or not claims["jti"]:
            raise AuthenticationRejected()
        claims["_verified_kid"] = key_id
        return claims

    @staticmethod
    def _require_subject_match(claims: dict[str, Any]) -> None:
        if (
            not isinstance(claims.get("application_ref"), str)
            or not claims["application_ref"]
            or claims.get("sub") != claims["application_ref"]
        ):
            raise AuthenticationRejected()


def _hash_identifier(value: str) -> str:
    """审计中仅保留不可逆标识哈希。"""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
