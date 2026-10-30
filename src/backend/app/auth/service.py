"""认证服务和 RBAC 规则。"""

import time
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.repository import find_user_by_email, find_user_by_id, find_user_by_login_name
from app.auth.schemas import TokenData, UserView
from app.auth.security import create_access_token, create_refresh_token, decode_token, verify_password
from app.auth.store_access import allowed_store_ids
from app.shared.config.settings import get_settings
from app.shared.database.base import User, UserLoginSession
from app.shared.database.redis import is_refresh_token_revoked
from app.shared.exceptions.errors import AppError, ErrorCode


def build_user_view(user: User) -> UserView:
    """将 ORM 用户转换为不泄露敏感字段的响应对象。"""
    role_codes = {item.code for item in user.roles}
    role = next((code for code in ("admin", "supervisor", "agent") if code in role_codes), "agent")
    permissions = sorted({permission.code for item in user.roles for permission in item.permissions})
    return UserView(
        id=user.id,
        name=user.name,
        email=user.email,
        login_name=user.login_name,
        role=role,
        avatar=user.avatar,
        permissions=permissions,
        store_ids=[],
    )


async def build_scoped_user_view(session: AsyncSession, user: User) -> UserView:
    """构建包含权限与店铺范围的浏览器会话用户信息。"""
    view = build_user_view(user)
    return view.model_copy(update={"store_ids": sorted(await allowed_store_ids(session, user), key=str)})


async def authenticate_user(session: AsyncSession, identifier: str, password: str) -> User:
    """校验登录信息，并拒绝不存在或禁用用户。"""
    value = identifier.strip().lower()
    user = await (find_user_by_email(session, value) if "@" in value else find_user_by_login_name(session, value))
    if user is None or not verify_password(password, user.password_hash):
        raise AppError(ErrorCode.INVALID_CREDENTIALS, "账号、邮箱或密码错误", 401)
    if user.status != "active":
        raise AppError(ErrorCode.USER_DISABLED, "用户已被禁用", 403)
    # 只记录成功登录时间；失败尝试由 Redis 限流统计，不写入用户记录或日志正文。
    user.last_login_at = datetime.now(UTC)
    await session.commit()
    return user


def issue_token_data(user: User, user_view: UserView | None = None, session_id: uuid.UUID | None = None) -> TokenData:
    """为登录用户签发 Access Token 和 Refresh Token。"""
    settings = get_settings()
    return TokenData(
        access_token=create_access_token(user.id, user.auth_version or 0, session_id),
        refresh_token=create_refresh_token(user.id, user.auth_version or 0, session_id),
        expires_in=settings.access_token_expire_minutes * 60,
        user=user_view or build_user_view(user),
    )


def _login_session_id(payload: dict[str, object]) -> uuid.UUID | None:
    raw_id = payload.get("sid")
    if not raw_id:
        return None
    try:
        return uuid.UUID(str(raw_id))
    except (TypeError, ValueError) as exc:
        raise AppError(ErrorCode.TOKEN_INVALID, "登录会话标识无效", 401) from exc


async def start_login_session(session: AsyncSession, user: User) -> uuid.UUID:
    """成功登录后记录可过期的在线会话。"""
    login = UserLoginSession(
        id=uuid.uuid4(),
        user_id=user.id,
        expires_at=datetime.now(UTC) + timedelta(days=get_settings().refresh_token_expire_days),
    )
    session.add(login)
    await session.commit()
    return login.id


async def renew_login_session(session: AsyncSession, user: User, refresh_token: str) -> uuid.UUID:
    """轮换令牌时续期同一登录；迁移前令牌首次刷新建立会话。"""
    payload = decode_token(refresh_token, "refresh")
    login_id = _login_session_id(payload)
    login = await session.get(UserLoginSession, login_id) if login_id else None
    if login_id and (
        login is None
        or login.user_id != user.id
        or login.revoked_at is not None
        or login.expires_at <= datetime.now(UTC)
    ):
        raise AppError(ErrorCode.TOKEN_INVALID, "登录会话已失效", 401)
    if login is None:
        return await start_login_session(session, user)
    login.expires_at = datetime.now(UTC) + timedelta(days=get_settings().refresh_token_expire_days)
    await session.commit()
    return login.id


async def end_login_session(session: AsyncSession, refresh_token: str) -> None:
    payload = decode_token(refresh_token, "refresh")
    login_id = _login_session_id(payload)
    if login_id is None:
        return
    login = await session.get(UserLoginSession, login_id)
    if login is not None and login.user_id == uuid.UUID(str(payload["sub"])):
        login.revoked_at = datetime.now(UTC)
        await session.commit()


async def resolve_access_user(session: AsyncSession, token: str, timing_ms: dict[str, int] | None = None) -> User:
    """解析 Access Token 并加载当前有效用户。"""
    started_at = time.perf_counter_ns()
    payload = decode_token(token, "access")
    user_id = uuid.UUID(str(payload["sub"]))
    if timing_ms is not None:
        timing_ms["decode"] = max(0, (time.perf_counter_ns() - started_at) // 1_000_000)
        # 先验证令牌，再单独量取连接池等待；普通请求仍沿用原查询路径。
        started_at = time.perf_counter_ns()
        await session.connection()
        timing_ms["connection"] = max(0, (time.perf_counter_ns() - started_at) // 1_000_000)
        started_at = time.perf_counter_ns()
    user = await find_user_by_id(session, user_id)
    if timing_ms is not None:
        timing_ms["lookup"] = max(0, (time.perf_counter_ns() - started_at) // 1_000_000)
    if user is None:
        raise AppError(ErrorCode.AUTHENTICATION_REQUIRED, "用户不存在", 401)
    if user.status != "active":
        raise AppError(ErrorCode.USER_DISABLED, "用户已被禁用", 403)
    if payload.get("ver", 0) != (user.auth_version or 0):
        raise AppError(ErrorCode.TOKEN_INVALID, "密码已修改，请重新登录", 401)
    login_id = _login_session_id(payload)
    if login_id is not None:
        login = await session.scalar(
            select(UserLoginSession.id).where(
                UserLoginSession.id == login_id,
                UserLoginSession.user_id == user.id,
                UserLoginSession.revoked_at.is_(None),
                UserLoginSession.expires_at > datetime.now(UTC),
            )
        )
        if login is None:
            raise AppError(ErrorCode.TOKEN_INVALID, "登录会话已失效", 401)
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
    if payload.get("ver", 0) != (user.auth_version or 0):
        raise AppError(ErrorCode.TOKEN_INVALID, "密码已修改，请重新登录", 401)
    login_id = _login_session_id(payload)
    if login_id is not None:
        login = await session.scalar(
            select(UserLoginSession).where(
                UserLoginSession.id == login_id,
                UserLoginSession.user_id == user.id,
                UserLoginSession.revoked_at.is_(None),
                UserLoginSession.expires_at > datetime.now(UTC),
            )
        )
        if login is None:
            raise AppError(ErrorCode.TOKEN_INVALID, "登录会话已失效", 401)
    return user


def refresh_token_ttl(payload: dict[str, object]) -> int:
    """计算撤销记录 TTL，避免黑名单记录永久占用 Redis。"""
    raw_expiry = payload.get("exp")
    if not isinstance(raw_expiry, int | float):
        raise AppError(ErrorCode.TOKEN_INVALID, "令牌过期时间无效", 401)
    expires_at = datetime.fromtimestamp(float(raw_expiry), tz=UTC)
    return max(1, int((expires_at - datetime.now(UTC)).total_seconds()))
