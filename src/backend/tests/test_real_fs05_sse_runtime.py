"""REAL-FS-05 DeepSeek 配置和 SSE 生产运行面测试。"""

import asyncio
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

from app.agent.workflow import AgentWorkflowExecutionError
from app.chat import router as chat_router
from app.chat.router import _agent_error_payload
from app.chat.schemas import ChatQueryRequest
from app.shared.config.settings import Settings
from app.shared.database import redis as redis_module
from app.shared.health import check_llm_provider_configuration

SOURCE_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    ("error_code", "public_code", "retryable"),
    [
        ("LLM_RATE_LIMITED", 42901, True),
        ("LLM_TIMEOUT", 50003, True),
        ("LLM_CONNECTION_ERROR", 50003, True),
        ("LLM_AUTHENTICATION_ERROR", 50003, False),
        ("EMBEDDING_RATE_LIMITED", 42901, True),
        ("RERANK_TIMEOUT", 50003, True),
        ("RERANK_CONFIGURATION_ERROR", 50003, False),
        ("AGENT_WORKFLOW_ERROR", 50001, False),
    ],
)
def test_agent_errors_map_to_stable_low_sensitivity_sse_errors(
    error_code: str,
    public_code: int,
    retryable: bool,
) -> None:
    payload = _agent_error_payload(error_code)

    assert payload["code"] == public_code
    assert payload["retryable"] is retryable
    assert error_code not in str(payload)


def test_sse_runtime_configuration_is_bounded_and_heartbeat_precedes_timeout() -> None:
    settings = Settings(
        _env_file=None,
        CHAT_STREAM_TIMEOUT_SECONDS=180,
        CHAT_SSE_HEARTBEAT_SECONDS=15,
    )

    assert settings.chat_stream_timeout_seconds == 180
    assert settings.chat_sse_heartbeat_seconds == 15

    with pytest.raises(ValidationError, match="心跳间隔必须小于"):
        Settings(
            _env_file=None,
            CHAT_STREAM_TIMEOUT_SECONDS=10,
            CHAT_SSE_HEARTBEAT_SECONDS=10,
        )


def test_llm_health_state_checks_configuration_without_exposing_key() -> None:
    secret = "test-deepseek-secret"
    configured = Settings(
        _env_file=None,
        LLM_ENABLED=True,
        LLM_PRIMARY_PROVIDER="deepseek",
        LLM_PRIMARY_MODEL="test-model",
        DEEPSEEK_API_KEY=secret,
    )
    missing_key = Settings(
        _env_file=None,
        LLM_ENABLED=True,
        LLM_PRIMARY_PROVIDER="deepseek",
        LLM_PRIMARY_MODEL="test-model",
    )

    assert check_llm_provider_configuration(configured) is True
    assert check_llm_provider_configuration(missing_key) is False
    assert secret not in repr(configured)


@pytest.mark.parametrize("api_key", ["", " ", "\t\n"])
def test_real_environment_rejects_blank_deepseek_key(api_key: str) -> None:
    """真实环境不得把只含空白的 SecretStr 当作已安全注入的密钥。"""
    with pytest.raises(ValidationError, match="DeepSeek"):
        Settings(
            _env_file=None,
            APP_ENV="integration",
            TIKTOK_OAUTH_REDIRECT_URI=("https://www.hophorsefit.com/v1/integrations/tiktok/oauth/callback"),
            LLM_ENABLED=True,
            LLM_PRIMARY_PROVIDER="deepseek",
            LLM_PRIMARY_MODEL="test-model",
            DEEPSEEK_API_KEY=api_key,
        )


@pytest.mark.parametrize("api_key", ["", " ", "\t\n"])
def test_llm_health_rejects_blank_deepseek_key(api_key: str) -> None:
    settings = Settings(
        _env_file=None,
        LLM_ENABLED=True,
        LLM_PRIMARY_PROVIDER="deepseek",
        LLM_PRIMARY_MODEL="test-model",
        DEEPSEEK_API_KEY=api_key,
    )

    assert check_llm_provider_configuration(settings) is False


def test_chat_stream_lease_outlives_maximum_stream_timeout() -> None:
    settings = Settings(
        _env_file=None,
        CHAT_STREAM_TIMEOUT_SECONDS=600,
        CHAT_SSE_HEARTBEAT_SECONDS=15,
    )

    assert settings.chat_stream_lease_seconds == 660


def test_sse_load_profile_only_allows_integration_or_staging() -> None:
    with pytest.raises(ValidationError, match="integration/staging"):
        Settings(
            _env_file=None,
            APP_ENV="production",
            TIKTOK_OAUTH_REDIRECT_URI=("https://www.hophorsefit.com/v1/integrations/tiktok/oauth/callback"),
            SSE_LOAD_TEST_ENABLED=True,
            CHAT_QUERY_LIMIT=60,
        )


def test_sse_load_profile_requires_fifty_request_ip_capacity() -> None:
    with pytest.raises(ValidationError, match="不得低于 50"):
        Settings(
            _env_file=None,
            APP_ENV="integration",
            TIKTOK_OAUTH_REDIRECT_URI=("https://www.hophorsefit.com/v1/integrations/tiktok/oauth/callback"),
            SSE_LOAD_TEST_ENABLED=True,
            CHAT_QUERY_LIMIT=49,
        )

    settings = Settings(
        _env_file=None,
        APP_ENV="staging",
        TIKTOK_OAUTH_REDIRECT_URI=("https://staging.hophorsefit.com/v1/integrations/tiktok/oauth/callback"),
        # staging 压测仍须满足公网基础安全；这些虚构凭据不启用任何真实平台能力。
        AUTH_COOKIE_SECURE=True,
        ALLOW_MOCK_PLATFORM_ADAPTERS=False,
        JWT_SECRET_KEY="unit-test-jwt-secret-with-at-least-32-characters",
        MINIO_SECRET_KEY="unit-test-minio-secret",
        DATABASE_URL="postgresql+asyncpg://crm:unit-test-password@localhost:5432/crm",
        PUBLIC_BASE_URL="https://staging.hophorsefit.com",
        CORS_ORIGINS="https://staging.hophorsefit.com",
        TIKTOK_EGRESS_IP="203.0.113.10",
        SSE_LOAD_TEST_ENABLED=True,
        CHAT_QUERY_LIMIT=60,
    )
    assert settings.sse_load_test_enabled is True


@pytest.mark.asyncio
async def test_chat_stream_lease_is_unique_and_uses_derived_ttl(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[object, ...]] = []

    async def evaluate(*args: object) -> int:
        calls.append(args)
        return 1

    monkeypatch.setattr(redis_module, "redis_client", SimpleNamespace(eval=evaluate))
    user_id = uuid.uuid4()

    lease_token = await redis_module.acquire_chat_stream(user_id, limit=2, lease_seconds=660)
    assert lease_token is not None
    await redis_module.release_chat_stream(user_id, lease_token)

    assert calls[0][1:] == (1, f"chat:concurrency:v2:{user_id}", lease_token, "660000", "2")
    assert calls[1][1:] == (1, f"chat:concurrency:v2:{user_id}", lease_token)


@pytest.mark.asyncio
async def test_chat_stream_capacity_rejection_returns_no_lease(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def reject(*_args: object) -> int:
        return 0

    monkeypatch.setattr(redis_module, "redis_client", SimpleNamespace(eval=reject))

    assert await redis_module.acquire_chat_stream(uuid.uuid4(), limit=2, lease_seconds=240) is None


def test_real_environment_deepseek_rejects_insecure_base_url() -> None:
    """集成、预发布和生产都可能承载真实数据，DeepSeek 地址必须使用 HTTPS。"""
    with pytest.raises(ValidationError, match="DEEPSEEK_BASE_URL"):
        Settings(
            _env_file=None,
            APP_ENV="staging",
            TIKTOK_OAUTH_REDIRECT_URI=("https://staging.hophorsefit.com/v1/integrations/tiktok/oauth/callback"),
            LLM_ENABLED=True,
            LLM_PRIMARY_PROVIDER="deepseek",
            LLM_PRIMARY_MODEL="test-model",
            DEEPSEEK_API_KEY="test-deepseek-secret",
            DEEPSEEK_BASE_URL="http://deepseek.invalid",
        )


def test_deepseek_sse_overlay_only_enables_authenticated_backend_drafts() -> None:
    overlay = (SOURCE_ROOT / "compose" / "docker-compose.deepseek-sse.yml").read_text(encoding="utf-8")

    assert "LLM_ENABLED: ${LLM_ENABLED:-false}" in overlay
    assert overlay.count('AUTO_REPLY_ENABLED: "false"') == 3
    assert overlay.count('AI_MARKETING_ENABLED: "false"') == 3
    assert overlay.count('AI_TRANSLATION_ENABLED: "false"') == 3
    assert "CHAT_STREAM_TIMEOUT_SECONDS" in overlay
    assert "CHAT_SSE_HEARTBEAT_SECONDS" in overlay


def test_sse_load_overlay_raises_only_backend_ip_rate_capacity() -> None:
    overlay = (SOURCE_ROOT / "compose" / "docker-compose.sse-load-test.yml").read_text(encoding="utf-8")

    assert "SSE_LOAD_TEST_APP_ENV:-integration" in overlay
    assert "SSE_LOAD_TEST_QUERY_LIMIT:-60" in overlay
    assert "SSE_LOAD_TEST_QUERY_WINDOW_SECONDS:-60" in overlay
    assert 'SSE_LOAD_TEST_ENABLED: "true"' in overlay
    assert overlay.count("backend:") == 1


@pytest.mark.asyncio
async def test_stream_timeout_cancels_workflow_and_ends_with_error_done(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = SimpleNamespace(id=uuid.uuid4())
    cancelled = asyncio.Event()
    released: list[uuid.UUID] = []

    async def allow_limits(*_args: object) -> None:
        return None

    async def acquire(*_args: object) -> str:
        return "test-lease"

    async def release(user_id: uuid.UUID, lease_token: str) -> None:
        assert lease_token == "test-lease"
        released.append(user_id)

    async def never_finishes(*_args: object) -> Any:
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    async def connected() -> bool:
        return False

    monkeypatch.setattr(chat_router, "_enforce_chat_limits", allow_limits)
    monkeypatch.setattr(chat_router, "acquire_chat_stream", acquire)
    monkeypatch.setattr(chat_router, "release_chat_stream", release)
    monkeypatch.setattr(chat_router, "suggest_for_user", never_finishes)
    monkeypatch.setattr(
        chat_router,
        "get_settings",
        lambda: SimpleNamespace(
            chat_user_concurrency=2,
            chat_stream_lease_seconds=1,
            chat_stream_timeout_seconds=0.03,
            chat_sse_heartbeat_seconds=0.01,
        ),
    )
    request = SimpleNamespace(
        state=SimpleNamespace(trace_id=str(uuid.uuid4())),
        client=SimpleNamespace(host="127.0.0.1"),
        is_disconnected=connected,
    )

    response = await chat_router.chat_query(
        ChatQueryRequest(session_id=uuid.uuid4()),
        request,  # type: ignore[arg-type]
        SimpleNamespace(),  # type: ignore[arg-type]
        user,  # type: ignore[arg-type]
    )
    body = "".join([chunk async for chunk in response.body_iterator])

    assert cancelled.is_set()
    assert ": keep-alive" in body
    assert '"code": 50003' in body
    assert '"reason": "timeout"' in body
    assert released == [user.id]


@pytest.mark.asyncio
async def test_provider_rate_limit_uses_error_done_without_raw_internal_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = SimpleNamespace(id=uuid.uuid4())
    run_id = uuid.uuid4()

    async def allow_limits(*_args: object) -> None:
        return None

    async def acquire(*_args: object) -> str:
        return "test-lease"

    async def release(*_args: object) -> None:
        return None

    async def rate_limited(*_args: object) -> Any:
        raise AgentWorkflowExecutionError(run_id, "LLM_RATE_LIMITED")

    async def connected() -> bool:
        return False

    monkeypatch.setattr(chat_router, "_enforce_chat_limits", allow_limits)
    monkeypatch.setattr(chat_router, "acquire_chat_stream", acquire)
    monkeypatch.setattr(chat_router, "release_chat_stream", release)
    monkeypatch.setattr(chat_router, "suggest_for_user", rate_limited)
    request = SimpleNamespace(
        state=SimpleNamespace(trace_id=str(uuid.uuid4())),
        client=SimpleNamespace(host="127.0.0.1"),
        is_disconnected=connected,
    )

    response = await chat_router.chat_query(
        ChatQueryRequest(session_id=uuid.uuid4()),
        request,  # type: ignore[arg-type]
        SimpleNamespace(),  # type: ignore[arg-type]
        user,  # type: ignore[arg-type]
    )
    body = "".join([chunk async for chunk in response.body_iterator])

    assert '"code": 42901' in body
    assert '"reason": "failed"' in body
    assert "LLM_RATE_LIMITED" not in body
