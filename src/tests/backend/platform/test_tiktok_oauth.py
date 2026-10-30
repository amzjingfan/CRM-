"""REAL-FS-02 TikTok OAuth、凭证加密和租户绑定测试。"""

import hashlib
import hmac
import json
import time
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from pydantic import ValidationError

import app.integrations.oauth_service as oauth_service
import app.integrations.tiktok_oauth as tiktok_oauth_module
import app.shared.database.redis as redis_module
import app.stores.models as store_models
import app.stores.service as stores_service
from app.audit.models import AuditLog
from app.auth.dependencies import get_current_user
from app.integrations.credential_crypto import decrypt_credential, encrypt_credential
from app.integrations.models import TikTokOAuthJob
from app.integrations.oauth_router import router as oauth_router
from app.integrations.oauth_schemas import TikTokAuthorizedShop, TikTokShopData, TikTokTokenData
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
from app.stores.models import ChannelAccount, Store
from app.stores.schemas import ChannelCreate, ChannelView, StoreAliasUpdate, StoreView


def oauth_settings(**overrides: Any) -> Settings:
    """构造仅含假数据的 OAuth 测试配置。"""
    values: dict[str, Any] = {
        "TIKTOK_APP_KEY": "unit-test-app-key",
        "TIKTOK_SERVICE_ID": "unit-test-service-id",
        "TIKTOK_APP_SECRET": "unit-test-app-secret-value",
        "TIKTOK_OAUTH_REDIRECT_URI": "https://www.example.com/v1/integrations/tiktok/oauth/callback",
        "TIKTOK_CREDENTIAL_ENCRYPTION_KEY": "unit-test-encryption-key-with-at-least-32-characters",
        "TIKTOK_EGRESS_PROXY_URL": "socks5h://127.0.0.1:1080",
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


def test_authorized_shop_response_accepts_more_than_twenty_shops() -> None:
    """平台卖家拥有二十余家店时仍可选择其中若干家。"""
    shops = [
        {
            "id": f"external-shop-{index}",
            "cipher": f"cipher-{index}",
            "code": f"SHOP-{index}",
            "name": f"Shop {index}",
            "region": "US",
            "seller_type": "LOCAL",
        }
        for index in range(21)
    ]
    assert len(TikTokShopData.model_validate({"shops": shops}).shops) == 21


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


class FakeSelectionSession(FakeSession):
    """只模拟本测试需要的待选择任务与空数据库结果。"""

    def __init__(self, job: TikTokOAuthJob) -> None:
        super().__init__()
        self.job = job

    async def get(self, model: object, _id: uuid.UUID, **_kwargs: object) -> TikTokOAuthJob | None:
        return self.job if model is TikTokOAuthJob and _id == self.job.id else None

    async def scalar(self, _statement: object) -> None:
        return None

    async def scalars(self, _statement: object) -> Any:
        return SimpleNamespace(all=lambda: [])


class FakeOAuthClient:
    """返回固定卖家 Token 和唯一店铺，不执行公网调用。"""

    def __init__(
        self, token: TikTokTokenData | None = None, shop_id: str = "external-shop-1", shop_count: int = 1
    ) -> None:
        self.token = token or token_data()
        self.shop_id = shop_id
        self.shop_count = shop_count

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
                    id=self.shop_id if index == 0 else f"external-shop-{index + 1}",
                    cipher="shop-cipher" if index == 0 else f"shop-cipher-{index + 1}",
                    code=f"SHOP-{index + 1}",
                    name="TikTok Shop One" if index == 0 else f"TikTok Shop {index + 1}",
                    region="GB",
                    seller_type="LOCAL",
                )
                for index in range(self.shop_count)
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


def test_shared_seller_credential_is_shop_bound_and_legacy_channel_still_works() -> None:
    """多店共享卖家 Token 时仅已关联且仍在授权列表中的店铺可使用。"""
    settings = oauth_settings()
    grant_id, store_id = uuid.uuid4(), uuid.uuid4()
    key = settings.tiktok_credential_encryption_key
    assert key is not None
    grant = store_models.TikTokSellerAuthorization(
        id=grant_id,
        app_key=settings.tiktok_app_key,
        open_id_hash=hashlib.sha256(b"seller-open-id").hexdigest(),
        access_token_ref=encrypt_credential(
            "shared-access-token-unit-test",
            key.get_secret_value(),
            f"tiktok:seller:{grant_id}:access",
        ),
        refresh_token_ref="encrypted:v1:unused",
        access_expires_at=datetime.now(UTC) + timedelta(hours=1),
        refresh_expires_at=datetime.now(UTC) + timedelta(days=1),
        authorized_shop_ids=["external-shop-1"],
        status="connected",
    )
    channel = ChannelAccount(
        store_id=store_id,
        platform="tiktok",
        external_store_id="external-shop-1",
        display_name="Shop One",
        access_token_ref=f"shared://{grant_id}",
        seller_authorization_id=grant_id,
        seller_authorization=grant,
        status="connected",
        metadata_json={"open_id_hash": grant.open_id_hash},
    )
    assert oauth_service.decrypt_tiktok_access_token(channel, settings) == "shared-access-token-unit-test"
    channel.external_store_id = "unapproved-shop"
    with pytest.raises(AppError):
        oauth_service.decrypt_tiktok_access_token(channel, settings)


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
async def test_oauth_default_client_uses_fixed_egress_factory(monkeypatch: pytest.MonkeyPatch) -> None:
    """默认 OAuth 传输绕过固定出口工厂时必须失败。"""
    settings = oauth_settings()
    factory_calls: list[Settings] = []
    async_client_type = httpx.AsyncClient

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"code": 0, "message": "Success", "data": token_data().model_dump()})

    def fake_factory(candidate: Settings) -> httpx.AsyncClient:
        factory_calls.append(candidate)
        return async_client_type(transport=httpx.MockTransport(handler))

    def reject_direct_client(**_kwargs: object) -> httpx.AsyncClient:
        raise AssertionError("OAuth client bypassed the fixed-egress factory")

    monkeypatch.setattr(tiktok_oauth_module, "create_tiktok_http_client", fake_factory, raising=False)
    monkeypatch.setattr(tiktok_oauth_module.httpx, "AsyncClient", reject_direct_client)

    result = await TikTokOAuthClient(settings).exchange_code("unit-test-auth-code")

    assert result.open_id == "seller-open-id"
    assert factory_calls == [settings]


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
    assert oauth_service.validate_return_to("/settings/stores") == "/settings/stores"


@pytest.mark.asyncio
async def test_direct_add_starts_oauth_without_creating_store(monkeypatch: pytest.MonkeyPatch) -> None:
    """新店按钮只发一次性授权链接，卖家授权前不写内部店铺。"""
    saved: list[dict[str, str]] = []

    async def global_admin(*_: object) -> None:
        return None

    async def save(_: str, payload: dict[str, str], __: int) -> bool:
        saved.append(payload)
        return True

    monkeypatch.setattr(oauth_service, "ensure_system_store_admin", global_admin)
    monkeypatch.setattr(oauth_service, "save_tiktok_oauth_state", save)
    user_id = uuid.uuid4()
    session = FakeSession()
    result = await oauth_service.start_new_tiktok_store_oauth(  # type: ignore[arg-type]
        session, SimpleNamespace(id=user_id), oauth_settings()
    )
    assert result.authorization_url.startswith("https://services.tiktokshop.com/open/authorize?")
    assert saved == [{"user_id": str(user_id), "return_to": "/settings/stores"}]
    assert session.added == [] and session.commits == 0


@pytest.mark.asyncio
async def test_direct_add_requires_system_admin_before_state_creation(monkeypatch: pytest.MonkeyPatch) -> None:
    """店铺级角色即使可读已有店铺，也不能开辟新租户。"""

    async def denied(*_: object) -> None:
        raise AppError(ErrorCode.PERMISSION_DENIED, "没有添加店铺的权限", 403)

    async def unexpected_save(*_: object) -> bool:
        raise AssertionError("不得写入 OAuth state")

    monkeypatch.setattr(oauth_service, "ensure_system_store_admin", denied)
    monkeypatch.setattr(oauth_service, "save_tiktok_oauth_state", unexpected_save)
    with pytest.raises(AppError) as error:
        await oauth_service.start_new_tiktok_store_oauth(  # type: ignore[arg-type]
            FakeSession(), SimpleNamespace(id=uuid.uuid4()), oauth_settings()
        )
    assert error.value.code == ErrorCode.PERMISSION_DENIED


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
    monkeypatch.setattr(oauth_service, "ensure_store_channel_manager", _async_result(None))
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
async def test_multi_shop_oauth_waits_for_admin_selection_without_creating_stores(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """一次卖家授权返回多家店铺时，先安全暂存授权而不擅自连接全部店铺。"""
    user_id = uuid.uuid4()
    job = TikTokOAuthJob(id=uuid.uuid4(), user_id=user_id, return_to="/settings/stores", status="processing")
    session = FakeSession()
    monkeypatch.setattr(
        oauth_service,
        "consume_tiktok_oauth_state",
        _async_result(
            {
                "user_id": str(user_id),
                "return_to": "/settings/stores",
            }
        ),
    )
    monkeypatch.setattr(oauth_service, "find_user_by_id", _async_result(SimpleNamespace(id=user_id, status="active")))
    monkeypatch.setattr(oauth_service, "ensure_system_store_admin", _async_result(None))

    result = await oauth_service.complete_tiktok_oauth(  # type: ignore[arg-type]
        session,
        "valid-state",
        "unit-test-auth-code",
        None,
        oauth_settings(),
        FakeOAuthClient(shop_count=2),
        job=job,
    )

    assert result.status == "selection_required"
    assert len(job.selection_shops) == 2
    assert job.selection_token_cipher is not None
    assert "access-token-unit-test-value" not in job.selection_token_cipher
    assert not any(isinstance(value, (Store, ChannelAccount)) for value in session.added)


@pytest.mark.asyncio
async def test_admin_selection_creates_two_isolated_shops_with_one_seller_grant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """勾选两店后以同一卖家凭证原子绑定，店铺和渠道各自独立。"""
    user_id = uuid.uuid4()
    job = TikTokOAuthJob(
        id=uuid.uuid4(),
        user_id=user_id,
        return_to="/settings/stores",
        status="selection_required",
        selection_expires_at=datetime.now(UTC) + timedelta(minutes=5),
        selection_shops=[
            shop.model_dump()
            for shop in (await FakeOAuthClient(shop_count=2).get_authorized_shops("access-token-unit-test-value"))[0]
        ],
    )
    key = oauth_settings().tiktok_credential_encryption_key
    assert key is not None
    job.selection_token_cipher = encrypt_credential(
        token_data().model_dump_json(), key.get_secret_value(), f"tiktok:oauth-job:{job.id}:selection"
    )
    session = FakeSelectionSession(job)
    user = SimpleNamespace(id=user_id, status="active")
    monkeypatch.setattr(oauth_service, "ensure_system_store_admin", _async_result(None))
    monkeypatch.setattr(oauth_service, "find_channel_by_external_store", _async_result(None))
    monkeypatch.setattr(oauth_service, "find_channel_by_store_platform", _async_result(None))

    result = await oauth_service.select_tiktok_oauth_shops(  # type: ignore[arg-type]
        session,
        user,
        job.id,
        ["external-shop-1", "external-shop-2"],
        oauth_settings(),
        FakeOAuthClient(shop_count=2),
    )

    grants = [item for item in session.added if isinstance(item, store_models.TikTokSellerAuthorization)]
    stores = [item for item in session.added if isinstance(item, Store)]
    channels = [item for item in session.added if isinstance(item, ChannelAccount)]
    assert result.status == "connected"
    assert len(grants) == 1 and len(stores) == len(channels) == 2
    assert len({channel.store_id for channel in channels}) == 2
    assert {channel.seller_authorization_id for channel in channels} == {grants[0].id}
    assert all(channel.access_token_ref.startswith("shared://") for channel in channels)
    assert job.selection_token_cipher is None and job.status == "connected"


@pytest.mark.asyncio
async def test_multi_shop_selection_conflict_does_not_mutate_seller_grant(monkeypatch: pytest.MonkeyPatch) -> None:
    """任一勾选店铺已绑定其他卖家时，本次选择整体失败，不部分接入。"""
    user_id = uuid.uuid4()
    shops = (await FakeOAuthClient(shop_count=2).get_authorized_shops("access-token-unit-test-value"))[0]
    job = TikTokOAuthJob(
        id=uuid.uuid4(),
        user_id=user_id,
        return_to="/settings/stores",
        status="selection_required",
        selection_expires_at=datetime.now(UTC) + timedelta(minutes=5),
        selection_shops=[shop.model_dump() for shop in shops],
    )
    key = oauth_settings().tiktok_credential_encryption_key
    assert key is not None
    job.selection_token_cipher = encrypt_credential(
        token_data().model_dump_json(), key.get_secret_value(), f"tiktok:oauth-job:{job.id}:selection"
    )
    session = FakeSelectionSession(job)
    other_seller = ChannelAccount(
        id=uuid.uuid4(),
        store_id=uuid.uuid4(),
        platform="tiktok",
        external_store_id=shops[1].id,
        display_name="Other seller shop",
        access_token_ref="encrypted:v1:other",
        status="connected",
        metadata_json={"open_id_hash": hashlib.sha256(b"other-seller").hexdigest()},
    )

    async def find_binding(
        _session: object, _platform: str, shop_id: str, *, for_update: bool = False
    ) -> ChannelAccount | None:
        assert for_update
        return other_seller if shop_id == shops[1].id else None

    monkeypatch.setattr(oauth_service, "ensure_system_store_admin", _async_result(None))
    monkeypatch.setattr(oauth_service, "find_channel_by_external_store", find_binding)
    with pytest.raises(AppError) as error:
        await oauth_service.select_tiktok_oauth_shops(  # type: ignore[arg-type]
            session,
            SimpleNamespace(id=user_id),
            job.id,
            [shop.id for shop in shops],
            oauth_settings(),
            FakeOAuthClient(shop_count=2),
        )
    assert error.value.code == ErrorCode.RESOURCE_CONFLICT
    assert job.status == "selection_required" and job.selection_token_cipher is not None
    assert not any(
        isinstance(item, (Store, ChannelAccount, store_models.TikTokSellerAuthorization)) for item in session.added
    )


@pytest.mark.asyncio
async def test_selection_status_returns_shop_choices_without_cipher_or_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """管理端只获得低敏选择摘要，不能取得 shop_cipher、open_id 或 Token。"""
    user_id = uuid.uuid4()
    shop = (await FakeOAuthClient().get_authorized_shops("access-token-unit-test-value"))[0][0]
    job = TikTokOAuthJob(
        id=uuid.uuid4(),
        user_id=user_id,
        return_to="/settings/stores",
        status="selection_required",
        selection_expires_at=datetime.now(UTC) + timedelta(minutes=5),
        selection_shops=[shop.model_dump()],
        selection_token_cipher="encrypted:v1:secret",
    )
    monkeypatch.setattr(oauth_service, "ensure_system_store_admin", _async_result(None))
    status = await oauth_service.get_tiktok_oauth_job_status(  # type: ignore[arg-type]
        FakeSelectionSession(job), SimpleNamespace(id=user_id), job.id
    )
    serialized = status.model_dump_json()
    assert status.status == "selection_required"
    assert status.shops[0].name == "TikTok Shop One"
    assert "shop-cipher" not in serialized and "encrypted" not in serialized


@pytest.mark.asyncio
async def test_failed_job_returns_only_stable_error_code(monkeypatch: pytest.MonkeyPatch) -> None:
    """授权失败提示使用稳定低敏错误码，不把任务密文或平台响应交给浏览器。"""
    user_id = uuid.uuid4()
    store_id = uuid.uuid4()
    job = TikTokOAuthJob(
        id=uuid.uuid4(),
        user_id=user_id,
        store_id=store_id,
        return_to="/settings/stores",
        status="failed",
        error_code="STATE_EXPIRED",
        state_cipher="encrypted:v1:secret",
    )
    monkeypatch.setattr(oauth_service, "ensure_store_access", _async_result(None))
    monkeypatch.setattr(oauth_service, "ensure_store_channel_manager", _async_result(None))
    status = await oauth_service.get_tiktok_oauth_job_status(  # type: ignore[arg-type]
        FakeSelectionSession(job), SimpleNamespace(id=user_id), job.id
    )
    assert status.status == "failed"
    assert status.error_code == "STATE_EXPIRED"
    assert status.store_id == store_id
    assert "encrypted" not in status.model_dump_json()


@pytest.mark.asyncio
async def test_cleanup_scrubs_expired_shop_selection_before_receipt_retention() -> None:
    """待选择任务到期后应抹除卖家 Token 密文，而非等到收据整行删除。"""
    statements: list[str] = []

    class CleanupSession(FakeSession):
        async def execute(self, statement: object) -> None:
            statements.append(str(statement))

    await oauth_service.cleanup_tiktok_oauth_jobs(CleanupSession())  # type: ignore[arg-type]
    assert statements[0].startswith("UPDATE tiktok_oauth_jobs")
    assert "selection_token_cipher" in statements[0]
    assert "selection_expires_at" in statements[0]


@pytest.mark.asyncio
async def test_direct_add_creates_store_only_after_verified_shop(monkeypatch: pytest.MonkeyPatch) -> None:
    """平台返回唯一卖家店铺且 Scope 完整后，才原子建立系统 ID 和渠道。"""
    user_id = uuid.uuid4()
    session = FakeSession()
    monkeypatch.setattr(
        oauth_service,
        "consume_tiktok_oauth_state",
        _async_result(
            {
                "user_id": str(user_id),
                "return_to": "/settings/stores",
            }
        ),
    )
    monkeypatch.setattr(oauth_service, "find_user_by_id", _async_result(SimpleNamespace(id=user_id, status="active")))
    monkeypatch.setattr(oauth_service, "ensure_system_store_admin", _async_result(None))
    monkeypatch.setattr(oauth_service, "find_channel_by_external_store", _async_result(None))
    monkeypatch.setattr(oauth_service, "find_channel_by_store_platform", _async_result(None))

    result = await oauth_service.complete_tiktok_oauth(  # type: ignore[arg-type]
        session, "valid-state", "unit-test-auth-code", None, oauth_settings(), FakeOAuthClient()
    )

    store = next(value for value in session.added if isinstance(value, Store))
    channel = next(value for value in session.added if isinstance(value, ChannelAccount))
    assert result.status == "connected" and result.return_to == "/settings/stores"
    assert result.store_id == store.id == channel.store_id
    assert store.name == "TikTok Shop One" and store.currency == "GBP"
    assert store.code == f"tiktok-{store.id.hex}"
    assert channel.metadata_json["region"] == "GB"
    assert isinstance(channel.metadata_json["last_authorized_at"], str)
    assert session.commits == 1


@pytest.mark.asyncio
async def test_direct_add_denial_leaves_no_empty_store(monkeypatch: pytest.MonkeyPatch) -> None:
    """卖家取消授权时只记低敏失败审计，不留占位店铺。"""
    user_id = uuid.uuid4()
    session = FakeSession()
    monkeypatch.setattr(
        oauth_service,
        "consume_tiktok_oauth_state",
        _async_result(
            {
                "user_id": str(user_id),
                "return_to": "/settings/stores",
            }
        ),
    )
    monkeypatch.setattr(oauth_service, "find_user_by_id", _async_result(SimpleNamespace(id=user_id, status="active")))
    monkeypatch.setattr(oauth_service, "ensure_system_store_admin", _async_result(None))
    result = await oauth_service.complete_tiktok_oauth(  # type: ignore[arg-type]
        session, "valid-state", None, "seller_denied", oauth_settings()
    )
    assert result.status == "denied"
    assert not any(isinstance(value, Store) for value in session.added)
    assert any(isinstance(value, AuditLog) and value.result == "failed" for value in session.added)


@pytest.mark.asyncio
async def test_direct_add_reuses_disconnected_store_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """删除授权后重新添加同一平台店铺，复用旧租户和业务历史。"""
    user_id, store_id = uuid.uuid4(), uuid.uuid4()
    channel = ChannelAccount(
        id=uuid.uuid4(),
        store_id=store_id,
        platform="tiktok",
        external_store_id="external-shop-1",
        display_name="Old shop",
        access_token_ref="revoked://old",
        status="disconnected",
        metadata_json={},
    )
    session = FakeSession()
    monkeypatch.setattr(
        oauth_service,
        "consume_tiktok_oauth_state",
        _async_result(
            {
                "user_id": str(user_id),
                "return_to": "/settings/stores",
            }
        ),
    )
    monkeypatch.setattr(oauth_service, "find_user_by_id", _async_result(SimpleNamespace(id=user_id, status="active")))
    monkeypatch.setattr(oauth_service, "ensure_system_store_admin", _async_result(None))
    monkeypatch.setattr(oauth_service, "ensure_store_access", _async_result(None))
    monkeypatch.setattr(oauth_service, "ensure_store_channel_manager", _async_result(None))
    monkeypatch.setattr(oauth_service, "get_active_store", _async_result(SimpleNamespace(id=store_id)))
    monkeypatch.setattr(oauth_service, "find_channel_by_external_store", _async_result(channel))
    monkeypatch.setattr(oauth_service, "find_channel_by_store_platform", _async_result(channel))
    result = await oauth_service.complete_tiktok_oauth(  # type: ignore[arg-type]
        session, "valid-state", "unit-test-auth-code", None, oauth_settings(), FakeOAuthClient()
    )
    assert result.store_id == store_id and channel.status == "connected"
    assert not any(isinstance(value, Store) for value in session.added)


@pytest.mark.asyncio
async def test_direct_add_rejects_existing_connected_shop(monkeypatch: pytest.MonkeyPatch) -> None:
    """添加按钮不能重绑已连接的店铺，必须使用对应行的重新添加。"""
    user_id = uuid.uuid4()
    existing = SimpleNamespace(store_id=uuid.uuid4(), status="connected")
    session = FakeSession()
    monkeypatch.setattr(
        oauth_service,
        "consume_tiktok_oauth_state",
        _async_result(
            {
                "user_id": str(user_id),
                "return_to": "/settings/stores",
            }
        ),
    )
    monkeypatch.setattr(oauth_service, "find_user_by_id", _async_result(SimpleNamespace(id=user_id, status="active")))
    monkeypatch.setattr(oauth_service, "ensure_system_store_admin", _async_result(None))
    monkeypatch.setattr(oauth_service, "find_channel_by_external_store", _async_result(existing))

    with pytest.raises(AppError) as error:
        await oauth_service.complete_tiktok_oauth(  # type: ignore[arg-type]
            session, "valid-state", "unit-test-auth-code", None, oauth_settings(), FakeOAuthClient()
        )
    assert error.value.code == ErrorCode.RESOURCE_CONFLICT
    assert not any(isinstance(value, Store) for value in session.added)


def test_store_list_views_expose_shop_fields_without_credentials() -> None:
    """店铺列表仅返回站点和授权时间等低敏摘要，不泄露 Token 或密文。"""
    now = datetime.now(UTC)
    store = Store(
        id=uuid.uuid4(),
        name="Shop One",
        code="shop-one",
        status="active",
        timezone="UTC",
        currency="GBP",
        metadata_json={"alias": "客服店"},
        created_at=now,
    )
    channel = ChannelAccount(
        id=uuid.uuid4(),
        store_id=store.id,
        platform="tiktok",
        external_store_id="external-shop-1",
        display_name="Shop One",
        access_token_ref="encrypted:v1:secret",
        status="connected",
        scopes=[],
        last_sync_at=None,
        created_at=now,
        metadata_json={"region": "GB", "refresh_token_expires_at": now.isoformat()},
    )
    store_view = StoreView.model_validate(store)
    channel_view = ChannelView.model_validate(channel)
    assert store_view.alias == "客服店" and store_view.id == store.id
    assert channel_view.site == "GB" and channel_view.authorization_expires_at == now
    assert channel_view.last_authorized_at == now
    assert "access_token_ref" not in channel_view.model_dump()

    # 平台到期通知可能早于 Refresh Token 到期；列表必须显示更早的真实期限。
    earlier = now - timedelta(days=1)
    channel.metadata_json = {
        **channel.metadata_json,
        "authorization_expires_at": earlier.isoformat(),
        "oauth_status": "reauthorization_required",
    }
    warned = ChannelView.model_validate(channel)
    assert warned.authorization_expires_at == earlier
    assert warned.authorization_status == "reauthorization_required"


@pytest.mark.asyncio
async def test_store_admin_check_is_bound_to_target_store() -> None:
    """其他店铺的管理员身份不能用于修改目标店铺的别名或撤销授权。"""
    store_id, user_id = uuid.uuid4(), uuid.uuid4()

    class RoleSession:
        statement = None

        async def scalar(self, statement: object) -> None:
            self.statement = statement
            return None

    session = RoleSession()
    with pytest.raises(AppError) as denied:
        await stores_service.ensure_store_admin(  # type: ignore[arg-type]
            session, SimpleNamespace(id=user_id), store_id
        )
    assert denied.value.code == ErrorCode.PERMISSION_DENIED
    sql = str(session.statement.compile(compile_kwargs={"literal_binds": True}))
    assert store_id.hex in sql
    assert "user_roles.store_id IS NULL" in sql


@pytest.mark.asyncio
async def test_oauth_channel_manager_permission_is_bound_to_target_store() -> None:
    """其他店铺的渠道权限不能启动或完成目标店铺的重新授权。"""
    store_id, user_id = uuid.uuid4(), uuid.uuid4()

    class RoleSession:
        statement = None

        async def scalar(self, statement: object) -> None:
            self.statement = statement
            return None

    session = RoleSession()
    with pytest.raises(AppError) as denied:
        await oauth_service.ensure_store_channel_manager(  # type: ignore[arg-type]
            session, SimpleNamespace(id=user_id), store_id
        )
    assert denied.value.code == ErrorCode.PERMISSION_DENIED
    sql = str(session.statement.compile(compile_kwargs={"literal_binds": True}))
    assert store_id.hex in sql
    assert "user_roles.store_id IS NULL" in sql
    assert "settings.channels" in sql


@pytest.mark.asyncio
async def test_alias_edit_changes_only_display_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    """编辑别名不更改店铺编码、平台 ID 或租户授权。"""
    store_id, user_id = uuid.uuid4(), uuid.uuid4()
    store = Store(
        id=store_id,
        name="Shop One",
        code="shop-one",
        status="active",
        timezone="UTC",
        currency="GBP",
        metadata_json={"alias": "旧别名"},
    )

    class AliasSession(FakeSession):
        async def refresh(self, _: object) -> None:
            return None

    session = AliasSession()
    monkeypatch.setattr(stores_service, "ensure_store_access", _async_result(None))
    monkeypatch.setattr(stores_service, "ensure_store_admin", _async_result(None))
    monkeypatch.setattr(stores_service, "get_active_store", _async_result(store))
    updated = await stores_service.update_store_alias(  # type: ignore[arg-type]
        session, SimpleNamespace(id=user_id), store_id, StoreAliasUpdate(alias=" 新别名 ")
    )
    assert updated.alias == "新别名"
    assert updated.code == "shop-one"
    assert any(isinstance(value, AuditLog) and value.action == "store.alias.update" for value in session.added)
    assert session.commits == 1


@pytest.mark.asyncio
async def test_complete_oauth_rejects_replay_and_unavailable_initiator(monkeypatch: pytest.MonkeyPatch) -> None:
    """缺失/重复 state 或不可用的发起用户都不能交换 Token。"""
    session = FakeSession()
    monkeypatch.setattr(oauth_service, "consume_tiktok_oauth_state", _async_result(None))
    with pytest.raises(AppError) as missing:
        await oauth_service.complete_tiktok_oauth(  # type: ignore[arg-type]
            session,
            "used-state",
            "code",
            None,
            oauth_settings(),
        )
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
        await oauth_service.complete_tiktok_oauth(  # type: ignore[arg-type]
            session,
            "valid-state",
            "code",
            None,
            oauth_settings(),
        )
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
    monkeypatch.setattr(oauth_service, "ensure_store_channel_manager", _async_result(None))
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
async def test_legacy_shop_refresh_stays_connected_when_seller_adds_second_shop() -> None:
    """平台多返回一家店时，旧单店只核对自身 ID，不能误标过期。"""
    store_id = uuid.uuid4()
    channel = ChannelAccount(
        id=uuid.uuid4(),
        store_id=store_id,
        platform="tiktok",
        external_store_id="external-shop-1",
        display_name="Existing TKW Group",
        access_token_ref="encrypted:v1:old",
        refresh_token_ref=encrypt_credential(
            "refresh-token-unit-test-value",
            "unit-test-encryption-key-with-at-least-32-characters",
            f"tiktok:{store_id}:external-shop-1:refresh",
        ),
        metadata_json={"open_id_hash": hashlib.sha256(b"seller-open-id").hexdigest()},
    )
    await oauth_service.refresh_tiktok_channel_token(
        FakeSession(),  # type: ignore[arg-type]
        channel,
        oauth_settings(),
        FakeOAuthClient(shop_count=2),  # type: ignore[arg-type]
    )
    assert channel.status == "connected"
    assert channel.metadata_json["shop_cipher"] == "shop-cipher"


@pytest.mark.asyncio
async def test_shared_seller_refresh_rotates_once_and_expires_only_removed_shop() -> None:
    """同卖家多店只刷新一次；平台移除其中一店时其他店仍可连接。"""
    settings = oauth_settings()
    key = settings.tiktok_credential_encryption_key
    assert key is not None
    grant_id = uuid.uuid4()
    grant = store_models.TikTokSellerAuthorization(
        id=grant_id,
        app_key=settings.tiktok_app_key,
        open_id_hash=hashlib.sha256(b"seller-open-id").hexdigest(),
        access_token_ref="encrypted:v1:old-access",
        refresh_token_ref=encrypt_credential(
            "refresh-token-unit-test-value", key.get_secret_value(), f"tiktok:seller:{grant_id}:refresh"
        ),
        access_expires_at=datetime.now(UTC) + timedelta(minutes=1),
        refresh_expires_at=datetime.now(UTC) + timedelta(days=1),
        authorized_shop_ids=["external-shop-1", "external-shop-2"],
        status="connected",
    )
    channels = [
        ChannelAccount(
            id=uuid.uuid4(),
            store_id=uuid.uuid4(),
            platform="tiktok",
            external_store_id=f"external-shop-{index}",
            display_name=f"Shop {index}",
            access_token_ref=f"shared://{grant_id}",
            seller_authorization_id=grant_id,
            seller_authorization=grant,
            status="connected",
            metadata_json={"open_id_hash": grant.open_id_hash},
        )
        for index in (1, 2)
    ]

    class RefreshSession(FakeSession):
        async def scalars(self, _statement: object) -> Any:
            return SimpleNamespace(all=lambda: channels)

    await oauth_service.refresh_tiktok_seller_authorization(  # type: ignore[attr-defined,arg-type]
        RefreshSession(), grant, settings, FakeOAuthClient(shop_count=1)
    )
    assert grant.access_token_ref.startswith("encrypted:v1:")
    assert channels[0].status == "connected"
    assert channels[1].status == "expired"
    assert grant.authorized_shop_ids == ["external-shop-1"]
    assert grant.next_refresh_at > datetime.now(UTC) + timedelta(minutes=5)


@pytest.mark.asyncio
async def test_reauthorize_one_shared_shop_updates_seller_grant_for_all_siblings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """对多店卖家的目标店重新授权时，更新共享凭证且不误绑定其他店。"""
    user_id, store_id, grant_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    grant = store_models.TikTokSellerAuthorization(
        id=grant_id,
        app_key=oauth_settings().tiktok_app_key,
        open_id_hash=hashlib.sha256(b"seller-open-id").hexdigest(),
        access_token_ref="encrypted:v1:old",
        refresh_token_ref="encrypted:v1:old",
        access_expires_at=datetime.now(UTC) + timedelta(minutes=1),
        refresh_expires_at=datetime.now(UTC) + timedelta(days=1),
        authorized_shop_ids=["external-shop-1", "external-shop-2"],
        status="connected",
    )
    channel = ChannelAccount(
        id=uuid.uuid4(),
        store_id=store_id,
        platform="tiktok",
        external_store_id="external-shop-1",
        display_name="Shop One",
        access_token_ref=f"shared://{grant_id}",
        seller_authorization_id=grant_id,
        seller_authorization=grant,
        status="connected",
        metadata_json={"open_id_hash": grant.open_id_hash},
    )
    expired_sibling = ChannelAccount(
        id=uuid.uuid4(),
        store_id=uuid.uuid4(),
        platform="tiktok",
        external_store_id="external-shop-2",
        display_name="Expired sibling",
        access_token_ref=f"shared://{grant_id}",
        seller_authorization_id=grant_id,
        seller_authorization=grant,
        status="expired",
        metadata_json={"open_id_hash": grant.open_id_hash},
    )

    class ReauthSession(FakeSession):
        async def get(self, model: object, _id: uuid.UUID, **_kwargs: object) -> Any:
            return grant if model is store_models.TikTokSellerAuthorization and _id == grant_id else None

        async def scalars(self, _statement: object) -> Any:
            return SimpleNamespace(all=lambda: [channel, expired_sibling])

    session = ReauthSession()
    monkeypatch.setattr(
        oauth_service,
        "consume_tiktok_oauth_state",
        _async_result(
            {
                "user_id": str(user_id),
                "store_id": str(store_id),
                "return_to": "/settings/stores",
            }
        ),
    )
    monkeypatch.setattr(oauth_service, "find_user_by_id", _async_result(SimpleNamespace(id=user_id, status="active")))
    monkeypatch.setattr(oauth_service, "ensure_store_access", _async_result(None))
    monkeypatch.setattr(oauth_service, "ensure_store_channel_manager", _async_result(None))
    monkeypatch.setattr(oauth_service, "get_active_store", _async_result(SimpleNamespace(id=store_id)))
    monkeypatch.setattr(oauth_service, "find_channel_by_external_store", _async_result(channel))
    monkeypatch.setattr(oauth_service, "find_channel_by_store_platform", _async_result(channel))

    result = await oauth_service.complete_tiktok_oauth(  # type: ignore[arg-type]
        session,
        "valid-state",
        "unit-test-auth-code",
        None,
        oauth_settings(),
        FakeOAuthClient(shop_count=2),
    )
    assert result.status == "connected" and result.store_id == store_id
    assert channel.access_token_ref == f"shared://{grant_id}"
    assert grant.access_token_ref.startswith("encrypted:v1:")
    assert grant.authorized_shop_ids == ["external-shop-1", "external-shop-2"]
    assert expired_sibling.status == "expired"


@pytest.mark.asyncio
async def test_shop_admin_cannot_rotate_seller_grant_for_unmanaged_sibling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A 店管理员重授不得改动无权管理的 B 店及共享卖家 Token。"""
    store_a, store_b, grant_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    grant = store_models.TikTokSellerAuthorization(
        id=grant_id,
        app_key=oauth_settings().tiktok_app_key,
        open_id_hash=hashlib.sha256(b"seller-open-id").hexdigest(),
        access_token_ref="encrypted:v1:old",
        refresh_token_ref="encrypted:v1:old",
        access_expires_at=datetime.now(UTC) + timedelta(minutes=1),
        refresh_expires_at=datetime.now(UTC) + timedelta(days=1),
        authorized_shop_ids=["external-shop-1", "external-shop-2"],
        status="connected",
    )
    channels = [
        ChannelAccount(
            id=uuid.uuid4(),
            store_id=store_id,
            platform="tiktok",
            external_store_id=f"external-shop-{index}",
            display_name=f"Shop {index}",
            access_token_ref=f"shared://{grant_id}",
            seller_authorization_id=grant_id,
            seller_authorization=grant,
            status="connected",
            metadata_json={"open_id_hash": grant.open_id_hash},
        )
        for index, store_id in ((1, store_a), (2, store_b))
    ]

    class ReauthSession(FakeSession):
        async def get(self, _model: object, _id: uuid.UUID, **_kwargs: object) -> Any:
            return grant

        async def scalars(self, _statement: object) -> Any:
            return SimpleNamespace(all=lambda: channels)

    async def ensure_manager(_session: object, _user: object, store_id: uuid.UUID) -> None:
        if store_id == store_b:
            raise AppError(ErrorCode.PERMISSION_DENIED, "没有管理该店铺渠道的权限", 403)

    monkeypatch.setattr(oauth_service, "ensure_store_access", _async_result(None))
    monkeypatch.setattr(oauth_service, "ensure_store_channel_manager", ensure_manager)
    session = ReauthSession()
    with pytest.raises(AppError) as denied:
        await oauth_service._reauthorize_shared_seller(  # type: ignore[arg-type]
            session,
            channels[0],
            token_data(),
            (await FakeOAuthClient(shop_count=2).get_authorized_shops("access-token-unit-test-value"))[0],
            SimpleNamespace(id=uuid.uuid4()),
            None,
            "/settings/stores",
            oauth_settings(),
            commit=False,
        )
    assert denied.value.code == ErrorCode.PERMISSION_DENIED
    assert grant.access_token_ref == "encrypted:v1:old"
    assert [channel.status for channel in channels] == ["connected", "connected"]


@pytest.mark.asyncio
async def test_readding_removed_shop_joins_existing_shared_seller_grant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """同卖家另一店仍在线时，已删除店铺重新添加须加入共享授权。"""
    user_id, store_id, grant_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    grant = store_models.TikTokSellerAuthorization(
        id=grant_id,
        app_key=oauth_settings().tiktok_app_key,
        open_id_hash=hashlib.sha256(b"seller-open-id").hexdigest(),
        access_token_ref="encrypted:v1:old",
        refresh_token_ref="encrypted:v1:old",
        access_expires_at=datetime.now(UTC) + timedelta(minutes=1),
        refresh_expires_at=datetime.now(UTC) + timedelta(days=1),
        authorized_shop_ids=["external-shop-1"],
        status="connected",
    )
    sibling = ChannelAccount(
        id=uuid.uuid4(),
        store_id=uuid.uuid4(),
        platform="tiktok",
        external_store_id="external-shop-1",
        display_name="Shop One",
        access_token_ref=f"shared://{grant_id}",
        seller_authorization_id=grant_id,
        seller_authorization=grant,
        status="connected",
        metadata_json={"open_id_hash": grant.open_id_hash},
    )
    removed = ChannelAccount(
        id=uuid.uuid4(),
        store_id=store_id,
        platform="tiktok",
        external_store_id="external-shop-2",
        display_name="Shop Two",
        access_token_ref="revoked://old",
        status="disconnected",
        metadata_json={"oauth_status": "revoked"},
    )

    class ReaddSession(FakeSession):
        async def scalar(self, _statement: object) -> store_models.TikTokSellerAuthorization:
            return grant

        async def scalars(self, _statement: object) -> Any:
            return SimpleNamespace(all=lambda: [sibling])

    session = ReaddSession()
    monkeypatch.setattr(
        oauth_service,
        "consume_tiktok_oauth_state",
        _async_result(
            {
                "user_id": str(user_id),
                "store_id": str(store_id),
                "return_to": "/settings/stores",
            }
        ),
    )
    monkeypatch.setattr(oauth_service, "find_user_by_id", _async_result(SimpleNamespace(id=user_id, status="active")))
    monkeypatch.setattr(oauth_service, "ensure_store_access", _async_result(None))
    monkeypatch.setattr(oauth_service, "ensure_store_channel_manager", _async_result(None))
    monkeypatch.setattr(oauth_service, "get_active_store", _async_result(SimpleNamespace(id=store_id)))
    monkeypatch.setattr(oauth_service, "find_channel_by_external_store", _async_result(removed))
    monkeypatch.setattr(oauth_service, "find_channel_by_store_platform", _async_result(removed))
    result = await oauth_service.complete_tiktok_oauth(  # type: ignore[arg-type]
        session,
        "valid-state",
        "unit-test-auth-code",
        None,
        oauth_settings(),
        FakeOAuthClient(shop_count=2),
    )
    assert result.status == "connected"
    assert removed.store_id == store_id and removed.seller_authorization_id == grant_id
    assert removed.access_token_ref == f"shared://{grant_id}"
    assert sibling.status == "connected"


@pytest.mark.asyncio
async def test_existing_single_shop_reauthorization_preserves_store_id_when_seller_has_multiple_shops(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """现有 TKW 单店在卖家变为多店后重授，保留 CRM 店铺 ID 并建立共享授权。"""
    user_id, store_id = uuid.uuid4(), uuid.uuid4()
    channel = ChannelAccount(
        id=uuid.uuid4(),
        store_id=store_id,
        platform="tiktok",
        external_store_id="external-shop-1",
        display_name="Existing TKW Group",
        access_token_ref="encrypted:v1:old",
        status="connected",
        metadata_json={"open_id_hash": hashlib.sha256(b"seller-open-id").hexdigest()},
    )

    class LegacySession(FakeSession):
        async def scalar(self, _statement: object) -> None:
            return None

        async def scalars(self, _statement: object) -> Any:
            return SimpleNamespace(all=lambda: [channel])

    session = LegacySession()
    monkeypatch.setattr(
        oauth_service,
        "consume_tiktok_oauth_state",
        _async_result(
            {
                "user_id": str(user_id),
                "store_id": str(store_id),
                "return_to": "/settings/stores",
            }
        ),
    )
    monkeypatch.setattr(oauth_service, "find_user_by_id", _async_result(SimpleNamespace(id=user_id, status="active")))
    monkeypatch.setattr(oauth_service, "ensure_store_access", _async_result(None))
    monkeypatch.setattr(oauth_service, "ensure_store_channel_manager", _async_result(None))
    monkeypatch.setattr(oauth_service, "get_active_store", _async_result(SimpleNamespace(id=store_id)))
    monkeypatch.setattr(oauth_service, "find_channel_by_external_store", _async_result(channel))
    monkeypatch.setattr(oauth_service, "find_channel_by_store_platform", _async_result(channel))
    result = await oauth_service.complete_tiktok_oauth(  # type: ignore[arg-type]
        session,
        "valid-state",
        "unit-test-auth-code",
        None,
        oauth_settings(),
        FakeOAuthClient(shop_count=2),
    )
    grants = [item for item in session.added if isinstance(item, store_models.TikTokSellerAuthorization)]
    assert result.status == "connected" and result.store_id == store_id
    assert len(grants) == 1 and channel.seller_authorization_id == grants[0].id
    assert channel.access_token_ref == f"shared://{grants[0].id}"
    assert not any(isinstance(item, Store) for item in session.added)
    assert any(isinstance(item, AuditLog) and item.action == "channel.authorization_migrated" for item in session.added)


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
    monkeypatch.setattr(oauth_service, "claim_tiktok_seller_for_refresh", _async_result(None))
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
    monkeypatch.setattr(stores_service, "ensure_store_admin", _async_result(None))

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


@pytest.mark.asyncio
async def test_revoking_last_shared_shop_destroys_seller_credential(monkeypatch: pytest.MonkeyPatch) -> None:
    """最后一家共享店铺删除后，不在系统保留仍可用的卖家 Token。"""
    grant_id = uuid.uuid4()
    grant = store_models.TikTokSellerAuthorization(id=grant_id, app_key="unit-test-app-key")
    channel = ChannelAccount(
        id=uuid.uuid4(),
        store_id=uuid.uuid4(),
        platform="tiktok",
        external_store_id="external-shop-1",
        display_name="Shop One",
        access_token_ref=f"shared://{grant_id}",
        seller_authorization_id=grant_id,
        seller_authorization=grant,
        status="connected",
        metadata_json={"shop_cipher": "cipher"},
    )

    class RevokeSession(FakeChannelSession):
        async def get(self, model: object, item_id: uuid.UUID, **_kwargs: object) -> Any:
            if model is store_models.TikTokSellerAuthorization and item_id == grant_id:
                return grant
            return channel if model is ChannelAccount and item_id == channel.id else None

        async def scalar(self, _statement: object) -> None:
            return None

    session = RevokeSession(channel)
    monkeypatch.setattr(stores_service, "ensure_store_access", _async_result(None))
    monkeypatch.setattr(stores_service, "ensure_store_admin", _async_result(None))
    await stores_service.delete_channel(  # type: ignore[arg-type]
        session, SimpleNamespace(id=uuid.uuid4()), channel.id
    )
    assert grant in session.deleted
    assert channel.seller_authorization_id is None
    assert channel.status == "disconnected"


def _async_result(value: Any) -> Any:
    """返回忽略入参并产生固定结果的异步函数。"""

    async def result(*_args: Any, **_kwargs: Any) -> Any:
        return value

    return result
