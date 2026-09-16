"""店铺与渠道管理 API 类型。"""

import uuid
from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field, field_validator

Platform = Literal["tiktok", "shopee", "amazon"]
ManualChannelPlatform = Literal["shopee", "amazon"]


class StoreCreate(BaseModel):
    """创建店铺请求。"""

    name: str = Field(min_length=1, max_length=200)
    code: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{1,99}$")
    timezone: str = Field(default="UTC", max_length=50)
    currency: str = Field(default="USD", min_length=3, max_length=10)

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        """店铺日指标依赖 IANA 时区，创建时必须拒绝无效值。"""
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("无效的 IANA 时区") from exc
        return value


class StoreView(BaseModel):
    """店铺响应。"""

    id: uuid.UUID
    name: str
    code: str
    status: str
    timezone: str
    currency: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ChannelCreate(BaseModel):
    """创建契约级 Mock 平台账号请求；TikTok 必须通过服务端 OAuth。"""

    store_id: uuid.UUID
    platform: ManualChannelPlatform
    external_store_id: str = Field(min_length=1, max_length=200)
    display_name: str = Field(min_length=1, max_length=200)
    access_token_ref: str = Field(min_length=1, max_length=500)
    scopes: list[str] = Field(default_factory=list, max_length=50)


class ChannelView(BaseModel):
    """脱敏后的渠道账号响应。"""

    id: uuid.UUID
    store_id: uuid.UUID
    platform: str
    external_store_id: str
    display_name: str
    status: str
    scopes: list[str]
    last_sync_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
