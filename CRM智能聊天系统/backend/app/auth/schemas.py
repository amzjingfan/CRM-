"""认证请求和响应 DTO。"""

import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    """登录请求。"""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserView(BaseModel):
    """对外用户信息，不暴露密码哈希。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    email: EmailStr
    role: str
    avatar: str | None = None
    permissions: list[str] = Field(default_factory=list)
    store_ids: list[uuid.UUID] = Field(default_factory=list)


class TokenData(BaseModel):
    """Token 响应数据。"""

    access_token: str
    refresh_token: str
    expires_in: int
    user: UserView


class RefreshRequest(BaseModel):
    """刷新令牌请求。"""

    refresh_token: str = Field(min_length=20)


class BrowserSessionData(BaseModel):
    """浏览器 Cookie 登录响应，不把 JWT 暴露给 JavaScript。"""

    expires_in: int
    user: UserView
