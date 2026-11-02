"""短事务台账：基线行锁串行新观察，通知行锁只允许一个执行者。"""

import uuid
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime, timedelta
from typing import cast

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from .contracts import (
    BoundLogisticsEvent,
    DeliveryMode,
    LogisticsObservation,
    LogisticsUpdateResult,
    NotificationRecord,
    NotificationState,
    can_finish,
)
from .models import LogisticsNotification, LogisticsObservationRow
from .proof import NotificationAuthorization, text_sha256


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


class SqlAlchemyLogisticsRepository:
    def __init__(
        self,
        sessions: Callable[[], AbstractAsyncContextManager[AsyncSession]],
        *,
        authorization: Callable[[BoundLogisticsEvent, str], NotificationAuthorization] | None = None,
    ) -> None:
        self.sessions = sessions
        self.authorization = authorization

    async def record(self, observation: LogisticsObservation) -> LogisticsUpdateResult:
        scope = observation.scope
        latest = observation.latest
        async with self.sessions() as session, session.begin():
            inserted = await session.scalar(
                insert(LogisticsObservationRow)
                .values(
                    scope_key=scope.observation_key,
                    store_id=scope.store_id,
                    customer_id=scope.customer_id,
                    order_id=scope.order_id,
                    package_id=scope.package_id,
                    latest_at=latest.occurred_at,
                    latest_fingerprint=latest.fingerprint,
                )
                .on_conflict_do_nothing(index_elements=["scope_key"])
                .returning(LogisticsObservationRow.scope_key)
            )
            if inserted is not None and observation.first_observation == "baseline":
                return LogisticsUpdateResult(status="baseline")
            row = await session.scalar(
                select(LogisticsObservationRow)
                .where(
                    LogisticsObservationRow.store_id == scope.store_id,
                    LogisticsObservationRow.scope_key == scope.observation_key,
                )
                .with_for_update()
            )
            if row is None:
                return LogisticsUpdateResult(status="context_unavailable")
            previous_at = _utc(row.latest_at)
            if inserted is None and (latest.occurred_at <= previous_at or latest.fingerprint == row.latest_fingerprint):
                return LogisticsUpdateResult(status="ignored")
            row.latest_at = latest.occurred_at
            row.latest_fingerprint = latest.fingerprint
            await session.execute(
                update(LogisticsNotification)
                .where(
                    LogisticsNotification.store_id == scope.store_id,
                    LogisticsNotification.scope_key == scope.observation_key,
                    LogisticsNotification.state == "pending",
                )
                .values(state="superseded", reason="newer_event")
            )
            context = BoundLogisticsEvent(scope=scope, event=latest, buyer_language=observation.buyer_language)
            session.add(
                LogisticsNotification(
                    idempotency_key=context.idempotency_key,
                    scope_key=scope.observation_key,
                    store_id=scope.store_id,
                    customer_id=scope.customer_id,
                    conversation_id=scope.conversation_id,
                    order_id=scope.order_id,
                    context_json=context.model_dump(mode="json"),
                    state="pending",
                    mode="preview",
                )
            )
            return LogisticsUpdateResult(status="pending", context=context, idempotency_key=context.idempotency_key)

    @staticmethod
    async def _row(
        session: AsyncSession,
        context: BoundLogisticsEvent,
        *,
        lock: bool = False,
    ) -> LogisticsNotification | None:
        query = select(LogisticsNotification).where(
            LogisticsNotification.store_id == context.scope.store_id,
            LogisticsNotification.idempotency_key == context.idempotency_key,
            LogisticsNotification.customer_id == context.scope.customer_id,
            LogisticsNotification.conversation_id == context.scope.conversation_id,
            LogisticsNotification.order_id == context.scope.order_id,
        )
        row = await session.scalar(query.with_for_update() if lock else query)
        if row is None or BoundLogisticsEvent.model_validate(row.context_json) != context:
            return None
        return row

    async def get(self, context: BoundLogisticsEvent) -> NotificationRecord | None:
        async with self.sessions() as session:
            row = await self._row(session, context)
            if row is None:
                return None
            return NotificationRecord(
                context=context,
                state=cast(NotificationState, row.state),
                reason=row.reason,
                reviewed_text=row.reviewed_text,
                mode=cast(DeliveryMode, row.mode),
                delivery_reference=row.delivery_reference,
                review_claim_token=row.review_claim_token,
                review_lease_expires_at=_utc(row.review_lease_expires_at) if row.review_lease_expires_at else None,
            )

    async def claim(self, context: BoundLogisticsEvent) -> uuid.UUID | None:
        async with self.sessions() as session, session.begin():
            latest = await session.scalar(
                select(LogisticsObservationRow)
                .where(
                    LogisticsObservationRow.store_id == context.scope.store_id,
                    LogisticsObservationRow.scope_key == context.scope.observation_key,
                )
                .with_for_update()
            )
            row = await self._row(session, context, lock=True)
            if latest is None or row is None or row.state not in {"pending", "reviewing"}:
                return None
            if latest.latest_fingerprint != context.event.fingerprint:
                row.state, row.reason = "superseded", "newer_event"
                return None
            now = datetime.now(UTC)
            if row.state == "reviewing" and row.review_lease_expires_at and _utc(row.review_lease_expires_at) > now:
                return None
            token = uuid.uuid4()
            row.state = "reviewing"
            row.review_claim_token = token
            row.review_lease_expires_at = now + timedelta(minutes=10)
            return token

    async def prepare(
        self,
        context: BoundLogisticsEvent,
        text: str,
        mode: DeliveryMode,
        *,
        claim_token: uuid.UUID,
    ) -> bool:
        async with self.sessions() as session, session.begin():
            latest = await session.scalar(
                select(LogisticsObservationRow)
                .where(
                    LogisticsObservationRow.store_id == context.scope.store_id,
                    LogisticsObservationRow.scope_key == context.scope.observation_key,
                )
                .with_for_update()
            )
            row = await self._row(session, context, lock=True)
            if (
                latest is None
                or row is None
                or row.state != "reviewing"
                or row.review_claim_token != claim_token
                or row.review_lease_expires_at is None
                or _utc(row.review_lease_expires_at) <= datetime.now(UTC)
            ):
                return False
            if latest.latest_fingerprint != context.event.fingerprint:
                return False
            proof = self.authorization(context, text) if mode == "external" and self.authorization else None
            if mode == "external" and (
                proof is None or proof.event_key != context.idempotency_key or proof.text_sha256 != text_sha256(text)
            ):
                return False
            # 事务先提交潜在写入，再调用交付端口；进程丢失也不会盲重发。
            row.state = "unknown"
            row.reason = "delivery_in_flight"
            row.reviewed_text = text
            row.mode = mode
            row.authorization_json = proof.model_dump(mode="json") if proof else {}
            return True

    async def finish(
        self,
        context: BoundLogisticsEvent,
        state: NotificationState,
        reason: str | None = None,
        reference: str | None = None,
        *,
        claim_token: uuid.UUID | None = None,
    ) -> None:
        async with self.sessions() as session, session.begin():
            row = await self._row(session, context, lock=True)
            if row is not None:
                if row.state == "reviewing" and (
                    claim_token is None
                    or row.review_claim_token != claim_token
                    or row.review_lease_expires_at is None
                    or _utc(row.review_lease_expires_at) <= datetime.now(UTC)
                ):
                    return
                if row.state == "unknown" and claim_token is not None and row.review_claim_token != claim_token:
                    return
            if row is not None and can_finish(row.state, state):
                row.state, row.reason, row.delivery_reference = state, reason, reference
