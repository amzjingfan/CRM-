"""应用、空间、店铺委托与服务端 grant 交集。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.knowledge_service.auth import ApplicationIdentity, DelegationIdentity


class AuthorizationRejected(Exception):
    """凭证已验证后的撤销或范围拒绝。"""

    def __init__(self, reason_code: str, http_status: int = 403) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code
        self.http_status = http_status


class AuthorityUnavailable(Exception):
    """权威授权存储无法给出可信判定。"""


@dataclass(frozen=True, slots=True)
class ApplicationScope:
    """应用 grant 必须对平台、市场、语言、读者和空间精确授权。"""

    platform_code: str
    market_code: str
    language_tag: str
    audience_code: str
    space_code: str


@dataclass(frozen=True, slots=True)
class ApplicationAuthority:
    """服务端应用登记和空间 grant 快照。"""

    application_ref: str
    enabled: bool
    allowed_scopes: frozenset[ApplicationScope]

    @property
    def allowed_space_codes(self) -> frozenset[str]:
        return frozenset(scope.space_code for scope in self.allowed_scopes)


@dataclass(frozen=True, slots=True)
class AuthorizationContext:
    """传入检索层的最小授权上下文。"""

    application_ref: str
    allowed_space_codes: frozenset[str]
    shop_ref: str | None
    application_jti_hash: str
    delegation_jti_hash: str | None


class AuthorityRepository(Protocol):
    """授权权威数据读取端口。"""

    async def load_application(self, application_ref: str) -> ApplicationAuthority | None: ...

    async def is_credential_revoked(self, issuer: str, jti_hash: str) -> bool: ...

    async def has_shop_grant(self, application_ref: str, shop_ref: str, space_code: str) -> bool: ...


class KnowledgeAuthorizer:
    """不信任请求正文，只认可验签身份与服务端 grant 的交集。"""

    def __init__(self, repository: AuthorityRepository) -> None:
        self._repository = repository

    async def authorize(
        self,
        *,
        application_identity: ApplicationIdentity,
        delegation_identity: DelegationIdentity | None,
        requested_space_codes: frozenset[str],
        shop_ref: str | None,
        platform_code: str,
        market_code: str,
        language_tag: str,
        audience_code: str,
    ) -> AuthorizationContext:
        try:
            return await self._authorize(
                application_identity=application_identity,
                delegation_identity=delegation_identity,
                requested_space_codes=requested_space_codes,
                shop_ref=shop_ref,
                platform_code=platform_code,
                market_code=market_code,
                language_tag=language_tag,
                audience_code=audience_code,
            )
        except AuthorizationRejected:
            raise
        except Exception as error:
            raise AuthorityUnavailable("authorization authority unavailable") from error

    async def _authorize(
        self,
        *,
        application_identity: ApplicationIdentity,
        delegation_identity: DelegationIdentity | None,
        requested_space_codes: frozenset[str],
        shop_ref: str | None,
        platform_code: str,
        market_code: str,
        language_tag: str,
        audience_code: str,
    ) -> AuthorizationContext:
        if await self._repository.is_credential_revoked(
            application_identity.issuer,
            application_identity.jti_hash,
        ):
            raise AuthorizationRejected("CREDENTIAL_REVOKED", http_status=401)

        authority = await self._repository.load_application(application_identity.application_ref)
        if authority is None or not authority.enabled:
            raise AuthorizationRejected("APPLICATION_NOT_ALLOWED")
        requested_scopes = {
            ApplicationScope(platform_code, market_code, language_tag, audience_code, space_code)
            for space_code in requested_space_codes
        }
        if not requested_space_codes or not requested_scopes <= authority.allowed_scopes:
            raise AuthorizationRejected("NO_SCOPE_MATCH")
        if requested_space_codes - {"company_shared", "shop_private"}:
            raise AuthorizationRejected("NO_SCOPE_MATCH")

        if requested_space_codes == {"company_shared"}:
            if shop_ref is not None or delegation_identity is not None:
                raise AuthorizationRejected("NO_SCOPE_MATCH")
            return AuthorizationContext(
                application_ref=application_identity.application_ref,
                allowed_space_codes=requested_space_codes,
                shop_ref=None,
                application_jti_hash=application_identity.jti_hash,
                delegation_jti_hash=None,
            )

        if requested_space_codes != {"shop_private"} or shop_ref is None or delegation_identity is None:
            raise AuthorizationRejected("NO_SCOPE_MATCH")
        if (
            delegation_identity.application_ref != application_identity.application_ref
            or delegation_identity.shop_ref != shop_ref
            or "shop_private" not in delegation_identity.allowed_space_codes
        ):
            raise AuthorizationRejected("NO_SCOPE_MATCH")
        if await self._repository.is_credential_revoked(
            delegation_identity.issuer,
            delegation_identity.jti_hash,
        ):
            raise AuthorizationRejected("CREDENTIAL_REVOKED", http_status=401)
        if not await self._repository.has_shop_grant(
            application_identity.application_ref,
            shop_ref,
            "shop_private",
        ):
            raise AuthorizationRejected("NO_SCOPE_MATCH")
        return AuthorizationContext(
            application_ref=application_identity.application_ref,
            allowed_space_codes=requested_space_codes,
            shop_ref=shop_ref,
            application_jti_hash=application_identity.jti_hash,
            delegation_jti_hash=delegation_identity.jti_hash,
        )
