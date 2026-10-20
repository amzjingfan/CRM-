"""平台统一事件和发送命令类型。"""

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, Field, TypeAdapter


class CustomerPayload(BaseModel):
    """平台客户最小标准化信息。"""

    external_id: str = Field(min_length=1, max_length=200)
    name: str | None = Field(default=None, max_length=200)
    email: str | None = Field(default=None, max_length=255)
    avatar: str | None = Field(default=None, max_length=500)


class MessageCreatedEvent(BaseModel):
    """统一入站消息事件。"""

    event_type: Literal["message.created"]
    event_id: str = Field(min_length=1, max_length=200)
    external_store_id: str = Field(min_length=1, max_length=200)
    external_conversation_id: str = Field(min_length=1, max_length=200)
    external_message_id: str = Field(min_length=1, max_length=200)
    customer: CustomerPayload
    content: str = Field(min_length=1, max_length=4000)
    created_at: datetime
    language: str | None = Field(default=None, max_length=20)


class OrderItemPayload(BaseModel):
    """统一订单商品。"""

    external_item_id: str | None = Field(default=None, max_length=200)
    product_id: str | None = Field(default=None, max_length=200)
    sku_id: str | None = Field(default=None, max_length=200)
    sku_name: str | None = Field(default=None, max_length=500)
    sku_image: str | None = Field(default=None, max_length=1000)
    sku: str | None = Field(default=None, max_length=200)
    product_name: str = Field(min_length=1, max_length=500)
    quantity: int = Field(ge=1, le=100_000)
    unit_price: Decimal = Field(ge=0)


class OrderUpdatedEvent(BaseModel):
    """统一订单更新事件。"""

    event_type: Literal["order.updated"]
    event_id: str = Field(min_length=1, max_length=200)
    external_store_id: str = Field(min_length=1, max_length=200)
    external_order_id: str = Field(min_length=1, max_length=200)
    customer: CustomerPayload | None = None
    status: str = Field(min_length=1, max_length=30)
    payment_status: str | None = Field(default=None, max_length=30)
    fulfillment_status: str | None = Field(default=None, max_length=30)
    currency: str = Field(min_length=3, max_length=10)
    total_amount: Decimal = Field(ge=0)
    payment_breakdown: dict[str, str] = Field(default_factory=dict)
    tracking_number: str | None = Field(default=None, max_length=200)
    tracking_status: str | None = Field(default=None, max_length=100)
    ordered_at: datetime | None = None
    items: list[OrderItemPayload] = Field(default_factory=list, max_length=500)


class ReviewUpdatedEvent(BaseModel):
    """统一创建或更新评价事件。"""

    event_type: Literal["review.created", "review.updated"]
    event_id: str = Field(min_length=1, max_length=200)
    external_store_id: str = Field(min_length=1, max_length=200)
    external_review_id: str = Field(min_length=1, max_length=200)
    external_order_id: str | None = Field(default=None, max_length=200)
    customer: CustomerPayload | None = None
    rating: int = Field(ge=1, le=5)
    content: str | None = Field(default=None, max_length=4000)
    reviewed_at: datetime


PlatformEvent = Annotated[
    MessageCreatedEvent | OrderUpdatedEvent | ReviewUpdatedEvent,
    Field(discriminator="event_type"),
]
platform_event_adapter: TypeAdapter[PlatformEvent] = TypeAdapter(PlatformEvent)


class SendMessageCommand(BaseModel):
    """统一人工发送命令。"""

    external_conversation_id: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=4000)
    idempotency_key: str = Field(min_length=1, max_length=200)
    human_confirmed: bool = False


class SendMessageResult(BaseModel):
    """平台发送结果。"""

    external_message_id: str | None = None
    status: Literal["sent", "failed", "unknown"]
    mock: bool = True
    error_code: str | None = None


class WebhookAccepted(BaseModel):
    """Webhook 快速接收响应。"""

    event_id: str
    duplicate: bool
    accepted: bool


class TikTokAuthorizationLifecycleEvent(BaseModel):
    """TikTok 店铺授权生命周期事件，不进入通用消息/订单事件联合。"""

    action: Literal["deauthorized", "expiring"]
    event_id: str = Field(min_length=1, max_length=200)
    external_store_id: str = Field(min_length=1, max_length=200)
    expiration_time: datetime | None = None


ResolvedPlatformEvent = PlatformEvent | TikTokAuthorizationLifecycleEvent | None
