"""TikTok OAuth 快速回跳任务的安全与失败关闭行为。"""

import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest

import app.integrations.oauth_router as oauth_router
import app.integrations.oauth_service as oauth_service
from app.integrations.credential_crypto import encrypt_credential
from app.integrations.models import TikTokOAuthJob
from app.shared.config.settings import Settings
from app.shared.exceptions.errors import AppError, ErrorCode


class MemorySession:
    """仅承载任务对象，不连接真实数据库。"""

    def __init__(self) -> None:
        self.items: dict[uuid.UUID, object] = {}
        self.commits = 0

    async def get(self, _model: object, key: uuid.UUID) -> object | None:
        return self.items.get(key)

    def add(self, value: object) -> None:
        self.items[value.id] = value  # type: ignore[attr-defined]

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        return None

    @asynccontextmanager
    async def begin_nested(self):  # type: ignore[no-untyped-def]
        yield


class ClaimSession(MemorySession):
    """返回一个待处理任务。"""

    def __init__(self, job: TikTokOAuthJob) -> None:
        super().__init__()
        self.items[job.id] = job
        self.job = job
        self.calls = 0

    async def scalar(self, _: object) -> TikTokOAuthJob | None:
        self.calls += 1
        return self.job if self.calls == 1 else None


@pytest.mark.asyncio
async def test_callback_redirects_to_processing_without_waiting_for_platform(monkeypatch: pytest.MonkeyPatch) -> None:
    """公网 callback 只入队即跳回，不在请求中交换 Token。"""
    job_id = uuid.uuid4()

    async def queued(*_: object) -> SimpleNamespace:
        return SimpleNamespace(id=job_id, status="pending")

    monkeypatch.setattr(oauth_router, "queue_tiktok_oauth", queued, raising=False)
    response = await oauth_router.tiktok_oauth_callback(  # type: ignore[arg-type]
        MemorySession(), "unit-test-state-with-enough-length", "unit-test-code", None
    )

    assert response.status_code == 303
    parsed = urlparse(response.headers["location"])
    assert parsed.path == "/settings/channels"
    assert parse_qs(parsed.query) == {"oauth": ["tiktok"], "status": ["processing"], "job": [str(job_id)]}
    assert "unit-test-code" not in response.headers["location"]
    assert "unit-test-state" not in response.headers["location"]


@pytest.mark.asyncio
async def test_queue_is_one_time_encrypted_and_duplicate_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    """重复 callback 复用同一任务，不保存明文或二次交换 code。"""
    user_id, store_id = uuid.uuid4(), uuid.uuid4()
    payload = {"user_id": str(user_id), "store_id": str(store_id), "return_to": "/settings/channels"}
    session = MemorySession()

    async def state_payload(_: str) -> dict[str, str]:
        return payload

    async def user(_: object, __: uuid.UUID) -> SimpleNamespace:
        return SimpleNamespace(id=user_id, status="active")

    async def store_access(*_: object) -> None:
        return None

    async def store(*_: object) -> SimpleNamespace:
        return SimpleNamespace(id=store_id)

    monkeypatch.setattr(oauth_service, "peek_tiktok_oauth_state", state_payload, raising=False)
    monkeypatch.setattr(oauth_service, "find_user_by_id", user)
    monkeypatch.setattr(oauth_service, "ensure_store_access", store_access)
    monkeypatch.setattr(oauth_service, "get_active_store", store)
    settings = Settings(
        _env_file=None,
        TIKTOK_CREDENTIAL_ENCRYPTION_KEY="unit-test-encryption-key-with-at-least-32-characters",
    )
    # 此处仅验证任务排队行为；配置固定校验由现有 OAuth 用例覆盖。
    monkeypatch.setattr(oauth_service, "validate_oauth_runtime", lambda _: None)
    first = await oauth_service.queue_tiktok_oauth(  # type: ignore[attr-defined,arg-type]
        session, "unit-test-state-with-enough-length", "unit-test-code", settings=settings
    )
    second = await oauth_service.queue_tiktok_oauth(  # type: ignore[attr-defined,arg-type]
        session, "unit-test-state-with-enough-length", "different-code", settings=settings
    )

    assert first.id == second.id
    assert session.commits == 1
    assert len(session.items) == 1
    assert "unit-test-code" not in str(first.code_cipher)
    assert "unit-test-state" not in str(first.state_cipher)


@pytest.mark.asyncio
async def test_queue_rejects_unknown_state_before_database_write(monkeypatch: pytest.MonkeyPatch) -> None:
    """无效或过期的 state 不创建任务。"""

    async def missing(_: str) -> None:
        return None

    monkeypatch.setattr(oauth_service, "peek_tiktok_oauth_state", missing, raising=False)
    monkeypatch.setattr(oauth_service, "validate_oauth_runtime", lambda _: None)
    session = MemorySession()
    with pytest.raises(AppError) as error:
        await oauth_service.queue_tiktok_oauth(  # type: ignore[attr-defined,arg-type]
            session, "unknown-state-with-enough-length", "unit-test-code"
        )
    assert error.value.code == ErrorCode.VALIDATION_ERROR
    assert not session.items


@pytest.mark.asyncio
async def test_duplicate_rechecks_job_after_state_is_consumed(monkeypatch: pytest.MonkeyPatch) -> None:
    """并发回调初查未命中时，首请求提交并消费 state 后仍复用收据。"""
    job_id = uuid.uuid4()
    existing = SimpleNamespace(id=job_id, status="processing")

    class RacingSession(MemorySession):
        def __init__(self) -> None:
            super().__init__()
            self.reads = 0

        async def get(self, _model: object, _key: uuid.UUID) -> object | None:
            self.reads += 1
            return None if self.reads == 1 else existing

    async def missing(_: str) -> None:
        return None

    monkeypatch.setattr(oauth_service, "peek_tiktok_oauth_state", missing)
    monkeypatch.setattr(oauth_service, "validate_oauth_runtime", lambda _: None)
    session = RacingSession()
    result = await oauth_service.queue_tiktok_oauth(  # type: ignore[arg-type]
        session, "state-consumed-after-first-query", "code"
    )
    assert result is existing
    assert session.reads == 2
    assert session.commits == 0


@pytest.mark.asyncio
async def test_queue_rejects_oversize_encrypted_code_as_client_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Query 的字符长度上限不能允许多字节 code 撑爆密文列。"""
    user_id, store_id = uuid.uuid4(), uuid.uuid4()

    async def state_payload(_: str) -> dict[str, str]:
        return {"user_id": str(user_id), "store_id": str(store_id), "return_to": "/settings/channels"}

    async def user(_: object, __: uuid.UUID) -> SimpleNamespace:
        return SimpleNamespace(id=user_id, status="active")

    async def store(_: object, __: uuid.UUID) -> SimpleNamespace:
        return SimpleNamespace(id=store_id)

    async def access(*_: object) -> None:
        return None

    monkeypatch.setattr(oauth_service, "peek_tiktok_oauth_state", state_payload)
    monkeypatch.setattr(oauth_service, "find_user_by_id", user)
    monkeypatch.setattr(oauth_service, "get_active_store", store)
    monkeypatch.setattr(oauth_service, "ensure_store_access", access)
    monkeypatch.setattr(oauth_service, "validate_oauth_runtime", lambda _: None)
    session = MemorySession()
    settings = Settings(
        _env_file=None,
        TIKTOK_CREDENTIAL_ENCRYPTION_KEY="unit-test-encryption-key-with-at-least-32-characters",
    )
    with pytest.raises(AppError) as error:
        await oauth_service.queue_tiktok_oauth(  # type: ignore[arg-type]
            session, "unit-test-state-with-enough-length", "😀" * 500, settings
        )
    assert error.value.code == ErrorCode.VALIDATION_ERROR
    assert session.commits == 0


@pytest.mark.asyncio
async def test_job_status_is_limited_to_initiating_user_and_store(monkeypatch: pytest.MonkeyPatch) -> None:
    """即使知道任务 UUID，其他用户也不能推断授权进度。"""
    owner_id, store_id, job_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    session = MemorySession()
    session.items[job_id] = SimpleNamespace(id=job_id, user_id=owner_id, store_id=store_id, status="pending")

    async def store_access(*_: object) -> None:
        return None

    monkeypatch.setattr(oauth_service, "ensure_store_access", store_access)
    with pytest.raises(AppError) as error:
        await oauth_service.get_tiktok_oauth_job_status(  # type: ignore[attr-defined,arg-type]
            session, SimpleNamespace(id=uuid.uuid4()), job_id
        )
    assert error.value.code == ErrorCode.RESOURCE_NOT_FOUND

    async def denied_store_access(*_: object) -> None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "资源不存在", 404)

    monkeypatch.setattr(oauth_service, "ensure_store_access", denied_store_access)
    with pytest.raises(AppError) as store_error:
        await oauth_service.get_tiktok_oauth_job_status(  # type: ignore[arg-type]
            session, SimpleNamespace(id=owner_id), job_id
        )
    assert store_error.value.code == ErrorCode.RESOURCE_NOT_FOUND


def make_job() -> tuple[TikTokOAuthJob, Settings]:
    """生成与真实加密上下文一致的合成授权任务。"""
    job_id = uuid.uuid4()
    settings = Settings(
        _env_file=None,
        TIKTOK_CREDENTIAL_ENCRYPTION_KEY="unit-test-encryption-key-with-at-least-32-characters",
    )
    key = settings.tiktok_credential_encryption_key
    assert key is not None
    master = key.get_secret_value()
    job = TikTokOAuthJob(
        id=job_id,
        user_id=uuid.uuid4(),
        store_id=uuid.uuid4(),
        state_cipher=encrypt_credential("unit-test-state", master, f"tiktok:oauth-job:{job_id}:state"),
        code_cipher=encrypt_credential("unit-test-code", master, f"tiktok:oauth-job:{job_id}:code"),
        status="pending",
        created_at=datetime.now(UTC),
    )
    return job, settings


@pytest.mark.asyncio
async def test_worker_completes_once_and_scrubs_temporary_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """worker 才交换一次 Token，成功后清除暂存的 state/code 密文。"""
    job, settings = make_job()
    session = ClaimSession(job)
    calls = 0

    async def complete(
        _: object, state: str, code: str, __: object, ___: object, ____: object, *, commit: bool = True
    ) -> SimpleNamespace:
        nonlocal calls
        calls += 1
        assert state == "unit-test-state"
        assert code == "unit-test-code"
        assert commit is False
        return SimpleNamespace(status="connected")

    monkeypatch.setattr(oauth_service, "complete_tiktok_oauth", complete)
    assert await oauth_service.process_tiktok_oauth_job(session, settings) is True  # type: ignore[arg-type]
    assert calls == 1
    assert job.status == "connected"
    assert job.state_cipher is None and job.code_cipher is None
    assert session.commits == 1


@pytest.mark.asyncio
async def test_worker_failure_closes_job_without_replaying_code(monkeypatch: pytest.MonkeyPatch) -> None:
    """外部失败与中断均进入终态，不盲目重用一次性授权码。"""
    job, settings = make_job()
    session = ClaimSession(job)

    async def fail(*_: object, **__: object) -> None:
        raise AppError(ErrorCode.THIRD_PARTY_ERROR, "平台不可用", 502)

    monkeypatch.setattr(oauth_service, "complete_tiktok_oauth", fail)
    assert await oauth_service.process_tiktok_oauth_job(session, settings) is True  # type: ignore[arg-type]
    assert job.status == "failed"
    assert job.error_code == ErrorCode.THIRD_PARTY_ERROR.value
    assert job.state_cipher is None and job.code_cipher is None
