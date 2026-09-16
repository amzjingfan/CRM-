"""认证服务和 RBAC 规则。"""

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.repository import find_user_by_email, find_user_by_id
from app.auth.schemas import TokenData, UserView
from app.auth.security import create_access_token, create_refresh_token, decode_token, verify_password
from app.auth.store_access import allowed_store_ids
from app.shared.config.settings import get_settings
from app.shared.database.base import User
from app.shared.database.redis import is_refresh_token_revoked
from app.shared.exceptions.errors import AppError, ErrorCode


def build_user_view(user: User) -> UserView:
    """将 ORM 用户转换为不泄露敏感字段的响应对象。"""
    role = user.roles[0].code if user.roles else "agent"
    permissions = sorted({permission.code for item in user.roles for permission in item.permissions})
    return UserView(
        id=user.id,
        name=user.name,
        email=user.email,
        role=role,
        avatar=user.avatar,
        permissions=permissions,
        store_ids=[],
    )


async def build_scoped_user_view(session: AsyncSession, user: User) -> UserView:
    """构建包含权限与店铺范围的浏览器会话用户信息。"""
    view = build_user_view(user)
    return view.model_copy(update={"store_ids": sorted(await allowed_store_ids(session, user), key=str)})


async def authenticate_user(session: AsyncSession, email: str, password: str) -> User:
    """校验登录信息，并拒绝不存在或禁用用户。"""
    user = await find_user_by_email(session, email)
    if user is None or not verify_password(password, user.password_hash):
        raise AppError(ErrorCode.INVALID_CREDENTIALS, "邮箱或密码错误", 401)
    if user.status != "active":
        raise AppError(ErrorCode.USER_DISABLED, "用户已被禁用", 403)
    # 只记录成功登录时间；失败尝试由 Redis 限流统计，不写入用户记录或日志正文。
    user.last_login_at = datetime.now(UTC)
    await session.commit()
    return user


def issue_token_data(user: User, user_view: UserView | None = None) -> TokenData:
    """为登录用户签发 Access Token 和 Refresh Token。"""
    settings = get_settings()
    return TokenData(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
        expires_in=settings.access_token_expire_minutes * 60,
        user=user_view or build_user_view(user),
    )


async def resolve_access_user(session: AsyncSession, token: str) -> User:
    """解析 Access Token 并加载当前有效用户。"""
    payload = decode_token(token, "access")
    user = await find_user_by_id(session, uuid.UUID(str(payload["sub"])))
    if user is None:
        raise AppError(ErrorCode.AUTHENTICATION_REQUIRED, "用户不存在", 401)
    if user.status != "active":
        raise AppError(ErrorCode.USER_DISABLED, "用户已被禁用", 403)
    return user


async def resolve_refresh_user(session: AsyncSession, refresh_token: str) -> User:
    """解析 Refresh Token 并加载当前有效用户。"""
    payload = decode_token(refresh_token, "refresh")
    if await is_refresh_token_revoked(str(payload["jti"])):
        raise AppError(ErrorCode.TOKEN_INVALID, "Refresh Token 已撤销", 401)
    user = await find_user_by_id(session, uuid.UUID(str(payload["sub"])))
    if user is None:
        raise AppError(ErrorCode.AUTHENTICATION_REQUIRED, "用户不存在", 401)
    if user.status != "active":
        raise AppError(ErrorCode.USER_DISABLED, "用户已被禁用", 403)
    return user


def refresh_token_ttl(payload: dict[str, object]) -> int:
    """计算撤销记录 TTL，避免黑名单记录永久占用 Redis。"""
    raw_expiry = payload.get("exp")
    if not isinstance(raw_expiry, int | float):
        raise AppError(ErrorCode.TOKEN_INVALID, "令牌过期时间无效", 401)
    expires_at = datetime.fromtimestamp(float(raw_expiry), tz=UTC)
    return max(1, int((expires_at - datetime.now(UTC)).total_seconds()))
