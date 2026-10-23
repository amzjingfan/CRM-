"""隔离 PostgreSQL 上验证 OAuth 快速回跳任务的唯一性与 worker 流转。"""

import asyncio
import os
import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.integrations.oauth_service as oauth_service
from app.audit.models import AuditLog
from app.integrations.models import TikTokOAuthJob
from app.shared.config.settings import Settings
from app.shared.database.base import Role, User, user_roles
from app.shared.exceptions.errors import AppError, ErrorCode
from app.stores.models import ChannelAccount, Store

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="未提供隔离的 PostgreSQL 测试数据库")


@pytest.mark.asyncio
async def test_oauth_job_is_encrypted_deduplicated_and_completed(monkeypatch: pytest.MonkeyPatch) -> None:
    """真实约束与事务中，重复 callback 只生成一个任务，worker 清除临时密文。"""
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    user_id, store_id = uuid.uuid4(), uuid.uuid4()
    settings = Settings(
        _env_file=None,
        TIKTOK_CREDENTIAL_ENCRYPTION_KEY="unit-test-encryption-key-with-at-least-32-characters",
    )

    async def peek(_: str) -> dict[str, str]:
        return {"user_id": str(user_id), "store_id": str(store_id), "return_to": "/settings/channels"}

    async def store(*_: object) -> SimpleNamespace:
        return SimpleNamespace(id=store_id)

    async def complete(
        _: object, state: str, code: str, __: object, ___: object, ____: object, *, commit: bool = True
    ) -> SimpleNamespace:
        assert state == "unit-test-state-with-enough-length"
        assert code == "unit-test-code"
        assert commit is False
        return SimpleNamespace(status="connected")

    monkeypatch.setattr(oauth_service, "peek_tiktok_oauth_state", peek)
    monkeypatch.setattr(oauth_service, "get_active_store", store)
    monkeypatch.setattr(oauth_service, "complete_tiktok_oauth", complete)
    monkeypatch.setattr(oauth_service, "validate_oauth_runtime", lambda _: None)
    try:
        async with sessions() as session:
            session.add(
                User(id=user_id, email=f"oauth-{uuid.uuid4().hex}@example.invalid", password_hash="unused", name="Test")
            )
            session.add(Store(id=store_id, name="OAuth Test", code=f"oauth-job-{uuid.uuid4().hex}"))
            admin_role_id = await session.scalar(select(Role.id).where(Role.code == "admin"))
            assert admin_role_id is not None
            await session.flush()
            await session.execute(user_roles.insert().values(user_id=user_id, role_id=admin_role_id, store_id=store_id))
            await session.commit()

            first = await oauth_service.queue_tiktok_oauth(
                session, "unit-test-state-with-enough-length", "unit-test-code", settings
            )
            second = await oauth_service.queue_tiktok_oauth(
                session, "unit-test-state-with-enough-length", "different-code", settings
            )
            assert first.id == second.id
            assert first.status == "pending"
            assert first.state_cipher and "unit-test-state" not in first.state_cipher
            assert first.code_cipher and "unit-test-code" not in first.code_cipher
            assert await oauth_service.process_tiktok_oauth_job(session, settings) is True
            completed = await session.get(TikTokOAuthJob, first.id)
            assert completed is not None and completed.status == "connected"
            assert completed.state_cipher is None and completed.code_cipher is None
    finally:
        async with sessions() as session:
            await session.execute(delete(User).where(User.id == user_id))
            await session.execute(delete(Store).where(Store.id == store_id))
            await session.commit()
        await engine.dispose()


@pytest.mark.asyncio
async def test_oauth_job_lock_fences_parallel_worker_and_crash_rolls_back_channel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """双 worker 不重复兑换；崩溃不能留下已连接渠道和未完成任务。"""
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    user_id, store_id = uuid.uuid4(), uuid.uuid4()
    state = "parallel-oauth-state-with-enough-length"
    settings = Settings(
        _env_file=None,
        TIKTOK_CREDENTIAL_ENCRYPTION_KEY="unit-test-encryption-key-with-at-least-32-characters",
    )

    async def peek(_: str) -> dict[str, str]:
        return {"user_id": str(user_id), "store_id": str(store_id), "return_to": "/settings/channels"}

    async def store(*_: object) -> SimpleNamespace:
        return SimpleNamespace(id=store_id)

    monkeypatch.setattr(oauth_service, "peek_tiktok_oauth_state", peek)
    monkeypatch.setattr(oauth_service, "get_active_store", store)
    monkeypatch.setattr(oauth_service, "validate_oauth_runtime", lambda _: None)
    entered = asyncio.Event()
    release = asyncio.Event()

    async def crash(
        session: object, _state: str, _code: str, _error: object, _settings: object, _client: object, *, commit: bool
    ) -> SimpleNamespace:
        assert commit is False
        session.add(  # type: ignore[attr-defined]
            ChannelAccount(
                store_id=store_id,
                platform="tiktok",
                external_store_id="crash-test-shop",
                display_name="Crash Test",
                access_token_ref="encrypted:test-only",
                status="connected",
            )
        )
        await session.flush()  # type: ignore[attr-defined]
        entered.set()
        await release.wait()
        raise SystemExit("synthetic worker crash before commit")

    monkeypatch.setattr(oauth_service, "complete_tiktok_oauth", crash)
    try:
        async with sessions() as setup:
            setup.add(
                User(id=user_id, email=f"oauth-{uuid.uuid4().hex}@example.invalid", password_hash="unused", name="Test")
            )
            setup.add(Store(id=store_id, name="OAuth Test", code=f"oauth-lock-{uuid.uuid4().hex}"))
            admin_role_id = await setup.scalar(select(Role.id).where(Role.code == "admin"))
            assert admin_role_id is not None
            await setup.flush()
            await setup.execute(user_roles.insert().values(user_id=user_id, role_id=admin_role_id, store_id=store_id))
            await setup.commit()
            job = await oauth_service.queue_tiktok_oauth(setup, state, "code", settings)

        async def run_first() -> None:
            async with sessions() as first:
                with pytest.raises(SystemExit, match="synthetic worker crash"):
                    await oauth_service.process_tiktok_oauth_job(first, settings)

        first_task = asyncio.create_task(run_first())
        await asyncio.wait_for(entered.wait(), timeout=5)
        async with sessions() as second:
            assert await asyncio.wait_for(oauth_service.process_tiktok_oauth_job(second, settings), timeout=5) is False
        release.set()
        await first_task

        async with sessions() as verify:
            persisted = await verify.get(TikTokOAuthJob, job.id)
            channels = (await verify.scalars(select(ChannelAccount).where(ChannelAccount.store_id == store_id))).all()
            assert persisted is not None and persisted.status == "pending"
            assert channels == []
    finally:
        release.set()
        async with sessions() as cleanup:
            await cleanup.execute(delete(User).where(User.id == user_id))
            await cleanup.execute(delete(Store).where(Store.id == store_id))
            await cleanup.commit()
        await engine.dispose()


@pytest.mark.asyncio
async def test_failed_oauth_keeps_claim_lock_until_single_audit_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    """失败保存点释放后、终态写入前，第二个 worker 仍不能抢占任务。"""
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    user_id, store_id = uuid.uuid4(), uuid.uuid4()
    settings = Settings(
        _env_file=None,
        TIKTOK_CREDENTIAL_ENCRYPTION_KEY="unit-test-encryption-key-with-at-least-32-characters",
    )

    async def peek(_: str) -> dict[str, str]:
        return {"user_id": str(user_id), "store_id": str(store_id), "return_to": "/settings/channels"}

    async def store(*_: object) -> SimpleNamespace:
        return SimpleNamespace(id=store_id)

    async def fail(*_: object, **__: object) -> None:
        raise AppError(ErrorCode.THIRD_PARTY_ERROR, "synthetic platform failure", 502)

    monkeypatch.setattr(oauth_service, "peek_tiktok_oauth_state", peek)
    monkeypatch.setattr(oauth_service, "get_active_store", store)
    monkeypatch.setattr(oauth_service, "validate_oauth_runtime", lambda _: None)
    monkeypatch.setattr(oauth_service, "complete_tiktok_oauth", fail)
    original_finish = oauth_service._finish_tiktok_oauth_job
    before_finish = asyncio.Event()
    release = asyncio.Event()

    async def pause_before_finish(
        session: object, job_id: uuid.UUID, status: str, error_code: str | None = None
    ) -> None:
        before_finish.set()
        await release.wait()
        await original_finish(session, job_id, status, error_code)  # type: ignore[arg-type]

    monkeypatch.setattr(oauth_service, "_finish_tiktok_oauth_job", pause_before_finish)
    try:
        async with sessions() as setup:
            setup.add(
                User(id=user_id, email=f"oauth-{uuid.uuid4().hex}@example.invalid", password_hash="unused", name="Test")
            )
            setup.add(Store(id=store_id, name="OAuth Test", code=f"oauth-fail-{uuid.uuid4().hex}"))
            admin_role_id = await setup.scalar(select(Role.id).where(Role.code == "admin"))
            assert admin_role_id is not None
            await setup.flush()
            await setup.execute(user_roles.insert().values(user_id=user_id, role_id=admin_role_id, store_id=store_id))
            await setup.commit()
            job = await oauth_service.queue_tiktok_oauth(setup, "failed-state-with-enough-length", "code", settings)

        async def run_first() -> bool:
            async with sessions() as first:
                return await oauth_service.process_tiktok_oauth_job(first, settings)

        first_task = asyncio.create_task(run_first())
        await asyncio.wait_for(before_finish.wait(), timeout=5)
        async with sessions() as second:
            assert await asyncio.wait_for(oauth_service.process_tiktok_oauth_job(second, settings), timeout=5) is False
        release.set()
        assert await first_task is True

        async with sessions() as verify:
            persisted = await verify.get(TikTokOAuthJob, job.id)
            audits = (
                await verify.scalars(
                    select(AuditLog).where(AuditLog.store_id == store_id, AuditLog.action == "channel.oauth")
                )
            ).all()
            assert persisted is not None and persisted.status == "failed"
            assert persisted.error_code == ErrorCode.THIRD_PARTY_ERROR.value
            assert persisted.state_cipher is None and persisted.code_cipher is None
            assert len(audits) == 1
    finally:
        release.set()
        async with sessions() as cleanup:
            await cleanup.execute(delete(User).where(User.id == user_id))
            await cleanup.execute(delete(Store).where(Store.id == store_id))
            await cleanup.commit()
        await engine.dispose()
