"""本地预演的原子内存台账；正式任务由 SQL 持久化适配器承接。"""

import asyncio
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from .contracts import (
    BoundLogisticsEvent,
    DeliveryMode,
    LogisticsObservation,
    LogisticsUpdateResult,
    NotificationRecord,
    NotificationState,
    TrackingEvent,
    can_finish,
)


class InMemoryLogisticsRepository:
    def __init__(self, *, clock: Callable[[], datetime] | None = None) -> None:
        self._lock = asyncio.Lock()
        self._observations: dict[str, TrackingEvent] = {}
        self._notifications: dict[str, NotificationRecord] = {}
        self._clock = clock or (lambda: datetime.now(UTC))

    async def record(self, observation: LogisticsObservation) -> LogisticsUpdateResult:
        async with self._lock:
            key = observation.scope.observation_key
            latest = observation.latest
            previous = self._observations.get(key)
            if previous is None and observation.first_observation == "baseline":
                self._observations[key] = latest
                return LogisticsUpdateResult(status="baseline")
            if previous is not None and (
                latest.occurred_at <= previous.occurred_at or latest.fingerprint == previous.fingerprint
            ):
                return LogisticsUpdateResult(status="ignored")
            self._observations[key] = latest
            for notification_key, row in tuple(self._notifications.items()):
                if row.context.scope.observation_key == key and row.state == "pending":
                    self._notifications[notification_key] = row.model_copy(update={"state": "superseded"})
            context = BoundLogisticsEvent(
                scope=observation.scope, event=latest, buyer_language=observation.buyer_language
            )
            self._notifications[context.idempotency_key] = NotificationRecord(context=context)
            return LogisticsUpdateResult(status="pending", context=context, idempotency_key=context.idempotency_key)

    async def get(self, context: BoundLogisticsEvent) -> NotificationRecord | None:
        async with self._lock:
            return self._get(context)

    def _get(self, context: BoundLogisticsEvent) -> NotificationRecord | None:
        row = self._notifications.get(context.idempotency_key)
        return row if row is not None and row.context == context else None

    async def claim(self, context: BoundLogisticsEvent) -> uuid.UUID | None:
        async with self._lock:
            row = self._get(context)
            if row is None or row.state not in {"pending", "reviewing"}:
                return None
            if self._observations.get(context.scope.observation_key) != context.event:
                self._notifications[context.idempotency_key] = row.model_copy(
                    update={"state": "superseded", "reason": "newer_event"}
                )
                return None
            now = self._clock()
            if row.state == "reviewing" and row.review_lease_expires_at and row.review_lease_expires_at > now:
                return None
            token = uuid.uuid4()
            self._notifications[context.idempotency_key] = row.model_copy(
                update={
                    "state": "reviewing",
                    "review_claim_token": token,
                    "review_lease_expires_at": now + timedelta(minutes=10),
                }
            )
            return token

    async def prepare(
        self,
        context: BoundLogisticsEvent,
        text: str,
        mode: DeliveryMode,
        *,
        claim_token: uuid.UUID,
    ) -> bool:
        async with self._lock:
            row = self._get(context)
            latest = self._observations.get(context.scope.observation_key)
            if (
                row is None
                or row.state != "reviewing"
                or latest != context.event
                or row.review_claim_token != claim_token
                or row.review_lease_expires_at is None
                or row.review_lease_expires_at <= self._clock()
            ):
                return False
            # 先持久化 unknown 再进入外部端口，崩溃恢复不能重发。
            self._notifications[context.idempotency_key] = row.model_copy(
                update={"state": "unknown", "reviewed_text": text, "mode": mode, "reason": "delivery_in_flight"}
            )
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
        async with self._lock:
            row = self._get(context)
            if row is not None:
                if row.state == "reviewing" and (
                    claim_token is None
                    or row.review_claim_token != claim_token
                    or row.review_lease_expires_at is None
                    or row.review_lease_expires_at <= self._clock()
                ):
                    return
                if row.state == "unknown" and claim_token is not None and row.review_claim_token != claim_token:
                    return
            if row is not None and can_finish(row.state, state):
                self._notifications[context.idempotency_key] = row.model_copy(
                    update={"state": state, "reason": reason, "delivery_reference": reference}
                )
