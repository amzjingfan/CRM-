"""客服工作台接口类型。"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.agent.draft_translation import DraftTargetLanguage


class CustomerSummary(BaseModel):
    """工作台客户摘要。"""

    id: uuid.UUID
    name: str | None
    email: str | None
    avatar: str | None
    tags: list[str]


class SessionSummary(BaseModel):
    """会话列表项。"""

    id: uuid.UUID
    store_id: uuid.UUID
    platform: str
    status: str
    is_starred: bool
    closed_at: datetime | None
    unread_count: int
    assigned_user_id: uuid.UUID | None
    last_message_at: datetime | None
    last_message: str | None
    customer: CustomerSummary


class MessageView(BaseModel):
    """消息展示类型。"""

    id: uuid.UUID
    role: str
    content: str
    status: str
    created_at: datetime
    error_code: str | None
    delivery_mode: Literal["inbound", "mock", "real", "unknown"]
    message_type: str = "text"
    logistics_card: "LogisticsCardView | None" = None


class LogisticsCardView(BaseModel):
    """已核对订单的物流卡片展示快照；轨迹详情仍按需读取。"""

    order_id: str
    package_id: str | None = None
    product_name: str | None = None
    image_url: str | None = None
    sku_name: str | None = None
    quantity: int | None = None
    unit_price: str | None = None
    currency: str | None = None
    tracking_number: str | None = None
    carrier_name: str | None = None
    latest_description: str | None = None
    latest_at: datetime | None = None


class MessageTranslationView(BaseModel):
    """只返回给当前坐席的单条消息中文辅助译文。"""

    message_id: uuid.UUID
    target_language: Literal["zh-CN"] = "zh-CN"
    translated_text: str


class DraftTranslationRequest(BaseModel):
    """坐席明确请求的回复草稿翻译；不会发送平台消息。"""

    source_text: str = Field(min_length=1, max_length=2000)
    target_language: DraftTargetLanguage


class DraftTranslationView(BaseModel):
    source_text_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    target_language: DraftTargetLanguage
    translated_text: str


class OrderSummary(BaseModel):
    """订单摘要。"""

    id: uuid.UUID
    external_order_id: str
    platform: str
    status: str
    currency: str
    total_amount: Decimal
    tracking_number: str | None
    tracking_status: str | None


class PageMeta(BaseModel):
    """页码分页元信息。"""

    page: int
    page_size: int
    total: int


class SessionListData(BaseModel):
    """会话分页响应。"""

    items: list[SessionSummary]
    pagination: PageMeta
    unread_messages_total: int = Field(ge=0)


class SessionSearchRequest(BaseModel):
    """搜索词放在请求体，避免买家标识进入访问日志中的 URL。"""

    filter: Literal["all", "unread", "mine", "starred", "closed"] = "all"
    platform: str | None = None
    store_id: uuid.UUID | None = None
    status: str | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=30, ge=1, le=100)
    search_scope: Literal["all", "buyer", "order", "tracking", "product"] = "all"
    q: str | None = Field(default=None, max_length=120)
    terms: list[str] = Field(default_factory=list, max_length=20)


class SessionMessagesData(BaseModel):
    """会话详情、客户、订单和消息。"""

    session: SessionSummary
    messages: list[MessageView]
    customer: CustomerSummary
    recent_orders: list[OrderSummary]
    ai_suggestion: None = None
    pagination: PageMeta
    send_mode: Literal["disabled", "mock", "real"]
    requires_confirmation: Literal[True] = True
    translation_enabled: bool = False
    draft_translation_enabled: bool = False


class SendMessageRequest(BaseModel):
    """人工发送消息请求。"""

    content: str = Field(min_length=1, max_length=4000)
    confirmed: Literal[True]

    @field_validator("confirmed", mode="before")
    @classmethod
    def validate_literal_confirmation(cls, value: object) -> object:
        """只接受 JSON 布尔 true，拒绝 Pydantic 默认允许的数字或字符串转换。"""
        if value is not True:
            raise ValueError("发送前必须显式提交布尔值 true")
        return value


class SendLogisticsCardRequest(BaseModel):
    """只允许发送当前买家已核对订单的 TikTok 原生物流卡片。"""

    order_id: str = Field(min_length=1, max_length=200, pattern=r"^\d+$")
    package_id: str | None = Field(default=None, min_length=1, max_length=200, pattern=r"^\d+$")
    confirmed: Literal[True]

    @field_validator("confirmed", mode="before")
    @classmethod
    def validate_literal_confirmation(cls, value: object) -> object:
        if value is not True:
            raise ValueError("发送前必须显式提交布尔值 true")
        return value


class ReconcileMessageRequest(BaseModel):
    """管理员依据 TikTok 后台事实关闭未知发送结果。"""

    resolution: Literal["sent", "failed"]
    external_message_id: str | None = Field(default=None, min_length=1, max_length=200, pattern=r"^\d+$")

    @model_validator(mode="after")
    def validate_resolution_evidence(self) -> "ReconcileMessageRequest":
        """确认已发送时必须登记平台消息 ID，失败时不得伪造该证据。"""
        if self.resolution == "sent" and self.external_message_id is None:
            raise ValueError("确认已发送时必须提供平台消息 ID")
        if self.resolution == "failed" and self.external_message_id is not None:
            raise ValueError("确认失败时不能提供平台消息 ID")
        return self


class ReadResult(BaseModel):
    """已读操作结果。"""

    unread_count: int


class SessionActionResult(BaseModel):
    """会话操作后可直接合并到列表和当前详情的状态。"""

    status: str
    is_starred: bool
    closed_at: datetime | None


class StarRequest(BaseModel):
    starred: bool


class ClosedRequest(BaseModel):
    closed: bool


class AssigneeView(BaseModel):
    id: uuid.UUID
    name: str


class AssignRequest(BaseModel):
    """分配客服请求。"""

    user_id: uuid.UUID


class TransferRequest(BaseModel):
    """转人工请求。"""

    reason: str = Field(min_length=1, max_length=500)
    assign_to: uuid.UUID | None = None


class TransferResult(BaseModel):
    """转人工结果。"""

    transfer_id: uuid.UUID
    status: Literal["transferred"]
