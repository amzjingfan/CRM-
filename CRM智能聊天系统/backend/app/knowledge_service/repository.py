"""知识服务授权权威的 SQLAlchemy 读取实现。"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.knowledge_service.authorization import ApplicationAuthority, ApplicationScope
from app.knowledge_service.models import (
    ApplicationSpaceGrant,
    AuditEvent,
    KnowledgeApplication,
    RevokedCredential,
    ShopSpaceGrant,
)
from app.knowledge_service.service import AuditRecord


class SqlAlchemyAuthorityRepository:
    """每次判定查询权威表，不信任 Token 自声明的 grant。"""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def load_application(self, application_ref: str) -> ApplicationAuthority | None:
        async with self._session_factory() as session:
            application = await session.scalar(
                select(KnowledgeApplication).where(KnowledgeApplication.application_ref == application_ref)
            )
            if application is None:
                return None
            grants = (
                await session.scalars(
                    select(ApplicationSpaceGrant).where(
                        ApplicationSpaceGrant.application_ref == application_ref,
                        ApplicationSpaceGrant.enabled.is_(True),
                    )
                )
            ).all()
            return ApplicationAuthority(
                application_ref=application.application_ref,
                enabled=application.enabled,
                allowed_scopes=frozenset(
                    ApplicationScope(
                        grant.platform_code,
                        grant.market_code,
                        grant.language_tag,
                        grant.audience_code,
                        grant.space_code,
                    )
                    for grant in grants
                ),
            )

    async def is_credential_revoked(self, issuer: str, jti_hash: str) -> bool:
        async with self._session_factory() as session:
            credential_id = await session.scalar(
                select(RevokedCredential.id).where(
                    RevokedCredential.issuer == issuer,
                    RevokedCredential.jti_hash == jti_hash,
                    RevokedCredential.expires_at >= datetime.now(UTC),
                )
            )
            return credential_id is not None

    async def has_shop_grant(self, application_ref: str, shop_ref: str, space_code: str) -> bool:
        now = datetime.now(UTC)
        async with self._session_factory() as session:
            grant_id = await session.scalar(
                select(ShopSpaceGrant.id).where(
                    ShopSpaceGrant.application_ref == application_ref,
                    ShopSpaceGrant.shop_ref == shop_ref,
                    ShopSpaceGrant.space_code == space_code,
                    ShopSpaceGrant.enabled.is_(True),
                    ShopSpaceGrant.valid_from <= now,
                    or_(ShopSpaceGrant.valid_until.is_(None), ShopSpaceGrant.valid_until >= now),
                )
            )
            return grant_id is not None


class SqlAlchemyAuditSink:
    """每个决策单独提交，保证检索失败仍可审计。"""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def record(self, event: AuditRecord) -> None:
        async with self._session_factory() as session:
            session.add(
                AuditEvent(
                    request_id=event.request_id,
                    application_ref=event.application_ref,
                    shop_ref_hash=event.shop_ref_hash,
                    requested_space_codes=list(event.requested_space_codes),
                    decision=event.decision,
                    reason_code=event.reason_code,
                    jti_hash=event.jti_hash,
                    evidence_count=event.evidence_count,
                    latency_ms=event.latency_ms,
                    created_at=datetime.now(UTC),
                )
            )
            await session.commit()
