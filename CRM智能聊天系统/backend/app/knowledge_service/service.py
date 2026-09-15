"""授权后的证据检索端口和低敏审计契约。"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.knowledge_service.authorization import AuthorizationContext
from app.knowledge_service.schemas import EvidenceSearchRequest, EvidenceSearchResponse, SearchStatus, StableReasonCode


@dataclass(frozen=True, slots=True)
class EvidenceSearchRequestContext:
    request: EvidenceSearchRequest
    authorization: AuthorizationContext
    trace_id: str


class EvidenceSearcher(Protocol):
    async def search(self, context: EvidenceSearchRequestContext) -> EvidenceSearchResponse: ...


class IndexUnavailableSearcher:
    """K3 激活完整索引代次前的安全默认实现。"""

    async def search(self, context: EvidenceSearchRequestContext) -> EvidenceSearchResponse:
        return EvidenceSearchResponse(
            status=SearchStatus.UNAVAILABLE,
            request_id=context.request.request_id,
            trace_id=context.trace_id,
            reason_code=StableReasonCode.INDEX_GENERATION_UNAVAILABLE,
            retryable=True,
        )


@dataclass(frozen=True, slots=True)
class AuditRecord:
    request_id: str
    trace_id: str
    application_ref: str | None
    shop_ref_hash: str | None
    requested_space_codes: tuple[str, ...]
    decision: str
    reason_code: str | None
    jti_hash: str | None
    evidence_count: int
    latency_ms: int


class AuditSink(Protocol):
    async def record(self, event: AuditRecord) -> None: ...


class ReadinessProbe(Protocol):
    async def check(self) -> None: ...


class DatabaseReadinessProbe:
    """就绪端点必须实际读取知识服务专属数据库。"""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def check(self) -> None:
        async with self._session_factory() as session:
            await session.execute(text("SELECT 1"))


class NullAuditSink:
    """仅用于本地应用创建；部署入口使用 SQL 审计。"""

    async def record(self, event: AuditRecord) -> None:
        del event


def hash_shop_ref(shop_ref: str | None) -> str | None:
    if shop_ref is None:
        return None
    return hashlib.sha256(shop_ref.encode("utf-8")).hexdigest()
