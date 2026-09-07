"""工作台业务工具 HTTP 类型。"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class LogisticsView(BaseModel):
    """订单物流摘要。"""

    order_id: uuid.UUID
    external_order_id: str
    tracking_number: str | None
    tracking_status: str | None
    shipped_at: datetime | None
    delivered_at: datetime | None


class ShippingAddressUpdate(BaseModel):
    """地址修改请求；完整内容不会进入工具或审计日志。"""

    recipient_name: str = Field(min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=50)
    address_line1: str = Field(min_length=1, max_length=300)
    address_line2: str | None = Field(default=None, max_length=300)
    city: str = Field(min_length=1, max_length=100)
    region: str | None = Field(default=None, max_length=100)
    postal_code: str = Field(min_length=1, max_length=30)
    country_code: str = Field(pattern=r"^[A-Z]{2}$")


class ShippingAddressResult(BaseModel):
    """Mock 地址修改结果。"""

    tool_call_id: uuid.UUID
    status: Literal["pending_confirmation"]
    mocked: Literal[True] = True
    replayed: bool = False


class CouponIssueRequest(BaseModel):
    """向客户发放优惠券。"""

    coupon_code: str = Field(pattern=r"^[A-Za-z0-9_-]+$", min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    expires_at: datetime | None = None


class CouponIssueResult(BaseModel):
    """优惠券发放结果。"""

    issuance_id: uuid.UUID
    tool_call_id: uuid.UUID
    coupon_code: str
    status: str
    mocked: bool
    replayed: bool = False
