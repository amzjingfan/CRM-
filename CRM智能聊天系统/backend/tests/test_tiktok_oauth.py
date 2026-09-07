"""REAL-FS-02 TikTok OAuth、凭证加密和租户绑定测试。"""

import hashlib
import hmac
import json
import time
import uuid
from types import SimpleNamespace
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from pydantic import ValidationError

import app.integrations.oauth_service as oauth_service
import app.shared.database.redis as redis_module
import app.stores.service as stores_service
from app.audit.models import AuditLog
from app.auth.dependencies import get_current_user
from app.integrations.credential_crypto import decrypt_credential, encrypt_credential
from app.integrations.oauth_router import router as oauth_router
from app.integrations.oauth_schemas import TikTokAuthorizedShop, TikTokTokenData
from app.integrations.tiktok_oauth import (
    SHOP_PATH,
    SHOP_URL,
    TikTokOAuthClient,
    build_authorization_url,
    generate_api_signature,
)
from app.shared.config.settings import (
    TIKTOK_OAUTH_CALLBACK_ROUTE,
    TIKTOK_OAUTH_FIXED_REDIRECT_URI,
    Settings,
)
from app.shared.exceptions.errors import AppError, ErrorCode
from app.stores.models import ChannelAccount
from app.stores.schemas import ChannelCreate


def oauth_settings(**overrides: Any) -> Settings:
    """构造仅含假数据的 OAuth 测试配置。"""
    values: dict[str, Any] = {
        "TIKTOK_APP_KEY": "unit-test-app-key",
        "TIKTOK_SERVICE_ID": "unit-test-service-id",
        "TIKTOK_APP_SECRET": "unit-test-app-secret-value",
        "TIKTOK_OAUTH_REDIRECT_URI": "https://www.example.com/v1/integrations/tiktok/oauth/callback",
        "TIKTOK_CREDENTIAL_ENCRYPTION_KEY": "unit-test-encryption-key-with-at-least-32-characters",
        "TIKTOK_REQUIRED_SCOPES": "seller.authorization.info",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def token_data(**overrides: Any) -> TikTokTokenData:
    """构造未过期的卖家 Token 契约。"""
    now = int(time.time())
    values: dict[str, Any] = {
        "access_token": "access-token-unit-test-value",
        "access_token_expire_in": now + 3600,
        "refresh_token": "refresh-token-unit-test-value",
        "refresh_token_expire_in": now + 86400,
        "open_id": "seller-open-id",
        "seller_name": "Test Seller",
        "seller_base_region": "GB",
        "user_type": 0,
        "granted_scopes": ["seller.authorization.info"],
    }
    values.update(overrides)
    return TikTokTokenData.model_validate(values)


class FakeRedis:
    """覆盖 Redis SET NX EX 与 GETDEL 的最小内存替身。"""

    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.expirations: dict[str, int] = {}

    async def set(self, key: str, value: str, *, ex: int, nx: bool) -> bool:
        if nx and key in self.values:
            return False
        self.values[key] = value
        self.expirations[key] = ex
        return True

    async def getdel(self, key: str) -> str | None:
        return self.values.pop(key, None)


class FakeSession:
    """记录 OAuth 服务产生的数据库写入，不接触真实数据库。"""

    def __init__(self) -> None:
        self.added: list[object] = []
        self.commits = 0
        self.rollbacks = 0

    def add(self, value: object) -> None:
        self.added.append(value)

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


class FakeChannelSession(FakeSession):
    """为渠道撤销补充主键读取和删除行为。"""

    def __init__(self, channel: ChannelAccount) -> None:
        super().__init__()
        self.channel = channel
        self.deleted: list[object] = []

    async def get(self, _model: object, channel_id: uuid.UUID) -> ChannelAccount | None:
        return self.channel if channel_id == self.channel.id else None

    async def delete(self, value: object) -> None:
        self.deleted.append(value)


class FakeOAuthClient:
    """返回固定卖家 Token 和唯一店铺，不执行公网调用。"""

    def __init__(self, token: TikTokTokenData | None = None, shop_id: str = "external-shop-1") -> None:
        self.token = token or token_data()
        self.shop_id = shop_id

    async def exchange_code(self, auth_code: str) -> TikTokTokenData:
        assert auth_code == "unit-test-auth-code"
        return self.token

    async def refresh_token(self, refresh_token: str) -> TikTokTokenData:
        assert refresh_token == "refresh-token-unit-test-value"
        return self.token

    async def get_authorized_shops(self, access_token: str) -> tuple[list[TikTokAuthorizedShop], str]:
        assert access_token == self.token.access_token
        return (
            [
                TikTokAuthorizedShop(
                    id=self.shop_id,
                    cipher="shop-cipher",
                    code="SHOP-1",
                    name="TikTok Shop One",
                    region="GB",
                    seller_type="LOCAL",
                )
            ],
            "platform-request-id",
        )


def test_authorization_url_uses_market_service_id_and_state_only() -> None:
    """授权 URL 只能暴露 Service ID 和随机 state，不能包含 App Secret。"""
    settings = oauth_settings(TIKTOK_OAUTH_MARKET="US")

    url = build_authorization_url(settings, "random-state")
    parsed = urlparse(url)

    assert parsed.netloc == "services.us.tiktokshop.com"
    assert parse_qs(parsed.query) == {"service_id": ["unit-test-service-id"], "state": ["random-state"]}
    assert settings.tiktok_app_secret is not None
    assert settings.tiktok_app_secret.get_secret_value() not in url


def test_api_signature_excludes_sign_and_access_token() -> None:
    """API 签名按官方顺序拼接，且排除 sign/access_token。"""
    params: dict[str, str | int] = {
        "timestamp": 123,
        "app_key": "app-key",
        "access_token": "must-not-sign",
        "sign": "old-signature",
    }
    secret = "app-secret"
    canonical = f"{secret}{SHOP_PATH}app_keyapp-keytimestamp123{secret}".encode()
    expected = hmac.new(secret.encode(), canonical, hashlib.sha256).hexdigest()

    assert generate_api_signature(SHOP_PATH, params, secret) == expected


def test_credential_encryption_is_context_bound_and_tamper_evident() -> None:
    """Token 密文不能泄露明文，也不能跨店铺/类型解密。"""
    encrypted = encrypt_credential("sensitive-token-value", "master-key", "store-1:access")

    assert "sensitive-token-value" not in encrypted
    assert decrypt_credential(encrypted, "master-key", "store-1:access") == "sensitive-token-value"
    with pytest.raises(ValueError):
        decrypt_credential(encrypted, "master-key", "store-2:access")
    with pytest.raises(ValueError):
        decrypt_credential(encrypted[:-2] + "AA", "master-key", "store-1:access")


@pytest.mark.asyncio
async def test_oauth_state_is_hashed_one_time_and_keeps_ttl(monkeypatch: pytest.MonkeyPatch) -> None:
    """Redis 不保存可直接使用的 state 键，且 GETDEL 使重复回调失效。"""
    fake = FakeRedis()
    monkeypatch.setattr(redis_module, "redis_client", fake)
    state = "one-time-oauth-state"
    payload = {"user_id": str(uuid.uuid4()), "store_id": str(uuid.uuid4()), "return_to": "/settings/channels"}

    assert await redis_module.save_tiktok_oauth_state(state, payload, 600) is True
    stored_key = next(iter(fake.values))
    assert state not in stored_key
    assert fake.expirations[stored_key] == 600
    assert json.loads(fake.values[stored_key]) == payload
    assert await redis_module.consume_tiktok_oauth_state(state) == payload
    assert await redis_module.consume_tiktok_oauth_state(state) is None


@pytest.mark.asyncio
async def test_token_exchange_uses_official_grant_and_hides_secret_from_response() -> None:
    """Token 交换使用官方 authorized_code，不向调用方返回请求凭证。"""
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update({key: value for key, value in request.url.params.multi_items()})
        return httpx.Response(200, json={"code": 0, "message": "Success", "data": token_data().model_dump()})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await TikTokOAuthClient(oauth_settings(), client).exchange_code("unit-test-auth-code")

    assert seen == {
        "app_key": "unit-test-app-key",
        "app_secret": "unit-test-app-secret-value",
        "auth_code": "unit-test-auth-code",
        "grant_type": "authorized_code",
    }
    assert result.open_id == "seller-open-id"


@pytest.mark.asyncio
async def test_authorized_shop_request_is_signed_and_uses_token_header() -> None:
    """授权店铺读取必须签名，并只在请求 Header 携带 Access Token。"""
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["token"] = request.headers.get("x-tts-access-token")
        return httpx.Response(
            200,
            json={
                "code": 0,
                "message": "Success",
                "request_id": "request-1",
                "data": {
                    "shops": [
                        {
                            "id": "external-shop-1",
                            "cipher": "cipher",
                            "code": "SHOP-1",
                            "name": "Shop One",
                            "region": "GB",
                            "seller_type": "LOCAL",
                        }
                    ]
                },
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        shops, request_id = await TikTokOAuthClient(oauth_settings(), client).get_authorized_shops(
            "access-token-unit-test-value"
        )

    query = parse_qs(urlparse(seen["url"]).query)
    assert seen["url"].startswith(SHOP_URL)
    assert query["app_key"] == ["unit-test-app-key"]
    assert len(query["sign"][0]) == 64
    assert seen["token"] == "access-token-unit-test-value"
    assert shops[0].id == "external-shop-1"
    assert request_id == "request-1"


def test_oauth_runtime_and_return_url_fail_closed() -> None:
    """服务端配置缺失或开放重定向目标必须在授权开始前拒绝。"""
    with pytest.raises(AppError, match="OAuth 尚未配置"):
        oauth_service.validate_oauth_runtime(Settings(_env_file=None))
    with pytest.raises(AppError, match="回跳地址无效"):
        oauth_service.validate_return_to("https://attacker.example/callback")
    with pytest.raises(AppError, match="回跳地址无效"):
        oauth_service.validate_return_to("/settings/channels?unexpected=1")
    with pytest.raises(AppError, match="回跳地址无效"):
        oauth_service.validate_return_to("/settings/channels#fragment")


@pytest.mark.parametrize(
    "unsafe_redirect_uri",
    [
        "http://www.example.com/v1/integrations/tiktok/oauth/callback",
        "https://www.example.com/v1/integrations/tiktok/oauth/wrong",
        "https://www.example.com/v1/integrations/tiktok/oauth/callback?next=unexpected",
        "https://www.example.com/v1/integrations/tiktok/oauth/callback#fragment",
    ],
)
def test_oauth_runtime_rejects_invalid_callback_before_authorization_start(unsafe_redirect_uri: str) -> None:
    """即使配置对象绕过启动校验，OAuth 服务也必须在生成 state 前失败关闭。"""
    settings = oauth_settings().model_copy(update={"tiktok_oauth_redirect_uri": unsafe_redirect_uri})

    with pytest.raises(AppError, match="OAuth 回调配置无效"):
        oauth_service.validate_oauth_runtime(settings)


def test_oauth_callback_route_matches_fixed_production_redirect_uri() -> None:
    """公开回调声明必须与实际 FastAPI 路由共享固定路径契约。"""
    route_paths = {route.path for route in oauth_router.routes}

    assert TIKTOK_OAUTH_CALLBACK_ROUTE in route_paths
    assert TIKTOK_OAUTH_FIXED_REDIRECT_URI.endswith(f"/v1{TIKTOK_OAUTH_CALLBACK_ROUTE}")


def test_oauth_callback_does_not_require_crm_browser_cookie() -> None:
    """独立卖家浏览器回调只校验一次性 state，不能额外依赖 CRM Cookie。"""
    callback_route = next(route for route in oauth_router.routes if route.path == TIKTOK_OAUTH_CALLBACK_ROUTE)

    assert all(dependency.call is not get_current_user for dependency in callback_route.dependant.dependencies)


@pytest.mark.asyncio
async def test_oauth_start_rejects_invalid_callback_before_store_or_state_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """错误回调必须先于店铺查询和 Redis state 写入失败关闭。"""
    store_access_checked = False

    async def unexpected_store_access(*_: object) -> None:
        nonlocal store_access_checked
        store_access_checked = True

    monkeypatch.setattr(oauth_service, "ensure_store_access", unexpected_store_access)
    settings = oauth_settings().model_copy(
        update={"tiktok_oauth_redirect_uri": "http://attacker.example/v1/integrations/tiktok/oauth/callback"}
    )

    with pytest.raises(AppError, match="OAuth 回调配置无效"):
        await oauth_service.start_tiktok_oauth(
            FakeSession(),
            SimpleNamespace(id=uuid.uuid4()),
            uuid.uuid4(),
            settings=settings,
        )

    assert store_access_checked is False


def test_manual_channel_schema_rejects_tiktok_oauth_bypass() -> None:
    """通用渠道接口不能伪造 TikTok connected 记录。"""
    with pytest.raises(ValidationError):
        ChannelCreate.model_validate(
            {
                "store_id": str(uuid.uuid4()),
                "platform": "tiktok",
                "external_store_id": "forged-shop",
                "display_name": "Forged TikTok",
                "access_token_ref": "forged-token-ref",
            }
        )


@pytest.mark.asyncio
async def test_channel_service_rejects_internal_tiktok_schema_bypass() -> None:
    """内部调用即使跳过 Pydantic 校验，也不能绕过 TikTok OAuth。"""
    payload = ChannelCreate.model_construct(
        store_id=uuid.uuid4(),
        platform="tiktok",
        external_store_id="forged-shop",
        display_name="Forged TikTok",
        access_token_ref="forged-token-ref",
        scopes=[],
    )

    with pytest.raises(AppError, match="必须通过 OAuth"):
        await stores_service.create_channel(  # type: ignore[arg-type]
            FakeSession(),
            SimpleNamespace(id=uuid.uuid4()),
            payload,
        )


@pytest.mark.parametrize(
    "invalid_token",
    [
        token_data(user_type=1),
        token_data(granted_scopes=[]),
        token_data(access_token_expire_in=1),
    ],
)
def test_token_contract_rejects_non_seller_missing_scope_and_expiry(invalid_token: TikTokTokenData) -> None:
    """创作者、缺少 Scope 或过期 Token 都不能绑定真实店铺。"""
    with pytest.raises(AppError):
        oauth_service._validate_token_contract(invalid_token, oauth_settings())


@pytest.mark.asyncio
async def test_complete_oauth_encrypts_tokens_only_after_store_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    """正常回调完成后仅保存密文和低敏店铺摘要。"""
    user_id = uuid.uuid4()
    store_id = uuid.uuid4()
    session = FakeSession()
    state_payload = {"user_id": str(user_id), "store_id": str(store_id), "return_to": "/settings/channels"}
    monkeypatch.setattr(oauth_service, "consume_tiktok_oauth_state", _async_result(state_payload))
    monkeypatch.setattr(
        oauth_service,
        "find_user_by_id",
        _async_result(SimpleNamespace(id=user_id, status="active")),
    )
    monkeypatch.setattr(oauth_service, "ensure_store_access", _async_result(None))
    monkeypatch.setattr(oauth_service, "get_active_store", _async_result(SimpleNamespace(id=store_id)))
    monkeypatch.setattr(oauth_service, "find_channel_by_external_store", _async_result(None))
    monkeypatch.setattr(oauth_service, "find_channel_by_store_platform", _async_result(None))

    result = await oauth_service.complete_tiktok_oauth(
        session,  # type: ignore[arg-type]
        "valid-state",
        "unit-test-auth-code",
        None,
        oauth_settings(),
        FakeOAuthClient(),  # type: ignore[arg-type]
    )

    channel = next(value for value in session.added if isinstance(value, ChannelAccount))
    audit = next(value for value in session.added if isinstance(value, AuditLog))
    assert result.status == "connected"
    assert channel.status == "connected"
    assert channel.external_store_id == "external-shop-1"
    assert channel.access_token_ref.startswith("encrypted:v1:")
    assert channel.refresh_token_ref is not None and channel.refresh_token_ref.startswith("encrypted:v1:")
    assert "access-token-unit-test-value" not in channel.access_token_ref
    assert "refresh-token-unit-test-value" not in channel.refresh_token_ref
    assert channel.metadata_json["open_id_hash"] != "seller-open-id"
    assert audit.action == "channel.authorize"
    assert audit.result == "succeeded"
    assert session.commits == 1


@pytest.mark.asyncio
async def test_complete_oauth_rejects_replay_and_unavailable_initiator(monkeypatch: pytest.MonkeyPatch) -> None:
    """缺失/重复 state 或不可用的发起用户都不能交换 Token。"""
    session = FakeSession()
    monkeypatch.setattr(oauth_service, "consume_tiktok_oauth_state", _async_result(None))
    with pytest.raises(AppError) as missing:
        await oauth_service.complete_tiktok_oauth(session, "used-state", "code", None)  # type: ignore[arg-type]
    assert missing.value.code == ErrorCode.VALIDATION_ERROR

    user_id = uuid.uuid4()
    payload = {
        "user_id": str(user_id),
        "store_id": str(uuid.uuid4()),
        "return_to": "/settings/channels",
    }
    monkeypatch.setattr(oauth_service, "consume_tiktok_oauth_state", _async_result(payload))
    monkeypatch.setattr(oauth_service, "find_user_by_id", _async_result(None))
    with pytest.raises(AppError) as unavailable:
        await oauth_service.complete_tiktok_oauth(session, "valid-state", "code", None)  # type: ignore[arg-type]
    assert unavailable.value.code == ErrorCode.PERMISSION_DENIED


@pytest.mark.asyncio
async def test_complete_oauth_rejects_cross_store_binding_without_partial_channel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """同一外部店铺不得绑定两个租户，失败只保留低敏审计。"""
    user_id = uuid.uuid4()
    store_id = uuid.uuid4()
    payload = {"user_id": str(user_id), "store_id": str(store_id), "return_to": "/settings/channels"}
    session = FakeSession()
    monkeypatch.setattr(oauth_service, "consume_tiktok_oauth_state", _async_result(payload))
    monkeypatch.setattr(
        oauth_service,
        "find_user_by_id",
        _async_result(SimpleNamespace(id=user_id, status="active")),
    )
    monkeypatch.setattr(oauth_service, "ensure_store_access", _async_result(None))
    monkeypatch.setattr(oauth_service, "get_active_store", _async_result(SimpleNamespace(id=store_id)))
    monkeypatch.setattr(
        oauth_service,
        "find_channel_by_external_store",
        _async_result(SimpleNamespace(store_id=uuid.uuid4())),
    )

    with pytest.raises(AppError) as conflict:
        await oauth_service.complete_tiktok_oauth(
            session,  # type: ignore[arg-type]
            "valid-state",
            "unit-test-auth-code",
            None,
            oauth_settings(),
            FakeOAuthClient(),  # type: ignore[arg-type]
        )

    assert conflict.value.code == ErrorCode.RESOURCE_CONFLICT
    assert not any(isinstance(value, ChannelAccount) for value in session.added)
    assert any(isinstance(value, AuditLog) and value.result == "failed" for value in session.added)
    assert session.rollbacks == 1


@pytest.mark.asyncio
async def test_refresh_updates_encrypted_tokens_and_audit() -> None:
    """刷新成功后继续保存认证密文，并追踪刷新状态。"""
    store_id = uuid.uuid4()
    channel = ChannelAccount(
        id=uuid.uuid4(),
        store_id=store_id,
        platform="tiktok",
        external_store_id="external-shop-1",
        display_name="Shop One",
        access_token_ref="old-encrypted-value",
        refresh_token_ref=encrypt_credential(
            "refresh-token-unit-test-value",
            "unit-test-encryption-key-with-at-least-32-characters",
            f"tiktok:{store_id}:external-shop-1:refresh",
        ),
        metadata_json={"open_id_hash": hashlib.sha256(b"seller-open-id").hexdigest()},
    )
    session = FakeSession()

    await oauth_service.refresh_tiktok_channel_token(
        session,  # type: ignore[arg-type]
        channel,
        oauth_settings(),
        FakeOAuthClient(),  # type: ignore[arg-type]
    )

    assert channel.status == "connected"
    assert channel.access_token_ref.startswith("encrypted:v1:")
    assert channel.metadata_json["oauth_status"] == "refreshed"
    assert any(isinstance(value, AuditLog) and value.action == "channel.token_refresh" for value in session.added)


@pytest.mark.asyncio
async def test_refresh_rejects_changed_authorization_principal_without_overwriting_tokens() -> None:
    """刷新返回其他 open_id 时必须保留旧密文并要求重新授权。"""
    store_id = uuid.uuid4()
    old_access = "encrypted:v1:old-access"
    old_refresh = encrypt_credential(
        "refresh-token-unit-test-value",
        "unit-test-encryption-key-with-at-least-32-characters",
        f"tiktok:{store_id}:external-shop-1:refresh",
    )
    channel = ChannelAccount(
        id=uuid.uuid4(),
        store_id=store_id,
        platform="tiktok",
        external_store_id="external-shop-1",
        display_name="Shop One",
        access_token_ref=old_access,
        refresh_token_ref=old_refresh,
        metadata_json={"open_id_hash": hashlib.sha256(b"seller-open-id").hexdigest()},
    )
    session = FakeSession()

    with pytest.raises(AppError, match="重新授权"):
        await oauth_service.refresh_tiktok_channel_token(
            session,  # type: ignore[arg-type]
            channel,
            oauth_settings(),
            FakeOAuthClient(token_data(open_id="different-seller-open-id")),  # type: ignore[arg-type]
        )

    assert channel.status == "expired"
    assert channel.access_token_ref == old_access
    assert channel.refresh_token_ref == old_refresh
    assert channel.metadata_json["oauth_status"] == "reauthorization_required"
    assert any(isinstance(value, AuditLog) and value.result == "failed" for value in session.added)


@pytest.mark.asyncio
async def test_refresh_rejects_changed_authorized_shop() -> None:
    """刷新后的授权店铺必须继续匹配当前渠道的外部店铺 ID。"""
    store_id = uuid.uuid4()
    channel = ChannelAccount(
        id=uuid.uuid4(),
        store_id=store_id,
        platform="tiktok",
        external_store_id="external-shop-1",
        display_name="Shop One",
        access_token_ref="encrypted:v1:old-access",
        refresh_token_ref=encrypt_credential(
            "refresh-token-unit-test-value",
            "unit-test-encryption-key-with-at-least-32-characters",
            f"tiktok:{store_id}:external-shop-1:refresh",
        ),
        metadata_json={"open_id_hash": hashlib.sha256(b"seller-open-id").hexdigest()},
    )

    with pytest.raises(AppError, match="重新授权"):
        await oauth_service.refresh_tiktok_channel_token(
            FakeSession(),  # type: ignore[arg-type]
            channel,
            oauth_settings(),
            FakeOAuthClient(shop_id="different-external-shop"),  # type: ignore[arg-type]
        )

    assert channel.status == "expired"
    assert channel.access_token_ref == "encrypted:v1:old-access"


@pytest.mark.asyncio
async def test_token_refresh_cycle_claims_due_channels_and_continues_after_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Jobs 刷新入口必须批量认领，单店铺失败不能阻断其他店铺。"""
    channels = [SimpleNamespace(id=uuid.uuid4()), SimpleNamespace(id=uuid.uuid4()), None]
    refreshed: list[uuid.UUID] = []

    async def claim(*_args: Any, **_kwargs: Any) -> Any:
        return channels.pop(0)

    async def refresh(_session: Any, channel: Any, *_args: Any, **_kwargs: Any) -> None:
        refreshed.append(channel.id)
        if len(refreshed) == 1:
            raise AppError(ErrorCode.THIRD_PARTY_ERROR, "刷新失败", 502)

    monkeypatch.setattr(oauth_service, "claim_tiktok_channel_for_refresh", claim)
    monkeypatch.setattr(oauth_service, "refresh_tiktok_channel_token", refresh)

    processed = await oauth_service.process_tiktok_token_refresh_cycle(
        FakeSession(),  # type: ignore[arg-type]
        oauth_settings(TIKTOK_TOKEN_REFRESH_BATCH_SIZE=3),
    )

    assert processed == 2
    assert len(refreshed) == 2


@pytest.mark.asyncio
async def test_revoke_destroys_local_tokens_and_keeps_lifecycle_audit(monkeypatch: pytest.MonkeyPatch) -> None:
    """撤销真实 OAuth 渠道时不物理删除证据，并立即使本地 Token 不可用。"""
    store_id = uuid.uuid4()
    channel = ChannelAccount(
        id=uuid.uuid4(),
        store_id=store_id,
        platform="tiktok",
        external_store_id="external-shop-1",
        display_name="Shop One",
        access_token_ref="encrypted:v1:not-a-real-token",
        refresh_token_ref="encrypted:v1:not-a-real-refresh-token",
        metadata_json={},
    )
    session = FakeChannelSession(channel)
    monkeypatch.setattr(stores_service, "ensure_store_access", _async_result(None))

    await stores_service.delete_channel(
        session,  # type: ignore[arg-type]
        SimpleNamespace(id=uuid.uuid4()),  # type: ignore[arg-type]
        channel.id,
    )

    assert channel.status == "disconnected"
    assert channel.access_token_ref == f"revoked://{channel.id}"
    assert channel.refresh_token_ref is None
    assert channel.token_expires_at is None
    assert channel.metadata_json["oauth_status"] == "revoked"
    assert session.deleted == []
    assert any(isinstance(value, AuditLog) and value.action == "channel.revoke" for value in session.added)


def _async_result(value: Any) -> Any:
    """返回忽略入参并产生固定结果的异步函数。"""

    async def result(*_args: Any, **_kwargs: Any) -> Any:
        return value

    return result
