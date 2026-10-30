"""TikTok OAuth 对外响应与平台契约类型。"""

import uuid
from typing import Literal

from pydantic import BaseModel, Field

MAX_TIKTOK_AUTHORIZED_SHOPS = 200


class TikTokOAuthStart(BaseModel):
    """卖家授权跳转信息，不包含任何平台凭证。"""

    authorization_url: str
    expires_in: int


class TikTokOAuthShopChoice(BaseModel):
    """管理端可见的店铺选择摘要，不包含平台调用标识或凭证。"""

    id: str
    code: str
    name: str
    region: str
    seller_type: str


class TikTokOAuthJobStatus(BaseModel):
    """管理端可见的低敏后台授权结果。"""

    status: Literal["pending", "processing", "selection_required", "connected", "denied", "failed"]
    shops: list[TikTokOAuthShopChoice] = Field(default_factory=list)
    selection_expires_at: str | None = None
    error_code: str | None = None
    store_id: uuid.UUID | None = None


class TikTokOAuthShopSelection(BaseModel):
    """管理员明确勾选的本次授权店铺 ID。"""

    shop_ids: list[str] = Field(min_length=1, max_length=MAX_TIKTOK_AUTHORIZED_SHOPS)


class TikTokOAuthState(BaseModel):
    """Redis 一次性 state 绑定内容。"""

    user_id: uuid.UUID
    store_id: uuid.UUID | None = None
    return_to: str


class TikTokTokenData(BaseModel):
    """TikTok Shop Token 响应中经校验的卖家授权数据。"""

    access_token: str = Field(min_length=16, max_length=500)
    access_token_expire_in: int = Field(gt=0)
    refresh_token: str = Field(min_length=16, max_length=500)
    refresh_token_expire_in: int = Field(gt=0)
    open_id: str = Field(min_length=1, max_length=200)
    seller_name: str = Field(min_length=1, max_length=200)
    seller_base_region: str = Field(min_length=1, max_length=20)
    user_type: int
    granted_scopes: list[str] = Field(default_factory=list, max_length=100)


class TikTokTokenResponse(BaseModel):
    """TikTok Shop Token API 统一响应。"""

    code: int
    message: str = ""
    request_id: str | None = None
    data: TikTokTokenData | None = None


class TikTokAuthorizedShop(BaseModel):
    """TikTok 已授权店铺信息。"""

    id: str = Field(min_length=1, max_length=200)
    cipher: str = Field(min_length=1, max_length=200)
    code: str = Field(min_length=1, max_length=200)
    name: str = Field(min_length=1, max_length=200)
    region: str = Field(min_length=1, max_length=20)
    seller_type: str = Field(min_length=1, max_length=50)


class TikTokShopData(BaseModel):
    """已授权店铺列表容器。"""

    shops: list[TikTokAuthorizedShop] = Field(max_length=MAX_TIKTOK_AUTHORIZED_SHOPS)


class TikTokShopResponse(BaseModel):
    """Get Authorized Shops API 响应。"""

    code: int
    message: str = ""
    request_id: str | None = None
    data: TikTokShopData | None = None


class TikTokOAuthCompletion(BaseModel):
    """OAuth 回调完成后的内部跳转决策。"""

    status: Literal["connected", "selection_required", "denied"]
    return_to: str
    store_id: uuid.UUID | None = None
