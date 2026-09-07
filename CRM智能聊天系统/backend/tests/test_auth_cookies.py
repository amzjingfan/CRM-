"""浏览器认证 Cookie 安全属性测试。"""

import uuid
from typing import cast

import pytest
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response

from app.auth.dependencies import get_current_user
from app.auth.router import clear_browser_cookies, set_browser_cookies
from app.auth.schemas import TokenData, UserView
from app.shared.exceptions.errors import AppError, ErrorCode


def token_data() -> TokenData:
    """构造不包含真实凭证的测试令牌数据。"""
    return TokenData(
        access_token="access-token-for-test",
        refresh_token="refresh-token-for-test",
        expires_in=7200,
        user=UserView(
            id=uuid.uuid4(),
            name="测试用户",
            email="test@example.com",
            role="agent",
            permissions=["workspace.view"],
            store_ids=[],
        ),
    )


def test_browser_cookies_are_http_only_except_csrf() -> None:
    """JWT Cookie 不允许 JavaScript 读取，CSRF Cookie 用于双提交。"""
    response = Response()
    set_browser_cookies(response, token_data(), "csrf-token")
    cookies = response.headers.getlist("set-cookie")
    access = next(value for value in cookies if value.startswith("crm_access_token="))
    refresh = next(value for value in cookies if value.startswith("crm_refresh_token="))
    csrf = next(value for value in cookies if value.startswith("crm_csrf_token="))
    assert "HttpOnly" in access
    assert "HttpOnly" in refresh
    assert "HttpOnly" not in csrf
    assert "SameSite=lax" in access
    assert "Path=/v1/auth/browser" in refresh


def test_logout_clears_all_browser_cookies() -> None:
    """退出必须覆盖三个 Cookie 的清理路径。"""
    response = Response()
    clear_browser_cookies(response)
    cookies = response.headers.getlist("set-cookie")
    assert sum("Max-Age=0" in value for value in cookies) == 3


@pytest.mark.asyncio
async def test_malformed_authorization_header_cannot_fallback_to_cookie() -> None:
    """显式但非法的认证头必须失败，不能借有效 Cookie 降级绕过。"""
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/v1/auth/me",
            "headers": [(b"authorization", b"Basic invalid")],
        }
    )
    with pytest.raises(AppError) as caught:
        await get_current_user(
            session=cast(AsyncSession, object()),
            request=request,
            bearer_credentials=None,
            access_cookie="otherwise-valid-cookie",
        )
    assert caught.value.code == ErrorCode.TOKEN_INVALID
