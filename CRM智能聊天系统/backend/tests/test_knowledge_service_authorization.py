"""知识服务应用、空间与店铺授权交集测试。"""

from dataclasses import replace

import pytest

from app.knowledge_service.auth import ApplicationIdentity, DelegationIdentity
from app.knowledge_service.authorization import (
    ApplicationAuthority,
    ApplicationScope,
    AuthorityUnavailable,
    AuthorizationRejected,
    KnowledgeAuthorizer,
)


class FakeAuthorityRepository:
    """只在单元测试内使用的授权权威快照。"""

    def __init__(self) -> None:
        self.application = ApplicationAuthority(
            application_ref="crm-assistant",
            enabled=True,
            allowed_scopes=frozenset(
                {
                    ApplicationScope("TK", "US", "en-US", "internal_agent", "company_shared"),
                    ApplicationScope("TK", "US", "en-US", "internal_agent", "shop_private"),
                }
            ),
        )
        self.revoked_hashes: set[str] = set()
        self.shop_grants = {("crm-assistant", "shop-ref-us-001", "shop_private")}
        self.subject_grants = {("crm-assistant", "employee-ref-001", "shop-ref-us-001")}
        self.unavailable = False

    async def load_application(self, application_ref: str) -> ApplicationAuthority | None:
        if self.unavailable:
            raise RuntimeError("authority database unavailable")
        return self.application if application_ref == self.application.application_ref else None

    async def is_credential_revoked(self, issuer: str, jti_hash: str) -> bool:
        del issuer
        return jti_hash in self.revoked_hashes

    async def has_shop_grant(self, application_ref: str, shop_ref: str, space_code: str) -> bool:
        return (application_ref, shop_ref, space_code) in self.shop_grants

    async def has_delegated_subject_grant(
        self,
        application_ref: str,
        delegated_subject_ref: str,
        shop_ref: str,
    ) -> bool:
        return (application_ref, delegated_subject_ref, shop_ref) in self.subject_grants


@pytest.fixture
def application_identity() -> ApplicationIdentity:
    return ApplicationIdentity(
        application_ref="crm-assistant",
        issuer="company-service-identity",
        jti_hash="a" * 64,
    )


@pytest.fixture
def delegation_identity() -> DelegationIdentity:
    return DelegationIdentity(
        delegated_subject_ref="employee-ref-001",
        application_ref="crm-assistant",
        shop_ref="shop-ref-us-001",
        allowed_space_codes=frozenset({"shop_private"}),
        issuer="company-business-delegation",
        jti_hash="b" * 64,
    )


async def test_company_shared_requires_only_application_grant(application_identity: ApplicationIdentity) -> None:
    repository = FakeAuthorityRepository()

    context = await KnowledgeAuthorizer(repository).authorize(
        application_identity=application_identity,
        delegation_identity=None,
        requested_space_codes=frozenset({"company_shared"}),
        shop_ref=None,
        platform_code="TK",
        market_code="US",
        language_tag="en-US",
        audience_code="internal_agent",
    )

    assert context.allowed_space_codes == frozenset({"company_shared"})
    assert context.shop_ref is None


async def test_shop_private_requires_matching_delegation_and_server_grant(
    application_identity: ApplicationIdentity,
    delegation_identity: DelegationIdentity,
) -> None:
    repository = FakeAuthorityRepository()
    mismatched = replace(delegation_identity, shop_ref="another-shop")

    with pytest.raises(AuthorizationRejected):
        await KnowledgeAuthorizer(repository).authorize(
            application_identity=application_identity,
            delegation_identity=mismatched,
            requested_space_codes=frozenset({"shop_private"}),
            shop_ref="shop-ref-us-001",
            platform_code="TK",
            market_code="US",
            language_tag="en-US",
            audience_code="internal_agent",
        )

    context = await KnowledgeAuthorizer(repository).authorize(
        application_identity=application_identity,
        delegation_identity=delegation_identity,
        requested_space_codes=frozenset({"shop_private"}),
        shop_ref="shop-ref-us-001",
        platform_code="TK",
        market_code="US",
        language_tag="en-US",
        audience_code="internal_agent",
    )
    assert context.shop_ref == "shop-ref-us-001"
    assert context.delegated_subject_ref == "employee-ref-001"


async def test_disabled_delegated_subject_is_forbidden(
    application_identity: ApplicationIdentity,
    delegation_identity: DelegationIdentity,
) -> None:
    repository = FakeAuthorityRepository()
    repository.subject_grants.clear()

    with pytest.raises(AuthorizationRejected) as error:
        await KnowledgeAuthorizer(repository).authorize(
            application_identity=application_identity,
            delegation_identity=delegation_identity,
            requested_space_codes=frozenset({"shop_private"}),
            shop_ref="shop-ref-us-001",
            platform_code="TK",
            market_code="US",
            language_tag="en-US",
            audience_code="internal_agent",
        )

    assert error.value.http_status == 403
    assert error.value.reason_code == "NO_SCOPE_MATCH"


async def test_revoked_credential_is_authentication_failure(application_identity: ApplicationIdentity) -> None:
    repository = FakeAuthorityRepository()
    repository.revoked_hashes.add(application_identity.jti_hash)

    with pytest.raises(AuthorizationRejected) as error:
        await KnowledgeAuthorizer(repository).authorize(
            application_identity=application_identity,
            delegation_identity=None,
            requested_space_codes=frozenset({"company_shared"}),
            shop_ref=None,
            platform_code="TK",
            market_code="US",
            language_tag="en-US",
            audience_code="internal_agent",
        )

    assert error.value.http_status == 401


async def test_disabled_application_is_forbidden(application_identity: ApplicationIdentity) -> None:
    repository = FakeAuthorityRepository()
    repository.application = replace(repository.application, enabled=False)

    with pytest.raises(AuthorizationRejected) as error:
        await KnowledgeAuthorizer(repository).authorize(
            application_identity=application_identity,
            delegation_identity=None,
            requested_space_codes=frozenset({"company_shared"}),
            shop_ref=None,
            platform_code="TK",
            market_code="US",
            language_tag="en-US",
            audience_code="internal_agent",
        )

    assert error.value.http_status == 403


async def test_authority_failure_is_not_downgraded_to_forbidden(application_identity: ApplicationIdentity) -> None:
    repository = FakeAuthorityRepository()
    repository.unavailable = True

    with pytest.raises(AuthorityUnavailable):
        await KnowledgeAuthorizer(repository).authorize(
            application_identity=application_identity,
            delegation_identity=None,
            requested_space_codes=frozenset({"company_shared"}),
            shop_ref=None,
            platform_code="TK",
            market_code="US",
            language_tag="en-US",
            audience_code="internal_agent",
        )


async def test_wrong_market_is_request_level_forbidden(application_identity: ApplicationIdentity) -> None:
    repository = FakeAuthorityRepository()

    with pytest.raises(AuthorizationRejected) as error:
        await KnowledgeAuthorizer(repository).authorize(
            application_identity=application_identity,
            delegation_identity=None,
            requested_space_codes=frozenset({"company_shared"}),
            shop_ref=None,
            platform_code="TK",
            market_code="UK",
            language_tag="en-GB",
            audience_code="internal_agent",
        )

    assert error.value.http_status == 403
    assert error.value.reason_code == "NO_SCOPE_MATCH"
