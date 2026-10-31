"""TikTok OAuth 一次性状态、店铺绑定和凭证生命周期。"""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.models import AuditLog
from app.auth.repository import find_user_by_id
from app.auth.store_access import allowed_store_ids_for_permission, ensure_store_access
from app.integrations.credential_crypto import decrypt_credential, encrypt_credential
from app.integrations.models import TikTokOAuthJob
from app.integrations.oauth_schemas import (
    MAX_TIKTOK_AUTHORIZED_SHOPS,
    TikTokAuthorizedShop,
    TikTokOAuthCompletion,
    TikTokOAuthJobStatus,
    TikTokOAuthStart,
    TikTokOAuthState,
    TikTokTokenData,
)
from app.integrations.tiktok_oauth import TikTokOAuthClient, build_authorization_url
from app.shared.config.settings import Settings, get_settings
from app.shared.database.base import Permission, Role, User, user_roles
from app.shared.database.redis import consume_tiktok_oauth_state, peek_tiktok_oauth_state, save_tiktok_oauth_state
from app.shared.exceptions.errors import AppError, ErrorCode
from app.stores.models import ChannelAccount, Store, TikTokSellerAuthorization
from app.stores.repository import (
    claim_tiktok_channel_for_refresh,
    claim_tiktok_seller_for_refresh,
    find_channel_by_external_store,
    find_channel_by_store_platform,
    get_active_store,
)
from app.users.models import department_members, department_stores

SELLER_USER_TYPES = {0, 4, 5}
DEFAULT_RETURN_TO = "/settings/channels"
STORES_RETURN_TO = "/settings/stores"
OAUTH_JOB_RETENTION_SECONDS = 86400
SHOP_SELECTION_SECONDS = 600
SHOP_CURRENCIES = {
    "US": "USD",
    "GB": "GBP",
    "UK": "GBP",
    "CA": "CAD",
    "MX": "MXN",
    "BR": "BRL",
    "DE": "EUR",
    "FR": "EUR",
    "IT": "EUR",
    "ES": "EUR",
    "IE": "EUR",
    "JP": "JPY",
    "AU": "AUD",
    "SG": "SGD",
    "MY": "MYR",
    "TH": "THB",
    "VN": "VND",
    "ID": "IDR",
    "PH": "PHP",
}


def validate_return_to(value: str) -> str:
    """只允许两个固定设置页，禁止利用 return_to 开放重定向。"""
    if value not in {DEFAULT_RETURN_TO, STORES_RETURN_TO}:
        raise AppError(ErrorCode.VALIDATION_ERROR, "OAuth 回跳地址无效", 400)
    return value


async def ensure_system_store_admin(session: AsyncSession, user: User) -> None:
    """新店铺只能由系统级管理员发起，店铺级角色不能扩大租户范围。"""
    assignment = await session.scalar(
        select(user_roles.c.user_id)
        .join(Role, user_roles.c.role_id == Role.id)
        .where(user_roles.c.user_id == user.id, user_roles.c.store_id.is_(None), Role.code == "admin")
    )
    if assignment is None:
        raise AppError(ErrorCode.PERMISSION_DENIED, "没有添加店铺的权限", 403)


async def ensure_new_store_authorizer(session: AsyncSession, user: User) -> uuid.UUID | None:
    """系统管理员可全局建店；主管须属于唯一负责部门且在该部门有店铺角色。"""
    try:
        await ensure_system_store_admin(session, user)
        return None
    except AppError as exc:
        if exc.code != ErrorCode.PERMISSION_DENIED:
            raise
    departments: set[uuid.UUID] = set(
        (
            await session.scalars(
                select(department_members.c.department_id)
                .join(department_stores, department_stores.c.department_id == department_members.c.department_id)
                .join(user_roles, user_roles.c.store_id == department_stores.c.store_id)
                .join(Store, Store.id == department_stores.c.store_id)
                .join(Role, Role.id == user_roles.c.role_id)
                .where(
                    department_members.c.user_id == user.id,
                    user_roles.c.user_id == user.id,
                    Role.code == "supervisor",
                    Role.permissions.any(Permission.code == "settings.store_authorize"),
                    Store.status == "active",
                    Store.deleted_at.is_(None),
                )
                .distinct()
            )
        ).all()
    )
    if len(departments) != 1:
        raise AppError(ErrorCode.PERMISSION_DENIED, "没有添加店铺的权限", 403)
    return departments.pop()


async def ensure_store_channel_manager(session: AsyncSession, user: User, store_id: uuid.UUID) -> None:
    """渠道管理权限须来自系统级或目标店铺角色，不能借用其他店铺授权。"""
    assignment = await session.scalar(
        select(user_roles.c.user_id)
        .join(Role, user_roles.c.role_id == Role.id)
        .where(
            user_roles.c.user_id == user.id,
            or_(user_roles.c.store_id.is_(None), user_roles.c.store_id == store_id),
            or_(Role.code == "admin", Role.permissions.any(Permission.code == "settings.channels")),
        )
    )
    if assignment is None and store_id not in await allowed_store_ids_for_permission(
        session, user, "settings.store_authorize"
    ):
        raise AppError(ErrorCode.PERMISSION_DENIED, "没有管理该店铺渠道的权限", 403)


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
        if channel.seller_authorization_id is not None:
            authorization = channel.seller_authorization
            if (
                authorization is None
                or authorization.id != channel.seller_authorization_id
                or authorization.app_key != settings.tiktok_app_key
                or authorization.status != "connected"
                or channel.external_store_id not in authorization.authorized_shop_ids
                or channel.metadata_json.get("open_id_hash") != authorization.open_id_hash
                or authorization.access_expires_at <= datetime.now(UTC)
            ):
                raise AppError(ErrorCode.TOKEN_INVALID, "TikTok 授权凭证无效，请重新授权", 401)
            return decrypt_credential(
                authorization.access_token_ref,
                _credential_key(settings),
                f"tiktok:seller:{authorization.id}:access",
            )
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


def _next_seller_refresh_at(expires_at: datetime, settings: Settings) -> datetime:
    """长效 Token 按提前量刷新；短效 Token 至少用到半程，避免 Worker 热循环。"""
    now = datetime.now(UTC)
    return max(
        expires_at - timedelta(seconds=settings.tiktok_token_refresh_lead_seconds),
        now + (expires_at - now) / 2,
    )


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
    await ensure_store_channel_manager(session, user, store_id)
    if await get_active_store(session, store_id) is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "资源不存在", 404)
    safe_return_to = validate_return_to(return_to)
    return await _create_oauth_start(user.id, store_id, safe_return_to, runtime)


async def start_new_tiktok_store_oauth(
    session: AsyncSession,
    user: User,
    settings: Settings | None = None,
) -> TikTokOAuthStart:
    """点击添加店铺时先取得一次性授权链接，成功回调后再创建内部店铺。"""
    runtime = settings or get_settings()
    validate_oauth_runtime(runtime)
    await ensure_new_store_authorizer(session, user)
    return await _create_oauth_start(user.id, None, STORES_RETURN_TO, runtime)


async def _create_oauth_start(
    user_id: uuid.UUID, store_id: uuid.UUID | None, return_to: str, runtime: Settings
) -> TikTokOAuthStart:
    state = secrets.token_urlsafe(32)
    payload = TikTokOAuthState(user_id=user_id, store_id=store_id, return_to=return_to)
    try:
        stored = await save_tiktok_oauth_state(
            state,
            {key: str(value) for key, value in payload.model_dump(exclude_none=True).items()},
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
    store_id: uuid.UUID | None,
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


async def queue_tiktok_oauth(
    session: AsyncSession,
    state: str,
    auth_code: str,
    settings: Settings | None = None,
) -> TikTokOAuthJob:
    """先入加密、去重短期任务并快速返回；不在 callback 中访问 TikTok。"""
    runtime = settings or get_settings()
    validate_oauth_runtime(runtime)
    job_id = uuid.UUID(bytes=hashlib.sha256(state.encode()).digest()[:16])
    existing = await session.get(TikTokOAuthJob, job_id)
    if existing is not None:
        return existing
    try:
        raw_state = await peek_tiktok_oauth_state(state)
        bound = TikTokOAuthState.model_validate(raw_state) if raw_state else None
    except Exception as exc:
        raise AppError(ErrorCode.VALIDATION_ERROR, "OAuth state 无效或已过期", 400) from exc
    if bound is None:
        # 首次查询可能早于另一个 callback 的提交，而 Redis state 随后已被 worker 消费。
        existing = await session.get(TikTokOAuthJob, job_id)
        if existing is not None:
            return existing
        raise AppError(ErrorCode.VALIDATION_ERROR, "OAuth state 无效或已过期", 400)
    validate_return_to(bound.return_to)
    user = await find_user_by_id(session, bound.user_id)
    if user is None or user.status != "active":
        raise AppError(ErrorCode.PERMISSION_DENIED, "OAuth 发起用户不可用", 403)
    if bound.store_id is None:
        await ensure_new_store_authorizer(session, user)
    else:
        await ensure_store_access(session, user, bound.store_id)
        await ensure_store_channel_manager(session, user, bound.store_id)
        if await get_active_store(session, bound.store_id) is None:
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "资源不存在", 404)
    key = _credential_key(runtime)
    state_cipher = encrypt_credential(state, key, f"tiktok:oauth-job:{job_id}:state")
    code_cipher = encrypt_credential(auth_code, key, f"tiktok:oauth-job:{job_id}:code")
    if len(state_cipher) > 1200 or len(code_cipher) > 1200:
        raise AppError(ErrorCode.VALIDATION_ERROR, "OAuth 授权参数过长", 400)
    job = TikTokOAuthJob(
        id=job_id,
        user_id=bound.user_id,
        store_id=bound.store_id,
        return_to=bound.return_to,
        state_cipher=state_cipher,
        code_cipher=code_cipher,
        status="pending",
    )
    session.add(job)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        existing = await session.get(TikTokOAuthJob, job_id)
        if existing is None:
            raise
        return existing
    return job


async def get_tiktok_oauth_job_status(session: AsyncSession, user: User, job_id: uuid.UUID) -> TikTokOAuthJobStatus:
    """仅原发起用户且仍有店铺访问权可查看低敏进度。"""
    job = await session.get(TikTokOAuthJob, job_id)
    if job is None or job.user_id != user.id:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "资源不存在", 404)
    if job.store_id is None:
        await ensure_new_store_authorizer(session, user)
    else:
        await ensure_store_access(session, user, job.store_id)
        await ensure_store_channel_manager(session, user, job.store_id)
    if job.status == "selection_required":
        if job.selection_expires_at is None or job.selection_expires_at <= datetime.now(UTC):
            return TikTokOAuthJobStatus(status="failed", error_code="SELECTION_EXPIRED")
        return TikTokOAuthJobStatus.model_validate(
            {
                "status": "selection_required",
                "shops": job.selection_shops or [],
                "selection_expires_at": job.selection_expires_at.isoformat(),
            }
        )
    return TikTokOAuthJobStatus.model_validate(
        {
            "status": job.status,
            "error_code": job.error_code if job.status == "failed" else None,
            "store_id": job.store_id,
        }
    )


async def complete_tiktok_oauth(
    session: AsyncSession,
    state: str,
    auth_code: str | None,
    provider_error: str | None,
    settings: Settings | None = None,
    client: TikTokOAuthClient | None = None,
    *,
    commit: bool = True,
    job: TikTokOAuthJob | None = None,
) -> TikTokOAuthCompletion:
    """原子消费 state；worker 可将渠道、审计和任务终态合并提交。"""
    runtime = settings or get_settings()
    validate_oauth_runtime(runtime)
    try:
        raw_state = await consume_tiktok_oauth_state(state)
        bound = TikTokOAuthState.model_validate(raw_state) if raw_state else None
    except Exception as exc:
        raise AppError(ErrorCode.VALIDATION_ERROR, "OAuth state 无效或已过期", 400) from exc
    if bound is None:
        raise AppError(ErrorCode.VALIDATION_ERROR, "OAuth state 无效或已过期", 400)
    validate_return_to(bound.return_to)
    # TikTok 卖家可能在独立的店铺浏览器中授权，回调不能依赖 CRM Cookie；
    # 一次性 state 已绑定发起用户和店铺，因此只需恢复并重新校验该用户。
    user = await find_user_by_id(session, bound.user_id)
    if user is None or user.status != "active":
        raise AppError(ErrorCode.PERMISSION_DENIED, "OAuth 发起用户不可用", 403)
    if bound.store_id is None:
        department_id = await ensure_new_store_authorizer(session, user)
    else:
        department_id = None
        await ensure_store_access(session, user, bound.store_id)
        await ensure_store_channel_manager(session, user, bound.store_id)
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
        if not shops:
            raise AppError(ErrorCode.RESOURCE_CONFLICT, "TikTok 卖家授权没有可用店铺", 409)
        if len(shops) > 1 and bound.store_id is None:
            if job is None:
                raise AppError(ErrorCode.RESOURCE_CONFLICT, "多店铺授权需要选择店铺", 409)
            job.selection_token_cipher = encrypt_credential(
                token.model_dump_json(), _credential_key(runtime), f"tiktok:oauth-job:{job.id}:selection"
            )
            job.selection_shops = [shop.model_dump() for shop in shops]
            job.selection_expires_at = datetime.now(UTC) + timedelta(seconds=SHOP_SELECTION_SECONDS)
            if commit:
                await session.commit()
            return TikTokOAuthCompletion(status="selection_required", return_to=bound.return_to)
        if bound.store_id is not None and len(shops) > 1:
            bound_channel = await find_channel_by_store_platform(session, bound.store_id, "tiktok")
            shop = next(
                (item for item in shops if bound_channel is not None and item.id == bound_channel.external_store_id),
                None,
            )
            if shop is None:
                raise AppError(ErrorCode.RESOURCE_CONFLICT, "授权店铺不包含当前目标店铺", 409)
        else:
            shop = shops[0]
        external_binding = await find_channel_by_external_store(session, "tiktok", shop.id)
        store_id = bound.store_id
        if store_id is None:
            if external_binding is not None:
                # 删除授权仅撤销凭证；再次添加同一店铺复用原系统 ID 与历史数据。
                if external_binding.status != "disconnected":
                    raise AppError(ErrorCode.RESOURCE_CONFLICT, "店铺已添加，请使用重新添加", 409)
                store_id = external_binding.store_id
                await ensure_store_access(session, user, store_id)
                await ensure_store_channel_manager(session, user, store_id)
                if await get_active_store(session, store_id) is None:
                    raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "资源不存在", 404)
            else:
                currency = SHOP_CURRENCIES.get(shop.region.upper())
                if currency is None:
                    raise AppError(ErrorCode.VALIDATION_ERROR, "暂不支持该站点自动建店", 422)
                store_id = uuid.uuid4()
                session.add(
                    Store(
                        id=store_id,
                        name=shop.name,
                        code=f"tiktok-{store_id.hex}",
                        timezone="UTC",
                        currency=currency,
                        status="active",
                    )
                )
                await session.flush()
                if department_id is not None:
                    await session.execute(
                        department_stores.insert().values(department_id=department_id, store_id=store_id)
                    )
        elif external_binding is not None and external_binding.store_id != store_id:
            raise AppError(ErrorCode.RESOURCE_CONFLICT, "TikTok 店铺已绑定其他租户", 409)
        channel = await find_channel_by_store_platform(session, store_id, "tiktok")
        if channel is not None and channel.external_store_id != shop.id:
            raise AppError(ErrorCode.RESOURCE_CONFLICT, "当前店铺已绑定其他 TikTok 账号", 409)
        if channel is None:
            channel = ChannelAccount(
                store_id=store_id,
                platform="tiktok",
                external_store_id=shop.id,
                display_name=shop.name,
                access_token_ref="pending",
            )
            session.add(channel)
        if channel.seller_authorization_id is not None or len(shops) > 1:
            return await _reauthorize_shared_seller(
                session,
                channel,
                token,
                shops,
                user,
                platform_request_id,
                bound.return_to,
                runtime,
                commit=commit,
            )
        key = _credential_key(runtime)
        channel.display_name = shop.name
        channel.access_token_ref = encrypt_credential(
            token.access_token,
            key,
            _oauth_context(store_id, shop.id, "access"),
        )
        channel.refresh_token_ref = encrypt_credential(
            token.refresh_token,
            key,
            _oauth_context(store_id, shop.id, "refresh"),
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
            "last_authorized_at": datetime.now(UTC).isoformat(),
            "credential_format": "encrypted:v1",
        }
        await session.flush()
        session.add(
            AuditLog(
                store_id=store_id,
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
        if commit:
            await session.commit()
        return TikTokOAuthCompletion(status="connected", return_to=bound.return_to, store_id=store_id)
    except IntegrityError as exc:
        if commit:
            await session.rollback()
            await _record_failed_oauth(session, user, bound.store_id, ErrorCode.RESOURCE_CONFLICT.value)
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "TikTok 店铺授权已存在", 409) from exc
    except AppError as exc:
        if commit:
            await session.rollback()
            await _record_failed_oauth(session, user, bound.store_id, exc.code.value)
        raise


async def _reauthorize_shared_seller(
    session: AsyncSession,
    target: ChannelAccount,
    token: TikTokTokenData,
    shops: list[TikTokAuthorizedShop],
    user: User,
    request_id: str | None,
    return_to: str,
    settings: Settings,
    *,
    commit: bool,
) -> TikTokOAuthCompletion:
    """目标店重新授权时更新整组卖家凭证，绝不降级为店铺级旧密文。"""
    grant_id = target.seller_authorization_id
    actual_hash = hashlib.sha256(token.open_id.encode()).hexdigest()
    if target.status == "connected" and target.metadata_json.get("open_id_hash") not in {None, actual_hash}:
        raise AppError(ErrorCode.PERMISSION_DENIED, "TikTok 授权主体已变化，请重新授权", 403)
    if grant_id is not None:
        grant = await session.get(TikTokSellerAuthorization, grant_id, with_for_update=True)
    else:
        grant = await session.scalar(
            select(TikTokSellerAuthorization)
            .where(
                TikTokSellerAuthorization.app_key == settings.tiktok_app_key,
                TikTokSellerAuthorization.open_id_hash == actual_hash,
            )
            .with_for_update()
        )
    if grant_id is not None and (grant is None or grant.id != grant_id):
        raise AppError(ErrorCode.TOKEN_INVALID, "TikTok 卖家授权缺失", 401)
    if grant is not None and (
        grant.app_key != settings.tiktok_app_key or not secrets.compare_digest(grant.open_id_hash, actual_hash)
    ):
        raise AppError(ErrorCode.PERMISSION_DENIED, "TikTok 授权主体已变化，请重新授权", 403)
    new_grant = grant is None
    if grant is None:
        grant = TikTokSellerAuthorization(id=uuid.uuid4(), app_key=settings.tiktok_app_key, open_id_hash=actual_hash)
    live_shops = {shop.id: shop for shop in shops}
    if len(live_shops) != len(shops) or target.external_store_id not in live_shops:
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "授权店铺不包含当前目标店铺", 409)
    shared = list(
        (
            await session.scalars(
                select(ChannelAccount).where(ChannelAccount.seller_authorization_id == grant.id).with_for_update()
            )
        ).all()
    )
    legacy = list(
        (
            await session.scalars(
                select(ChannelAccount)
                .where(
                    ChannelAccount.platform == "tiktok",
                    ChannelAccount.seller_authorization_id.is_(None),
                    ChannelAccount.status == "connected",
                    ChannelAccount.metadata_json["open_id_hash"].astext == actual_hash,
                )
                .with_for_update()
            )
        ).all()
    )
    channels = {channel.id: channel for channel in [*shared, *legacy, target]}
    # 共享凭证轮换会影响同一卖家的所有在线店铺，发起者必须有每家店的渠道管理权。
    for store_id in {channel.store_id for channel in channels.values() if channel.status == "connected"}:
        await ensure_store_access(session, user, store_id)
        await ensure_store_channel_manager(session, user, store_id)
    key = _credential_key(settings)
    access_cipher = encrypt_credential(token.access_token, key, f"tiktok:seller:{grant.id}:access")
    refresh_cipher = encrypt_credential(token.refresh_token, key, f"tiktok:seller:{grant.id}:refresh")
    if len(access_cipher) > 1200 or len(refresh_cipher) > 1200:
        raise AppError(ErrorCode.THIRD_PARTY_ERROR, "TikTok 加密凭证超出存储上限", 502)
    access_expires = _expiration(token.access_token_expire_in)
    refresh_expires = _expiration(token.refresh_token_expire_in)
    grant.access_token_ref = access_cipher
    grant.refresh_token_ref = refresh_cipher
    grant.access_expires_at = access_expires
    grant.refresh_expires_at = refresh_expires
    grant.next_refresh_at = _next_seller_refresh_at(access_expires, settings)
    grant.scopes = sorted(set(token.granted_scopes))
    grant.authorized_shop_ids = list(live_shops)
    grant.status = "connected"
    if new_grant:
        session.add(grant)
    for channel in channels.values():
        if channel.status != "connected" and channel.id != target.id:
            continue
        matched_shop = live_shops.get(channel.external_store_id)
        if matched_shop is None:
            channel.status = "expired"
            channel.metadata_json = {**channel.metadata_json, "oauth_status": "reauthorization_required"}
        else:
            if channel.seller_authorization_id is None and channel.status == "connected":
                _audit_shared_migration(session, user, channel)
            _connect_shared_channel(channel, grant, matched_shop, token, access_expires, refresh_expires)
    await session.flush()
    session.add(
        AuditLog(
            store_id=target.store_id,
            actor_type="user",
            actor_id=user.id,
            action="channel.authorize",
            resource_type="channel_account",
            resource_id=target.id,
            request_id=request_id[:100] if request_id else None,
            after_data={"platform": "tiktok", "external_store_id": target.external_store_id, "scopes": grant.scopes},
            result="succeeded",
        )
    )
    if commit:
        await session.commit()
    return TikTokOAuthCompletion(status="connected", return_to=return_to, store_id=target.store_id)


async def _finish_tiktok_oauth_job(
    session: AsyncSession, job_id: uuid.UUID, status: str, error_code: str | None = None
) -> None:
    """终态即抹除一次性材料；对外只保留低敏状态。"""
    job = await session.get(TikTokOAuthJob, job_id)
    if job is None:
        return
    job.status = status
    job.error_code = error_code
    job.state_cipher = None
    job.code_cipher = None
    job.completed_at = datetime.now(UTC)
    if status == "failed" and error_code is not None:
        session.add(
            AuditLog(
                store_id=job.store_id,
                actor_type="user",
                actor_id=job.user_id,
                action="channel.oauth",
                resource_type="channel_account",
                result="failed",
                after_data={"platform": "tiktok", "error_code": error_code},
            )
        )
    await session.commit()


async def process_tiktok_oauth_job(
    session: AsyncSession,
    settings: Settings | None = None,
    client: TikTokOAuthClient | None = None,
) -> bool:
    """行锁贯穿平台调用和终态提交，崩溃时回滚并禁止并行重复兑换。"""
    runtime = settings or get_settings()
    now = datetime.now(UTC)
    job = await session.scalar(
        select(TikTokOAuthJob)
        .where(TikTokOAuthJob.status == "pending")
        .order_by(TikTokOAuthJob.created_at)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if job is None:
        return False
    if job.created_at < now - timedelta(seconds=runtime.tiktok_oauth_state_ttl_seconds):
        await _finish_tiktok_oauth_job(session, job.id, "failed", "STATE_EXPIRED")
        return True
    job.status = "processing"
    job.started_at = now
    try:
        key = _credential_key(runtime)
        if job.state_cipher is None or job.code_cipher is None:
            raise ValueError("一次性材料缺失")
        state = decrypt_credential(job.state_cipher, key, f"tiktok:oauth-job:{job.id}:state")
        code = decrypt_credential(job.code_cipher, key, f"tiktok:oauth-job:{job.id}:code")
        # 保存点回滚部分渠道写入，外层事务持续持有任务行锁直到失败或成功终态提交。
        async with session.begin_nested():
            completion = await complete_tiktok_oauth(session, state, code, None, runtime, client, commit=False, job=job)
    except AppError as exc:
        await _finish_tiktok_oauth_job(session, job.id, "failed", exc.code.value)
    except (ValueError, UnicodeError):
        await _finish_tiktok_oauth_job(session, job.id, "failed", "INVALID_JOB_CREDENTIAL")
    else:
        completed_store_id = getattr(completion, "store_id", None)
        if completion.status == "connected" and completed_store_id is not None:
            job.store_id = completed_store_id
        await _finish_tiktok_oauth_job(session, job.id, completion.status)
    return True


async def cleanup_tiktok_oauth_jobs(session: AsyncSession) -> None:
    """清除一天前的终态收据，避免授权元数据无限留存。"""
    await session.execute(
        update(TikTokOAuthJob)
        .where(
            TikTokOAuthJob.status == "selection_required",
            TikTokOAuthJob.selection_expires_at < datetime.now(UTC),
        )
        .values(
            status="failed",
            error_code="SELECTION_EXPIRED",
            selection_token_cipher=None,
            selection_shops=None,
            selection_expires_at=None,
            completed_at=datetime.now(UTC),
        )
    )
    cutoff = datetime.now(UTC) - timedelta(seconds=OAUTH_JOB_RETENTION_SECONDS)
    await session.execute(
        delete(TikTokOAuthJob).where(
            TikTokOAuthJob.status.in_(("connected", "denied", "failed")),
            TikTokOAuthJob.completed_at < cutoff,
        )
    )
    await session.commit()


async def select_tiktok_oauth_shops(
    session: AsyncSession,
    user: User,
    job_id: uuid.UUID,
    selected_shop_ids: list[str],
    settings: Settings | None = None,
    client: TikTokOAuthClient | None = None,
) -> TikTokOAuthCompletion:
    """由原发起人确认多店绑定；再次核验平台清单并原子提交。"""
    runtime = settings or get_settings()
    validate_oauth_runtime(runtime)
    if (
        not selected_shop_ids
        or len(selected_shop_ids) > MAX_TIKTOK_AUTHORIZED_SHOPS
        or len(set(selected_shop_ids)) != len(selected_shop_ids)
    ):
        raise AppError(ErrorCode.VALIDATION_ERROR, "请选择有效的 TikTok 店铺", 400)
    department_id = await ensure_new_store_authorizer(session, user)
    job = await session.get(TikTokOAuthJob, job_id, with_for_update=True)
    if job is None or job.user_id != user.id:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "资源不存在", 404)
    if job.status != "selection_required" or job.store_id is not None:
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "授权任务不可重复选择", 409)
    if job.selection_expires_at is None or job.selection_expires_at <= datetime.now(UTC):
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "店铺选择已过期，请重新授权", 409)
    if job.selection_token_cipher is None or job.selection_shops is None:
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "授权任务缺少店铺选择材料", 409)

    candidate_ids = {item.get("id") for item in job.selection_shops}
    if not set(selected_shop_ids).issubset(candidate_ids):
        raise AppError(ErrorCode.VALIDATION_ERROR, "所选店铺不在本次授权范围内", 400)
    try:
        token_json = decrypt_credential(
            job.selection_token_cipher,
            _credential_key(runtime),
            f"tiktok:oauth-job:{job.id}:selection",
        )
        token = TikTokTokenData.model_validate_json(token_json)
    except (ValueError, UnicodeError) as exc:
        raise AppError(ErrorCode.TOKEN_INVALID, "授权任务凭证无效，请重新授权", 401) from exc
    _validate_token_contract(token, runtime)
    shops, platform_request_id = await (client or TikTokOAuthClient(runtime)).get_authorized_shops(token.access_token)
    live_shops = {shop.id: shop for shop in shops}
    if len(live_shops) != len(shops) or not set(selected_shop_ids).issubset(live_shops):
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "TikTok 店铺授权范围已变化，请重新授权", 409)
    open_id_hash = hashlib.sha256(token.open_id.encode()).hexdigest()
    grant = await session.scalar(
        select(TikTokSellerAuthorization)
        .where(
            TikTokSellerAuthorization.app_key == runtime.tiktok_app_key,
            TikTokSellerAuthorization.open_id_hash == open_id_hash,
        )
        .with_for_update()
    )
    grant_id = grant.id if grant is not None else uuid.uuid4()

    # 所有目标先检查完毕再写入，任何冲突都不覆盖已有卖家 Token 或租户绑定。
    bindings: list[tuple[TikTokAuthorizedShop, ChannelAccount | None, uuid.UUID]] = []
    for shop_id in selected_shop_ids:
        shop = live_shops[shop_id]
        if SHOP_CURRENCIES.get(shop.region.upper()) is None:
            raise AppError(ErrorCode.VALIDATION_ERROR, "暂不支持该站点自动建店", 422)
        binding = await find_channel_by_external_store(session, "tiktok", shop_id, for_update=True)
        if binding is not None:
            if binding.status == "connected" and (
                binding.metadata_json.get("open_id_hash") != open_id_hash
                or binding.seller_authorization_id not in {None, grant_id}
            ):
                raise AppError(ErrorCode.RESOURCE_CONFLICT, "TikTok 店铺已绑定其他卖家授权", 409)
            store_id = binding.store_id
            await ensure_store_access(session, user, store_id)
            await ensure_store_channel_manager(session, user, store_id)
            if await get_active_store(session, store_id) is None:
                raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "资源不存在", 404)
        else:
            store_id = uuid.uuid4()
        bindings.append((shop, binding, store_id))

    existing_shared = (
        list(
            (
                await session.scalars(
                    select(ChannelAccount).where(ChannelAccount.seller_authorization_id == grant_id).with_for_update()
                )
            ).all()
        )
        if grant is not None
        else []
    )
    legacy = list(
        (
            await session.scalars(
                select(ChannelAccount)
                .where(
                    ChannelAccount.platform == "tiktok",
                    ChannelAccount.seller_authorization_id.is_(None),
                    ChannelAccount.status == "connected",
                    ChannelAccount.metadata_json["open_id_hash"].astext == open_id_hash,
                )
                .with_for_update()
            )
        ).all()
    )

    # 新店授权可能复用已有卖家凭证；先检查全部受影响店铺，再轮换共享 Token。
    for channel in [*existing_shared, *legacy]:
        if channel.status == "connected":
            await ensure_store_access(session, user, channel.store_id)
            await ensure_store_channel_manager(session, user, channel.store_id)

    key = _credential_key(runtime)
    access_cipher = encrypt_credential(token.access_token, key, f"tiktok:seller:{grant_id}:access")
    refresh_cipher = encrypt_credential(token.refresh_token, key, f"tiktok:seller:{grant_id}:refresh")
    if len(access_cipher) > 1200 or len(refresh_cipher) > 1200:
        raise AppError(ErrorCode.THIRD_PARTY_ERROR, "TikTok 加密凭证超出存储上限", 502)
    access_expires = _expiration(token.access_token_expire_in)
    refresh_expires = _expiration(token.refresh_token_expire_in)
    if grant is None:
        grant = TikTokSellerAuthorization(id=grant_id, app_key=runtime.tiktok_app_key, open_id_hash=open_id_hash)
        session.add(grant)
    grant.access_token_ref = access_cipher
    grant.refresh_token_ref = refresh_cipher
    grant.access_expires_at = access_expires
    grant.refresh_expires_at = refresh_expires
    grant.next_refresh_at = _next_seller_refresh_at(access_expires, runtime)
    grant.scopes = sorted(set(token.granted_scopes))
    grant.authorized_shop_ids = list(live_shops)
    grant.status = "connected"

    selected_by_id = {binding.external_store_id: binding for _, binding, _ in bindings if binding is not None}
    for channel in [*existing_shared, *legacy]:
        if channel.external_store_id in selected_by_id:
            continue
        if channel.status != "connected":
            continue
        matched_shop = live_shops.get(channel.external_store_id)
        if matched_shop is None:
            channel.status = "expired"
            channel.metadata_json = {**channel.metadata_json, "oauth_status": "reauthorization_required"}
            continue
        if channel.seller_authorization_id is None:
            _audit_shared_migration(session, user, channel)
        _connect_shared_channel(channel, grant, matched_shop, token, access_expires, refresh_expires)

    for shop, selected_channel, store_id in bindings:
        if selected_channel is None:
            session.add(
                Store(
                    id=store_id,
                    name=shop.name,
                    code=f"tiktok-{store_id.hex}",
                    timezone="UTC",
                    currency=SHOP_CURRENCIES[shop.region.upper()],
                    status="active",
                )
            )
            if department_id is not None:
                await session.flush()
                await session.execute(department_stores.insert().values(department_id=department_id, store_id=store_id))
            selected_channel = ChannelAccount(
                id=uuid.uuid4(),
                store_id=store_id,
                platform="tiktok",
                external_store_id=shop.id,
                display_name=shop.name,
                access_token_ref=f"shared://{grant_id}",
            )
            session.add(selected_channel)
        _connect_shared_channel(selected_channel, grant, shop, token, access_expires, refresh_expires)
        try:
            await session.flush()
        except IntegrityError as exc:
            await session.rollback()
            raise AppError(ErrorCode.RESOURCE_CONFLICT, "TikTok 店铺授权已存在", 409) from exc
        session.add(
            AuditLog(
                store_id=store_id,
                actor_type="user",
                actor_id=user.id,
                action="channel.authorize",
                resource_type="channel_account",
                resource_id=selected_channel.id,
                request_id=platform_request_id[:100] if platform_request_id else None,
                after_data={"platform": "tiktok", "external_store_id": shop.id, "scopes": grant.scopes},
                result="succeeded",
            )
        )
    job.status = "connected"
    job.selection_token_cipher = None
    job.selection_shops = None
    job.selection_expires_at = None
    job.completed_at = datetime.now(UTC)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "TikTok 店铺授权已存在", 409) from exc
    return TikTokOAuthCompletion(status="connected", return_to=STORES_RETURN_TO)


def _connect_shared_channel(
    channel: ChannelAccount,
    grant: TikTokSellerAuthorization,
    shop: TikTokAuthorizedShop,
    token: TikTokTokenData,
    access_expires: datetime,
    refresh_expires: datetime,
) -> None:
    """将店铺绑定到共享卖家凭证，保留 CRM 店铺 ID 与业务历史。"""
    channel.seller_authorization = grant
    channel.seller_authorization_id = grant.id
    channel.access_token_ref = f"shared://{grant.id}"
    channel.refresh_token_ref = None
    channel.token_expires_at = access_expires
    channel.display_name = shop.name
    channel.scopes = grant.scopes
    channel.status = "connected"
    channel.last_sync_at = datetime.now(UTC)
    channel.metadata_json = {
        **(channel.metadata_json or {}),
        "shop_cipher": shop.cipher,
        "shop_code": shop.code,
        "region": shop.region,
        "seller_type": shop.seller_type,
        "seller_base_region": token.seller_base_region,
        "user_type": token.user_type,
        "open_id_hash": grant.open_id_hash,
        "refresh_token_expires_at": refresh_expires.isoformat(),
        "last_authorized_at": datetime.now(UTC).isoformat(),
        "oauth_status": "refreshed",
    }


def _audit_shared_migration(session: AsyncSession, user: User, channel: ChannelAccount) -> None:
    """记录旧单店凭证改为卖家共享凭证的店铺级安全审计。"""
    session.add(
        AuditLog(
            store_id=channel.store_id,
            actor_type="user",
            actor_id=user.id,
            action="channel.authorization_migrated",
            resource_type="channel_account",
            resource_id=channel.id,
            result="succeeded",
            after_data={"platform": "tiktok", "credential_scope": "seller"},
        )
    )


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
        live_shops = {shop.id: shop for shop in shops}
        if len(live_shops) != len(shops) or channel.external_store_id not in live_shops:
            raise AppError(ErrorCode.RESOURCE_CONFLICT, "TikTok 授权店铺已变化，请重新授权", 409)
        shop = live_shops[channel.external_store_id]
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


async def refresh_tiktok_seller_authorization(
    session: AsyncSession,
    grant: TikTokSellerAuthorization,
    settings: Settings | None = None,
    client: TikTokOAuthClient | None = None,
) -> None:
    """轮换卖家级凭证一次，并逐店核对当前平台授权清单。"""
    runtime = settings or get_settings()
    key = _credential_key(runtime)
    channels = list(
        (
            await session.scalars(
                select(ChannelAccount).where(ChannelAccount.seller_authorization_id == grant.id).with_for_update()
            )
        ).all()
    )
    platform_request_id: str | None = None
    try:
        if grant.app_key != runtime.tiktok_app_key or grant.status != "connected":
            raise AppError(ErrorCode.TOKEN_INVALID, "TikTok 卖家授权已失效", 401)
        refresh_token = decrypt_credential(grant.refresh_token_ref, key, f"tiktok:seller:{grant.id}:refresh")
        oauth_client = client or TikTokOAuthClient(runtime)
        token = await oauth_client.refresh_token(refresh_token)
        _validate_token_contract(token, runtime)
        actual_hash = hashlib.sha256(token.open_id.encode()).hexdigest()
        if not secrets.compare_digest(actual_hash, grant.open_id_hash):
            raise AppError(ErrorCode.PERMISSION_DENIED, "TikTok 授权主体已变化，请重新授权", 403)
        shops, platform_request_id = await oauth_client.get_authorized_shops(token.access_token)
        live_shops = {shop.id: shop for shop in shops}
        if len(live_shops) != len(shops):
            raise AppError(ErrorCode.RESOURCE_CONFLICT, "TikTok 授权店铺清单重复", 409)
        access_expires = _expiration(token.access_token_expire_in)
        refresh_expires = _expiration(token.refresh_token_expire_in)
        access_cipher = encrypt_credential(token.access_token, key, f"tiktok:seller:{grant.id}:access")
        refresh_cipher = encrypt_credential(token.refresh_token, key, f"tiktok:seller:{grant.id}:refresh")
        if len(access_cipher) > 1200 or len(refresh_cipher) > 1200:
            raise AppError(ErrorCode.THIRD_PARTY_ERROR, "TikTok 加密凭证超出存储上限", 502)
    except (AppError, ValueError, UnicodeError) as exc:
        grant.status = "expired"
        for channel in channels:
            if channel.status != "connected":
                continue
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
        raise AppError(ErrorCode.THIRD_PARTY_ERROR, "TikTok 卖家授权已过期，请重新授权", 502) from exc

    grant.access_token_ref = access_cipher
    grant.refresh_token_ref = refresh_cipher
    grant.access_expires_at = access_expires
    grant.refresh_expires_at = refresh_expires
    grant.next_refresh_at = _next_seller_refresh_at(access_expires, runtime)
    grant.scopes = sorted(set(token.granted_scopes))
    grant.authorized_shop_ids = list(live_shops)
    grant.status = "connected" if live_shops else "expired"
    for channel in channels:
        if channel.status != "connected":
            continue
        shop = live_shops.get(channel.external_store_id)
        if shop is None:
            channel.status = "expired"
            channel.metadata_json = {**channel.metadata_json, "oauth_status": "reauthorization_required"}
        else:
            channel.display_name = shop.name
            channel.scopes = grant.scopes
            channel.token_expires_at = access_expires
            channel.metadata_json = {
                **channel.metadata_json,
                "shop_cipher": shop.cipher,
                "shop_code": shop.code,
                "region": shop.region,
                "seller_type": shop.seller_type,
                "refresh_token_expires_at": refresh_expires.isoformat(),
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
                result="succeeded" if shop is not None else "failed",
                after_data={"platform": "tiktok", "shop_authorized": shop is not None},
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
        grant = await claim_tiktok_seller_for_refresh(session, datetime.now(UTC))
        if grant is None:
            break
        try:
            await refresh_tiktok_seller_authorization(session, grant, runtime)
        except AppError:
            pass
        processed += 1
    for _ in range(runtime.tiktok_token_refresh_batch_size - processed):
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
