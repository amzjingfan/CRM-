"""FastAPI 认证和权限依赖。"""

import hmac
import logging
import time
from collections.abc import Callable
from typing import Annotated

from fastapi import Cookie, Depends, Header, Request, Security
from fastapi.security import APIKeyCookie, HTTPAuthorizationCredentials, HTTPBearer

from app.auth.service import resolve_access_user
from app.shared.config.settings import get_settings
from app.shared.database.base import User
from app.shared.database.session import DbSession
from app.shared.exceptions.errors import AppError, ErrorCode

logger = logging.getLogger(__name__)

bearer_auth = HTTPBearer(
    auto_error=False,
    scheme_name="BearerAuth",
    description="非浏览器客户端使用的 JWT Bearer Token。",
)
cookie_auth = APIKeyCookie(
    name="crm_access_token",
    auto_error=False,
    scheme_name="CookieAuth",
    description="浏览器通过 HttpOnly crm_access_token Cookie 认证。",
)


async def get_current_user(
    session: DbSession,
    request: Request,
    bearer_credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Security(bearer_auth),
    ] = None,
    access_cookie: Annotated[str | None, Security(cookie_auth)] = None,
) -> User:
    """优先解析 Bearer Token，并在 OpenAPI 中声明浏览器 Cookie 认证。"""
    raw_authorization = request.headers.get("Authorization")
    token: str | None
    if raw_authorization:
        # 显式 Authorization 头优先且必须合法，不能在格式错误时静默降级到 Cookie。
        if bearer_credentials is None:
            raise AppError(ErrorCode.TOKEN_INVALID, "Token 无效", 401)
        token = bearer_credentials.credentials
    else:
        token = access_cookie
    if not token:
        raise AppError(ErrorCode.AUTHENTICATION_REQUIRED, "请求未认证", 401)
    g5_timing_enabled = request.url.path == "/v1/chat/query" and get_settings().sse_load_test_enabled
    timing_ms: dict[str, int] | None = {} if g5_timing_enabled else None
    started_at = time.perf_counter_ns()
    if timing_ms is None:
        user = await resolve_access_user(session, token)
    else:
        user = await resolve_access_user(session, token, timing_ms=timing_ms)
    if timing_ms is not None:
        trace_id = str(getattr(request.state, "trace_id", ""))
        logger.info(
            "g5_chat_auth_timing",
            extra={
                "event": "g5_chat_auth_timing",
                "trace_id": trace_id,
                "latency_ms": max(0, (time.perf_counter_ns() - started_at) // 1_000_000),
            },
        )
        for phase in ("decode", "connection", "lookup"):
            logger.info(
                "g5_chat_auth_%s_timing",
                phase,
                extra={
                    "event": f"g5_chat_auth_{phase}_timing",
                    "trace_id": trace_id,
                    "latency_ms": timing_ms[phase],
                },
            )
    return user


def require_role(required_role: str) -> Callable[..., object]:
    """生成角色校验依赖，角色不匹配时默认拒绝。"""

    async def dependency(user: Annotated[User, Depends(get_current_user)]) -> User:
        if required_role not in {role.code for role in user.roles}:
            raise AppError(ErrorCode.PERMISSION_DENIED, "没有执行该操作的权限", 403)
        return user

    return dependency


def require_permission(permission_code: str) -> Callable[..., object]:
    """生成权限校验依赖，避免只依赖前端按钮隐藏。"""

    async def dependency(user: Annotated[User, Depends(get_current_user)]) -> User:
        permissions = {permission.code for role in user.roles for permission in role.permissions}
        role_codes = {role.code for role in user.roles}
        if "admin" not in role_codes and permission_code not in permissions:
            raise AppError(ErrorCode.PERMISSION_DENIED, "没有执行该操作的权限", 403)
        return user

    return dependency


async def require_csrf(
    request: Request,
    csrf_header: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
    csrf_cookie: Annotated[str | None, Cookie(alias="crm_csrf_token")] = None,
) -> None:
    """Cookie 认证写操作必须通过来源与双提交 CSRF 校验。"""
    authorization = request.headers.get("Authorization", "")
    if authorization.startswith("Bearer "):
        return
    origin = request.headers.get("Origin")
    if origin not in get_settings().cors_origin_list:
        raise AppError(ErrorCode.PERMISSION_DENIED, "请求来源不受信任", 403)
    if not csrf_header or not csrf_cookie or not hmac.compare_digest(csrf_header, csrf_cookie):
        raise AppError(ErrorCode.PERMISSION_DENIED, "CSRF 校验失败", 403)


async def require_idempotency_key(
    idempotency_key: Annotated[
        str,
        Header(
            alias="Idempotency-Key",
            min_length=1,
            max_length=200,
            description="所有可能产生副作用的写操作必须携带；重试时复用同一值。",
        ),
    ],
) -> str:
    """强制副作用接口声明幂等边界，避免客户端漏传请求键。"""
    return idempotency_key
