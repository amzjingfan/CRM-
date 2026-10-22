"""认证 HTTP 路由。"""

import secrets
from typing import Annotated, Literal, cast

from fastapi import APIRouter, Depends, Request, Response

from app.auth.dependencies import get_current_user, require_csrf
from app.auth.schemas import BrowserSessionData, LoginRequest, RefreshRequest, TokenData, UserView
from app.auth.security import decode_token
from app.auth.service import (
    authenticate_user,
    build_scoped_user_view,
    issue_token_data,
    refresh_token_ttl,
    resolve_refresh_user,
)
from app.shared.config.settings import get_settings
from app.shared.database.base import User
from app.shared.database.redis import consume_login_attempt, revoke_refresh_token
from app.shared.database.session import DbSession
from app.shared.schemas.responses import ApiResponse

router = APIRouter(prefix="/auth", tags=["认证"])


def set_browser_cookies(response: Response, token_data: TokenData, csrf_token: str) -> None:
    """设置浏览器安全 Cookie；Refresh Token 仅发送到认证刷新路径。"""
    settings = get_settings()
    same_site = cast(Literal["lax", "strict", "none"], settings.auth_cookie_samesite)
    response.set_cookie(
        "crm_access_token",
        token_data.access_token,
        httponly=True,
        max_age=token_data.expires_in,
        path="/",
        secure=settings.auth_cookie_secure,
        samesite=same_site,
        domain=settings.auth_cookie_domain,
    )
    response.set_cookie(
        "crm_refresh_token",
        token_data.refresh_token,
        httponly=True,
        max_age=settings.refresh_token_expire_days * 86400,
        path="/v1/auth/browser",
        secure=settings.auth_cookie_secure,
        samesite=same_site,
        domain=settings.auth_cookie_domain,
    )
    response.set_cookie(
        "crm_csrf_token",
        csrf_token,
        httponly=False,
        max_age=settings.refresh_token_expire_days * 86400,
        path="/",
        secure=settings.auth_cookie_secure,
        samesite=same_site,
        domain=settings.auth_cookie_domain,
    )


def clear_browser_cookies(response: Response) -> None:
    """按创建 Cookie 时相同的路径和域清理认证状态。"""
    settings = get_settings()
    response.delete_cookie("crm_access_token", path="/", domain=settings.auth_cookie_domain)
    response.delete_cookie("crm_csrf_token", path="/", domain=settings.auth_cookie_domain)
    response.delete_cookie("crm_refresh_token", path="/v1/auth/browser", domain=settings.auth_cookie_domain)


async def enforce_login_limit(request: Request) -> None:
    """按客户端 IP 限制暴力登录；无法取得 IP 时使用 unknown 隔离桶。"""
    settings = get_settings()
    client_key = request.client.host if request.client else "unknown"
    if not await consume_login_attempt(client_key, settings.auth_login_limit, settings.auth_login_window_seconds):
        from app.shared.exceptions.errors import AppError, ErrorCode

        raise AppError(ErrorCode.RATE_LIMITED, "登录尝试过于频繁，请稍后再试", 429)


@router.post("/login", response_model=ApiResponse[TokenData])
async def login(payload: LoginRequest, session: DbSession, request: Request) -> ApiResponse[TokenData]:
    """使用登录账号或邮箱及密码登录。"""
    await enforce_login_limit(request)
    user = await authenticate_user(session, payload.identifier, payload.password)
    return ApiResponse(data=issue_token_data(user, await build_scoped_user_view(session, user)))


@router.get("/me", response_model=ApiResponse[UserView])
async def current_user(
    session: DbSession,
    user: Annotated[User, Depends(get_current_user)],
) -> ApiResponse[UserView]:
    """返回当前已认证用户。"""
    return ApiResponse(data=await build_scoped_user_view(session, user))


@router.post("/refresh", response_model=ApiResponse[TokenData])
async def refresh_token(
    payload: RefreshRequest,
    session: DbSession,
) -> ApiResponse[TokenData]:
    """使用 Refresh Token 重新签发令牌。"""
    user = await resolve_refresh_user(session, payload.refresh_token)
    return ApiResponse(data=issue_token_data(user, await build_scoped_user_view(session, user)))


@router.post("/logout", response_model=ApiResponse[dict[str, bool]])
async def logout(payload: RefreshRequest) -> ApiResponse[dict[str, bool]]:
    """撤销 Refresh Token，并要求前端清除本地令牌。"""
    token_payload = decode_token(payload.refresh_token, "refresh")
    await revoke_refresh_token(str(token_payload["jti"]), refresh_token_ttl(token_payload))
    return ApiResponse(data={"logged_out": True})


@router.post("/browser/login", response_model=ApiResponse[BrowserSessionData])
async def browser_login(
    payload: LoginRequest,
    response: Response,
    request: Request,
    session: DbSession,
) -> ApiResponse[BrowserSessionData]:
    """浏览器登录只通过 HttpOnly Cookie 持久化令牌。"""
    if request.headers.get("Origin") not in get_settings().cors_origin_list:
        from app.shared.exceptions.errors import AppError, ErrorCode

        raise AppError(ErrorCode.PERMISSION_DENIED, "请求来源不受信任", 403)
    await enforce_login_limit(request)
    user = await authenticate_user(session, payload.identifier, payload.password)
    token_data = issue_token_data(user, await build_scoped_user_view(session, user))
    set_browser_cookies(response, token_data, secrets.token_urlsafe(32))
    return ApiResponse(data=BrowserSessionData(expires_in=token_data.expires_in, user=token_data.user))


@router.post(
    "/browser/refresh",
    response_model=ApiResponse[BrowserSessionData],
    dependencies=[Depends(require_csrf)],
)
async def browser_refresh(
    response: Response,
    session: DbSession,
    request: Request,
) -> ApiResponse[BrowserSessionData]:
    """使用 HttpOnly Refresh Cookie 轮换浏览器会话。"""
    refresh_cookie = request.cookies.get("crm_refresh_token")
    if not refresh_cookie:
        from app.shared.exceptions.errors import AppError, ErrorCode

        raise AppError(ErrorCode.AUTHENTICATION_REQUIRED, "请求未认证", 401)
    user = await resolve_refresh_user(session, refresh_cookie)
    token_data = issue_token_data(user, await build_scoped_user_view(session, user))
    set_browser_cookies(response, token_data, secrets.token_urlsafe(32))
    return ApiResponse(data=BrowserSessionData(expires_in=token_data.expires_in, user=token_data.user))


@router.post(
    "/browser/logout",
    response_model=ApiResponse[dict[str, bool]],
    dependencies=[Depends(require_csrf)],
)
async def browser_logout(response: Response, request: Request) -> ApiResponse[dict[str, bool]]:
    """撤销浏览器 Refresh Token 并清除全部认证 Cookie。"""
    refresh_cookie = request.cookies.get("crm_refresh_token")
    if refresh_cookie:
        token_payload = decode_token(refresh_cookie, "refresh")
        await revoke_refresh_token(str(token_payload["jti"]), refresh_token_ttl(token_payload))
    clear_browser_cookies(response)
    return ApiResponse(data={"logged_out": True})
