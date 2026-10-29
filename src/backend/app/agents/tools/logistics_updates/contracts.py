"""物流观察只接受已核验服务端对象，模型只提供候选表达。"""

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Literal, Protocol

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

NotificationState = Literal[
    "pending", "reviewing", "superseded", "blocked", "rejected", "previewed", "succeeded", "failed", "unknown"
]
DeliveryMode = Literal["preview", "external"]


def can_finish(current: str, target: NotificationState) -> bool:
    if current == "reviewing":
        return target in {"blocked", "rejected", "failed", "superseded"}
    return current == "unknown" and target in {"unknown", "failed", "succeeded", "previewed"}


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class LogisticsScope(FrozenModel):
    store_id: uuid.UUID
    customer_id: uuid.UUID
    conversation_id: uuid.UUID
    order_id: uuid.UUID
    package_id: str = Field(min_length=1, max_length=200)

    @property
    def observation_key(self) -> str:
        # 同一买家的订单包裹即使换了会话，也不重新补发历史节点。
        return _digest(self.model_dump(mode="json", exclude={"conversation_id"}))


class TrackingEvent(FrozenModel):
    occurred_at: AwareDatetime
    status: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=2000)

    @field_validator("occurred_at")
    @classmethod
    def utc_time(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)

    @property
    def fingerprint(self) -> str:
        return _digest(
            {
                "at": self.occurred_at.isoformat(),
                "status": self.status.strip().casefold(),
                "description": " ".join(self.description.split()),
            }
        )


class LogisticsObservation(FrozenModel):
    scope: LogisticsScope
    buyer_language: str = Field(min_length=1, max_length=35)
    events: tuple[TrackingEvent, ...] = Field(min_length=1)
    # 仅官方订单/节点时间晚于策略启用 cutoff 才可 notify；CRM 首次同步时间不作凭据，未知仍 baseline。
    first_observation: Literal["baseline", "notify"] = "baseline"

    @property
    def latest(self) -> TrackingEvent:
        return max(self.events, key=lambda item: (item.occurred_at, item.fingerprint))


class BoundLogisticsEvent(FrozenModel):
    scope: LogisticsScope
    event: TrackingEvent
    buyer_language: str = Field(min_length=1, max_length=35)

    @property
    def idempotency_key(self) -> str:
        return "logistics:" + _digest([self.scope.observation_key, self.event.fingerprint])


class AuthorizationSnapshot(FrozenModel):
    global_enabled: bool = False
    store_enabled: bool = False
    tool_bound: bool = False
    grant_active: bool = False
    identity_verified: bool = False
    conversation_valid: bool = False
    send_window_valid: bool = False
    scope_available: bool = False

    @property
    def blocking_reason(self) -> str | None:
        return next((name for name, enabled in self.model_dump().items() if not enabled), None)


class NotificationArguments(FrozenModel):
    candidate_text: str = Field(min_length=1, max_length=2000, description="仅表达当前物流事件的买家语言通知正文")


class ReviewDecision(FrozenModel):
    status: Literal["approved", "rejected"]
    text: str | None = Field(default=None, min_length=1, max_length=2000)
    reason: str = Field(default="review_rejected", pattern=r"^[a-z_]{1,80}$")

    @model_validator(mode="after")
    def approved_text(self) -> "ReviewDecision":
        if self.status == "approved" and (self.text is None or not self.text.strip()):
            raise ValueError("已复核通知必须包含正文")
        if self.text and len(self.text.encode("utf-16-le")) // 2 > 2000:
            raise ValueError("通知正文超过平台长度预算")
        return self


class PreparedLogisticsNotification(FrozenModel):
    """复核后仅含一条最新物流文字；交付适配器据此生成不可变计划。"""

    scope: LogisticsScope
    event: TrackingEvent
    buyer_language: str
    idempotency_key: str
    text: str


class DeliveryReceipt(FrozenModel):
    status: Literal["succeeded", "failed", "unknown"]
    reference: str | None = Field(default=None, max_length=200)


class NotificationRecord(FrozenModel):
    context: BoundLogisticsEvent
    state: NotificationState = "pending"
    reason: str | None = None
    reviewed_text: str | None = None
    mode: DeliveryMode = "preview"
    delivery_reference: str | None = None
    review_claim_token: uuid.UUID | None = None
    review_lease_expires_at: AwareDatetime | None = None


class LogisticsUpdateResult(FrozenModel):
    status: Literal[
        "baseline",
        "ignored",
        "pending",
        "reviewing",
        "superseded",
        "blocked",
        "rejected",
        "previewed",
        "succeeded",
        "failed",
        "unknown",
        "context_unavailable",
    ]
    reason: str | None = None
    context: BoundLogisticsEvent | None = None
    idempotency_key: str | None = None


class LogisticsRepository(Protocol):
    async def record(self, observation: LogisticsObservation) -> LogisticsUpdateResult: ...

    async def get(self, context: BoundLogisticsEvent) -> NotificationRecord | None: ...

    async def claim(self, context: BoundLogisticsEvent) -> uuid.UUID | None: ...

    async def prepare(
        self,
        context: BoundLogisticsEvent,
        text: str,
        mode: DeliveryMode,
        *,
        claim_token: uuid.UUID,
    ) -> bool: ...

    async def finish(
        self,
        context: BoundLogisticsEvent,
        state: NotificationState,
        reason: str | None = None,
        reference: str | None = None,
        *,
        claim_token: uuid.UUID | None = None,
    ) -> None: ...


class NotificationDeliveryPort(Protocol):
    async def preview(self, notification: PreparedLogisticsNotification) -> DeliveryReceipt: ...

    async def deliver(self, notification: PreparedLogisticsNotification) -> DeliveryReceipt: ...

    async def reconcile(self, notification: PreparedLogisticsNotification) -> DeliveryReceipt: ...
