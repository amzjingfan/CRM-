"""在隔离 PostgreSQL 验证 G5 合成会话的 FK、权限与事务边界。"""

import os
import uuid

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.audit.models import AuditLog
from app.auth.service import build_user_view
from app.conversations.models import Conversation, Message
from app.customers.models import Customer
from app.knowledge_base.models import KnowledgeChunk, KnowledgeDocument
from app.knowledge_base.vector_port import ready_chunks
from app.shared.database import models as _models  # noqa: F401
from app.shared.database.base import Role, User, role_permissions, user_roles
from app.stores.models import Store
from scripts import prepare_sse_staging_content as content
from scripts import prepare_sse_staging_fixture as fixture
from scripts.check_sse_staging_fixture import ReadinessError, check_readiness

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="未提供隔离的 PostgreSQL 测试数据库")


@pytest.mark.asyncio
async def test_fixture_is_scoped_and_rolls_back_on_isolated_postgres(monkeypatch: pytest.MonkeyPatch) -> None:
    assert TEST_DATABASE_URL is not None
    monkeypatch.setattr(fixture, "hash_password", lambda _password: "test-hash")
    monkeypatch.setattr(fixture, "create_access_token", lambda user_id: f"test-{user_id}")
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    run_id = uuid.uuid4()
    try:
        async with sessions() as session:
            await session.begin()
            assert (await check_readiness(session, "staging"))["ready"] is True
            payload = await fixture.provision_fixture(session, run_id)
            store_id = uuid.UUID(payload["manifest"]["store_id"])
            role_id = uuid.UUID(payload["manifest"]["role_id"])
            assert await session.get(Store, store_id) is not None
            assert await session.get(Role, role_id) is not None
            assert (
                await session.scalar(select(func.count()).select_from(Customer).where(Customer.store_id == store_id))
                == 50
            )
            assert (
                await session.scalar(
                    select(func.count()).select_from(Conversation).where(Conversation.store_id == store_id)
                )
                == 50
            )
            assert (
                await session.scalar(select(func.count()).select_from(Message).where(Message.store_id == store_id))
                == 50
            )
            assignments = (await session.execute(select(user_roles).where(user_roles.c.role_id == role_id))).all()
            assert len(assignments) == 50
            assert {row.store_id for row in assignments} == {store_id}
            permissions = (
                await session.execute(select(role_permissions).where(role_permissions.c.role_id == role_id))
            ).all()
            assert len(permissions) == 1
            audit = await session.scalar(select(AuditLog).where(AuditLog.resource_id == store_id))
            assert audit is not None and audit.action == "g5.fixture.provision"
            assert len(payload["clients"]) == 50
            with pytest.raises(ReadinessError) as readiness_error:
                await check_readiness(session, "staging")
            assert readiness_error.value.stage == "existing_fixture"
            for user_id in payload["manifest"]["user_ids"]:
                assert await session.get(User, uuid.UUID(user_id)) is not None
            await session.rollback()
        async with sessions() as session:
            assert await session.get(Store, store_id) is None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_reconcile_only_original_fifty_users_and_sessions_on_isolated_postgres(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert TEST_DATABASE_URL is not None
    monkeypatch.setattr(fixture, "hash_password", lambda _password: "test-hash")
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessions() as session:
            await session.begin()
            payload = await fixture.provision_fixture(session, uuid.uuid4())
            manifest = fixture.validate_reconciliation_payload(payload)
            for user_id in manifest.user_ids:
                user = await session.get(User, user_id)
                assert user is not None
                user.email = user.email.replace("@example.com", "@example.invalid")
            await session.flush()

            users = await fixture.inspect_existing_reconciliation(session, manifest)
            assert len(users) == 50
            repaired = await fixture.reconcile_fixture_emails(session, manifest, users)
            await session.flush()

            assert len(repaired["clients"]) == 50
            assert repaired["manifest"] == payload["manifest"]
            assert all(build_user_view(user).email == user.email for user in users)
            assert (
                await session.scalar(select(func.count()).select_from(User).where(User.id.in_(manifest.user_ids))) == 50
            )
            assert (
                await session.scalar(
                    select(func.count()).select_from(Conversation).where(Conversation.store_id == manifest.store_id)
                )
                == 50
            )
            audits = (await session.scalars(select(AuditLog).where(AuditLog.store_id == manifest.store_id))).all()
            assert {audit.action for audit in audits} == {"g5.fixture.provision", "g5.fixture.reconcile_email"}
            await session.rollback()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_reconcile_rejects_changed_batch_without_touching_emails(monkeypatch: pytest.MonkeyPatch) -> None:
    assert TEST_DATABASE_URL is not None
    monkeypatch.setattr(fixture, "hash_password", lambda _password: "test-hash")
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessions() as session:
            await session.begin()
            payload = await fixture.provision_fixture(session, uuid.uuid4())
            manifest = fixture.validate_reconciliation_payload(payload)
            for user_id in manifest.user_ids:
                user = await session.get(User, user_id)
                assert user is not None
                user.email = user.email.replace("@example.com", "@example.invalid")
            first = await session.get(User, manifest.user_ids[0])
            assert first is not None
            first.status = "disabled"
            await session.flush()

            with pytest.raises(ValueError, match="fixture user mismatch"):
                await fixture.inspect_existing_reconciliation(session, manifest, lock_users=True)
            for user_id in manifest.user_ids:
                user = await session.get(User, user_id)
                assert user is not None and user.email.endswith("@example.invalid")
            assert (
                await session.scalar(
                    select(func.count()).select_from(AuditLog).where(AuditLog.action == "g5.fixture.reconcile_email")
                )
                == 0
            )
            await session.rollback()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_synthetic_content_uses_knowledge_approval_without_persistent_permission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert TEST_DATABASE_URL is not None
    monkeypatch.setattr(fixture, "hash_password", lambda _password: "test-hash")
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessions() as session:
            await session.begin()
            payload = await fixture.provision_fixture(session, uuid.uuid4())
            manifest = fixture.validate_reconciliation_payload(payload)
            for user_id in manifest.user_ids:
                user = await session.get(User, user_id)
                assert user is not None
                user.email = user.email.replace("@example.com", "@example.invalid")
            await session.flush()
            users = await fixture.inspect_existing_reconciliation(session, manifest)
            await fixture.reconcile_fixture_emails(session, manifest, users)
            await session.flush()

            original = await content.inspect_content_fixture(session, manifest)
            assert original.state == "original"
            await content.prepare_synthetic_content(session, manifest, original)
            await session.flush()

            prepared = await content.inspect_content_fixture(session, manifest)
            assert prepared.state == "legacy_prepared"
            assert prepared.document is not None
            assert prepared.document.approved_by == manifest.user_ids[0]
            assert prepared.document.vectorization_status == "pending"
            prepared.document.vectorization_status = "ready"
            session.add(
                KnowledgeChunk(
                    store_id=manifest.store_id,
                    document_id=prepared.document.id,
                    document_version=1,
                    chunk_index=0,
                    content=fixture.G5_LEGACY_ANSWER,
                    token_count=30,
                    embedding=[0.0] * 1024,
                    metadata_json={},
                )
            )
            await session.flush()
            legacy = await content.inspect_content_fixture(session, manifest)
            await content.replace_synthetic_content(session, manifest, legacy)
            await session.flush()
            replaced = await content.inspect_content_fixture(session, manifest)
            assert replaced.state == "prepared"
            assert replaced.document is not None
            assert replaced.document.document_version == 2
            assert replaced.document.vectorization_status == "pending"
            assert {message.content for message in replaced.messages} == {fixture.G5_SYNTHETIC_QUESTION}
            assert await ready_chunks(session, manifest.store_id) == []
            await session.execute(delete(KnowledgeChunk).where(KnowledgeChunk.store_id == manifest.store_id))
            replaced.document.vectorization_status = "ready"
            session.add(
                KnowledgeChunk(
                    store_id=manifest.store_id,
                    document_id=replaced.document.id,
                    document_version=2,
                    chunk_index=0,
                    content=fixture.G5_SYNTHETIC_ANSWER_V2,
                    token_count=45,
                    embedding=[0.0] * 1024,
                    metadata_json={},
                )
            )
            await session.flush()
            second = await content.inspect_content_fixture(session, manifest)
            assert second.state == "prepared"
            await content.replace_third_faq_answer(session, manifest, second)
            await session.flush()
            third = await content.inspect_content_fixture(session, manifest)
            assert third.state == "prepared_v3"
            assert third.document is not None
            assert third.document.answer == fixture.G5_SYNTHETIC_ANSWER
            assert third.document.document_version == 3
            assert third.document.vectorization_status == "pending"
            assert {message.content for message in third.messages} == {fixture.G5_SYNTHETIC_QUESTION}
            assert await ready_chunks(session, manifest.store_id) == []
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(KnowledgeDocument)
                    .where(KnowledgeDocument.store_id == manifest.store_id)
                )
                == 1
            )
            assignments = (
                await session.execute(select(user_roles).where(user_roles.c.user_id.in_(manifest.user_ids)))
            ).all()
            assert len(assignments) == 50
            assert {row.role_id for row in assignments} == {manifest.role_id}
            assert await session.scalar(select(func.count()).select_from(Role).where(Role.code.like("%-approver"))) == 0
            await session.rollback()
    finally:
        await engine.dispose()
