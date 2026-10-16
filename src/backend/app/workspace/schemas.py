"""客服工作台接口类型。"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


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


class MessageTranslationView(BaseModel):
    """只返回给当前坐席的单条消息中文辅助译文。"""

    message_id: uuid.UUID
    target_language: Literal["zh-CN"] = "zh-CN"
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
