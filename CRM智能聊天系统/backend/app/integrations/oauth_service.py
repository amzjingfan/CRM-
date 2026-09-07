"""TikTok OAuth 一次性状态、店铺绑定和凭证生命周期。"""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.models import AuditLog
from app.auth.repository import find_user_by_id
from app.auth.store_access import ensure_store_access
from app.integrations.credential_crypto import decrypt_credential, encrypt_credential
from app.integrations.oauth_schemas import TikTokOAuthCompletion, TikTokOAuthStart, TikTokOAuthState, TikTokTokenData
from app.integrations.tiktok_oauth import TikTokOAuthClient, build_authorization_url
from app.shared.config.settings import Settings, get_settings
from app.shared.database.base import User
from app.shared.database.redis import consume_tiktok_oauth_state, save_tiktok_oauth_state
from app.shared.exceptions.errors import AppError, ErrorCode
from app.stores.models import ChannelAccount
from app.stores.repository import (
    claim_tiktok_channel_for_refresh,
    find_channel_by_external_store,
    find_channel_by_store_platform,
    get_active_store,
)

SELLER_USER_TYPES = {0, 4, 5}
DEFAULT_RETURN_TO = "/settings/channels"


def validate_return_to(value: str) -> str:
    """限制 OAuth 回跳到站内渠道页，禁止利用 return_to 开放重定向。"""
    if value != DEFAULT_RETURN_TO:
        raise AppError(ErrorCode.VALIDATION_ERROR, "OAuth 回跳地址无效", 400)
    return value


def validate_oauth_runtime(settings: Settings) -> None:
    """在跳转第三方前校验 OAuth 最小配置，避免产生无法完成的授权流程。"""
    secret = settings.tiktok_app_secret
    credential_key = settings.tiktok_credential_encryption_key
    if settings.tiktok_app_key in {"", "mock-app"} or not settings.tiktok_service_id:
        raise AppError(ErrorCode.THIRD_PARTY_ERROR, "TikTok OAuth 尚未配置", 503)
    if secret is None or len(secret.get_secret_value()) < 16:
        raise AppError(ErrorCode.THIRD_PARTY_ERROR, "TikTok OAuth 尚未配置", 503)
    if credential_key is None or len(credential_key.get_secret_value()) < 32:
        raise AppError(ErrorCode.THIRD_PARTY_ERROR, "TikTok 凭证加密尚未配置", 503)
    try:
        settings.validate_tiktok_oauth_redirect_uri()
    except ValueError as exc:
        # 只返回稳定低敏错误，不把错误配置值带入 API 或日志。
        raise AppError(ErrorCode.THIRD_PARTY_ERROR, "TikTok OAuth 回调配置无效", 503) from exc


def _oauth_context(store_id: uuid.UUID, external_store_id: str, credential_type: str) -> str:
    """用租户、外部店铺和凭证类型构造 GCM 认证上下文。"""
    return f"tiktok:{store_id}:{external_store_id}:{credential_type}"


def _credential_key(settings: Settings) -> str:
    """只在需要加解密的服务端路径读取主密钥。"""
    key = settings.tiktok_credential_encryption_key
    if key is None or len(key.get_secret_value()) < 32:
        raise AppError(ErrorCode.THIRD_PARTY_ERROR, "TikTok 凭证加密尚未配置", 503)
    return key.get_secret_value()


def decrypt_tiktok_access_token(channel: ChannelAccount, settings: Settings) -> str:
    """解密已连接渠道的 Access Token，仅供服务端 TikTok 客户端使用。

    返回值只能短暂驻留在调用进程内存，不得进入日志、异常、API 响应或
    测试报告。凭证上下文同时绑定租户、外部店铺和凭证类型，防止密文
    被复制到其他渠道后继续解密。
    """
    if channel.platform != "tiktok" or channel.status != "connected":
        raise AppError(ErrorCode.TOKEN_INVALID, "TikTok 渠道未连接", 401)
    try:
        return decrypt_credential(
            channel.access_token_ref,
            _credential_key(settings),
            _oauth_context(channel.store_id, channel.external_store_id, "access"),
        )
    except (ValueError, UnicodeError) as exc:
        raise AppError(ErrorCode.TOKEN_INVALID, "TikTok 授权凭证无效，请重新授权", 401) from exc


def _expiration(value: int) -> datetime:
    """将 TikTok 返回的 Unix 过期时间转为 UTC 时间。"""
    try:
        expires_at = datetime.fromtimestamp(value, UTC)
    except (OverflowError, OSError, ValueError) as exc:
        raise AppError(ErrorCode.THIRD_PARTY_ERROR, "TikTok Token 过期时间无效", 502) from exc
    if expires_at <= datetime.now(UTC):
        raise AppError(ErrorCode.THIRD_PARTY_ERROR, "TikTok Token 已过期", 502)
    return expires_at


def _validate_token_contract(token: TikTokTokenData, settings: Settings) -> None:
    """只接受卖家授权和完整 Scope，拒绝创作者或 Partner 误授权。"""
    if token.user_type not in SELLER_USER_TYPES:
        raise AppError(ErrorCode.PERMISSION_DENIED, "TikTok 授权主体不是卖家", 403)
    missing = settings.tiktok_required_scope_set.difference(token.granted_scopes)
    if missing:
        raise AppError(ErrorCode.PERMISSION_DENIED, "TikTok 授权权限不完整", 403)
    _expiration(token.access_token_expire_in)
    _expiration(token.refresh_token_expire_in)


async def start_tiktok_oauth(
    session: AsyncSession,
    user: User,
    store_id: uuid.UUID,
    return_to: str = DEFAULT_RETURN_TO,
    settings: Settings | None = None,
) -> TikTokOAuthStart:
    """校验权限后生成 Redis 一次性 state 和 TikTok 卖家授权地址。"""
    runtime = settings or get_settings()
    validate_oauth_runtime(runtime)
    await ensure_store_access(session, user, store_id)
    if await get_active_store(session, store_id) is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "资源不存在", 404)
    safe_return_to = validate_return_to(return_to)
    state = secrets.token_urlsafe(32)
    payload = TikTokOAuthState(user_id=user.id, store_id=store_id, return_to=safe_return_to)
    try:
        stored = await save_tiktok_oauth_state(
            state,
            {key: str(value) for key, value in payload.model_dump().items()},
            runtime.tiktok_oauth_state_ttl_seconds,
        )
    except Exception as exc:
        raise AppError(ErrorCode.THIRD_PARTY_ERROR, "OAuth 状态服务暂时不可用", 503) from exc
    if not stored:
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "OAuth 状态创建失败，请重试", 409)
    return TikTokOAuthStart(
        authorization_url=build_authorization_url(runtime, state),
        expires_in=runtime.tiktok_oauth_state_ttl_seconds,
    )


async def _record_failed_oauth(
    session: AsyncSession,
    user: User,
    store_id: uuid.UUID,
    error_code: str,
) -> None:
    """只记录稳定错误码，不保存 code、state、Token 或平台原始错误。"""
    session.add(
        AuditLog(
            store_id=store_id,
            actor_type="user",
            actor_id=user.id,
            action="channel.oauth",
            resource_type="channel_account",
            result="failed",
            after_data={"platform": "tiktok", "error_code": error_code},
        )
    )
    await session.commit()


async def complete_tiktok_oauth(
    session: AsyncSession,
    state: str,
    auth_code: str | None,
    provider_error: str | None,
    settings: Settings | None = None,
    client: TikTokOAuthClient | None = None,
) -> TikTokOAuthCompletion:
    """原子消费 state，并恢复发起用户后完成跨浏览器卖家授权。"""
    runtime = settings or get_settings()
    validate_oauth_runtime(runtime)
    try:
        raw_state = await consume_tiktok_oauth_state(state)
        bound = TikTokOAuthState.model_validate(raw_state) if raw_state else None
    except Exception as exc:
        raise AppError(ErrorCode.VALIDATION_ERROR, "OAuth state 无效或已过期", 400) from exc
    if bound is None:
        raise AppError(ErrorCode.VALIDATION_ERROR, "OAuth state 无效或已过期", 400)
    # TikTok 卖家可能在独立的店铺浏览器中授权，回调不能依赖 CRM Cookie；
    # 一次性 state 已绑定发起用户和店铺，因此只需恢复并重新校验该用户。
    user = await find_user_by_id(session, bound.user_id)
    if user is None or user.status != "active":
        raise AppError(ErrorCode.PERMISSION_DENIED, "OAuth 发起用户不可用", 403)
    await ensure_store_access(session, user, bound.store_id)
    if await get_active_store(session, bound.store_id) is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "资源不存在", 404)
    if provider_error or not auth_code or auth_code == "null":
        await _record_failed_oauth(session, user, bound.store_id, "AUTH_DENIED")
        return TikTokOAuthCompletion(status="denied", return_to=bound.return_to)

    oauth_client = client or TikTokOAuthClient(runtime)
    try:
        token = await oauth_client.exchange_code(auth_code)
        _validate_token_contract(token, runtime)
        shops, platform_request_id = await oauth_client.get_authorized_shops(token.access_token)
        if len(shops) != 1:
            raise AppError(ErrorCode.RESOURCE_CONFLICT, "当前授权必须唯一对应一个 TikTok 店铺", 409)
        shop = shops[0]
        external_binding = await find_channel_by_external_store(session, "tiktok", shop.id)
        if external_binding is not None and external_binding.store_id != bound.store_id:
            raise AppError(ErrorCode.RESOURCE_CONFLICT, "TikTok 店铺已绑定其他租户", 409)
        channel = await find_channel_by_store_platform(session, bound.store_id, "tiktok")
        if channel is not None and channel.external_store_id != shop.id:
            raise AppError(ErrorCode.RESOURCE_CONFLICT, "当前店铺已绑定其他 TikTok 账号", 409)
        if channel is None:
            channel = ChannelAccount(
                store_id=bound.store_id,
                platform="tiktok",
                external_store_id=shop.id,
                display_name=shop.name,
                access_token_ref="pending",
            )
            session.add(channel)
        key = _credential_key(runtime)
        channel.display_name = shop.name
        channel.access_token_ref = encrypt_credential(
            token.access_token,
            key,
            _oauth_context(bound.store_id, shop.id, "access"),
        )
        channel.refresh_token_ref = encrypt_credential(
            token.refresh_token,
            key,
            _oauth_context(bound.store_id, shop.id, "refresh"),
        )
        if len(channel.access_token_ref) > 500 or len(channel.refresh_token_ref) > 500:
            raise AppError(ErrorCode.THIRD_PARTY_ERROR, "TikTok 加密凭证超出存储上限", 502)
        channel.token_expires_at = _expiration(token.access_token_expire_in)
        channel.status = "connected"
        channel.scopes = sorted(set(token.granted_scopes))
        channel.last_sync_at = datetime.now(UTC)
        channel.metadata_json = {
            "shop_cipher": shop.cipher,
            "shop_code": shop.code,
            "region": shop.region,
            "seller_type": shop.seller_type,
            "seller_base_region": token.seller_base_region,
            "user_type": token.user_type,
            "open_id_hash": hashlib.sha256(token.open_id.encode()).hexdigest(),
            "refresh_token_expires_at": _expiration(token.refresh_token_expire_in).isoformat(),
            "credential_format": "encrypted:v1",
        }
        await session.flush()
        session.add(
            AuditLog(
                store_id=bound.store_id,
                actor_type="user",
                actor_id=user.id,
                action="channel.authorize",
                resource_type="channel_account",
                resource_id=channel.id,
                request_id=platform_request_id[:100] if platform_request_id else None,
                after_data={"platform": "tiktok", "external_store_id": shop.id, "scopes": channel.scopes},
                result="succeeded",
            )
        )
        await session.commit()
        return TikTokOAuthCompletion(status="connected", return_to=bound.return_to)
    except IntegrityError as exc:
        await session.rollback()
        await _record_failed_oauth(session, user, bound.store_id, ErrorCode.RESOURCE_CONFLICT.value)
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "TikTok 店铺授权已存在", 409) from exc
    except AppError as exc:
        await session.rollback()
        await _record_failed_oauth(session, user, bound.store_id, exc.code.value)
        raise


async def refresh_tiktok_channel_token(
    session: AsyncSession,
    channel: ChannelAccount,
    settings: Settings | None = None,
    client: TikTokOAuthClient | None = None,
) -> None:
    """刷新已加密的 TikTok Token；失败时标记过期供后续重新授权。"""
    runtime = settings or get_settings()
    if channel.platform != "tiktok" or channel.refresh_token_ref is None:
        raise AppError(ErrorCode.VALIDATION_ERROR, "渠道不支持 TikTok Token 刷新", 400)
    key = _credential_key(runtime)
    oauth_client = client or TikTokOAuthClient(runtime)
    platform_request_id: str | None = None
    try:
        refresh_token = decrypt_credential(
            channel.refresh_token_ref,
            key,
            _oauth_context(channel.store_id, channel.external_store_id, "refresh"),
        )
        token = await oauth_client.refresh_token(refresh_token)
        _validate_token_contract(token, runtime)
        expected_open_id_hash = channel.metadata_json.get("open_id_hash")
        actual_open_id_hash = hashlib.sha256(token.open_id.encode()).hexdigest()
        if not isinstance(expected_open_id_hash, str) or not secrets.compare_digest(
            expected_open_id_hash,
            actual_open_id_hash,
        ):
            raise AppError(ErrorCode.PERMISSION_DENIED, "TikTok 授权主体已变化，请重新授权", 403)
        shops, platform_request_id = await oauth_client.get_authorized_shops(token.access_token)
        if len(shops) != 1 or shops[0].id != channel.external_store_id:
            raise AppError(ErrorCode.RESOURCE_CONFLICT, "TikTok 授权店铺已变化，请重新授权", 409)
        shop = shops[0]
    except (AppError, ValueError, UnicodeError) as exc:
        channel.status = "expired"
        channel.metadata_json = {**channel.metadata_json, "oauth_status": "reauthorization_required"}
        session.add(
            AuditLog(
                store_id=channel.store_id,
                actor_type="job",
                action="channel.token_refresh",
                resource_type="channel_account",
                resource_id=channel.id,
                result="failed",
                after_data={"platform": "tiktok", "error_code": "TOKEN_REFRESH_FAILED"},
            )
        )
        await session.commit()
        raise AppError(ErrorCode.THIRD_PARTY_ERROR, "TikTok 授权已过期，请重新授权", 502) from exc
    channel.access_token_ref = encrypt_credential(
        token.access_token,
        key,
        _oauth_context(channel.store_id, channel.external_store_id, "access"),
    )
    channel.refresh_token_ref = encrypt_credential(
        token.refresh_token,
        key,
        _oauth_context(channel.store_id, channel.external_store_id, "refresh"),
    )
    channel.token_expires_at = _expiration(token.access_token_expire_in)
    channel.scopes = sorted(set(token.granted_scopes))
    channel.display_name = shop.name
    channel.status = "connected"
    channel.last_sync_at = datetime.now(UTC)
    channel.metadata_json = {
        **channel.metadata_json,
        "shop_cipher": shop.cipher,
        "shop_code": shop.code,
        "region": shop.region,
        "seller_type": shop.seller_type,
        "seller_base_region": token.seller_base_region,
        "user_type": token.user_type,
        "open_id_hash": actual_open_id_hash,
        "refresh_token_expires_at": _expiration(token.refresh_token_expire_in).isoformat(),
        "oauth_status": "refreshed",
    }
    session.add(
        AuditLog(
            store_id=channel.store_id,
            actor_type="job",
            action="channel.token_refresh",
            resource_type="channel_account",
            resource_id=channel.id,
            request_id=platform_request_id[:100] if platform_request_id else None,
            result="succeeded",
            after_data={"platform": "tiktok", "scopes": channel.scopes},
        )
    )
    await session.commit()


async def process_tiktok_token_refresh_cycle(
    session: AsyncSession,
    settings: Settings | None = None,
) -> int:
    """批量刷新即将过期的 TikTok 渠道，并以数据库行锁避免并发重复请求。

    未配置 OAuth 的开发/测试环境直接跳过。单个渠道失败会由刷新服务写入
    `expired` 状态和审计，不能阻断同一轮其他店铺的凭证维护。
    """
    runtime = settings or get_settings()
    try:
        validate_oauth_runtime(runtime)
    except AppError:
        return 0

    refresh_before = datetime.now(UTC) + timedelta(seconds=runtime.tiktok_token_refresh_lead_seconds)
    processed = 0
    for _ in range(runtime.tiktok_token_refresh_batch_size):
        channel = await claim_tiktok_channel_for_refresh(session, refresh_before)
        if channel is None:
            break
        try:
            await refresh_tiktok_channel_token(session, channel, runtime)
        except AppError:
            # 失败状态和低敏审计已由刷新服务提交，继续处理其他店铺。
            pass
        processed += 1
    return processed
