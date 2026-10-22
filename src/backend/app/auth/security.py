"""密码、JWT 和 Refresh Token 黑名单安全能力。"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import cast

import jwt
from passlib.context import CryptContext

from app.shared.config.settings import get_settings
from app.shared.exceptions.errors import AppError, ErrorCode

password_context = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(password: str) -> str:
    """生成不可逆密码哈希。"""
    return str(password_context.hash(password))


def verify_password(password: str, password_hash: str) -> bool:
    """校验明文密码与哈希是否匹配。"""
    return bool(password_context.verify(password, password_hash))


def create_token(user_id: uuid.UUID, token_type: str, expires_delta: timedelta, auth_version: int = 0) -> str:
    """创建只包含身份、类型和过期时间的 JWT。"""
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
        "jti": str(uuid.uuid4()),
        "ver": auth_version,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: uuid.UUID, auth_version: int = 0) -> str:
    """创建短时 Access Token。"""
    settings = get_settings()
    return create_token(user_id, "access", timedelta(minutes=settings.access_token_expire_minutes), auth_version)


def create_refresh_token(user_id: uuid.UUID, auth_version: int = 0) -> str:
    """创建长时 Refresh Token。"""
    settings = get_settings()
    return create_token(user_id, "refresh", timedelta(days=settings.refresh_token_expire_days), auth_version)


def decode_token(token: str, expected_type: str) -> dict[str, object]:
    """解析并校验 JWT 类型，统一转换 JWT 库异常。"""
    settings = get_settings()
    try:
        payload = cast(
            dict[str, object],
            jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]),
        )
    except jwt.ExpiredSignatureError as error:
        raise AppError(ErrorCode.TOKEN_EXPIRED, "令牌已过期", 401) from error
    except jwt.InvalidTokenError as error:
        raise AppError(ErrorCode.TOKEN_INVALID, "令牌无效", 401) from error
    if payload.get("type") != expected_type or not payload.get("sub") or not payload.get("jti"):
        raise AppError(ErrorCode.TOKEN_INVALID, "令牌类型无效", 401)
    return payload
