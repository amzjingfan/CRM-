"""在隔离 PostgreSQL 中验证 AI 营销草稿审核的幂等和并发终态。"""

import asyncio
import os
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.audit.models import AuditLog
from app.marketing import service as marketing_service
from app.marketing.models import MarketingCampaign, MarketingEvent
from app.marketing.schemas import MarketingDraftReview
from app.shared.database import models as _models  # noqa: F401
from app.shared.database.base import User
from app.shared.exceptions.errors import AppError
from app.stores.models import Store

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="未提供隔离的 PostgreSQL 测试数据库")


async def create_pending_review(session: AsyncSession) -> tuple[Store, User, MarketingEvent]:
    """创建完全合成的店铺、审核员和待审核事件。"""
    store = Store(name="REAL-AI-04 review", code=f"real-ai04-{uuid.uuid4().hex}")
    user = User(
        email=f"real-ai04-{uuid.uuid4().hex}@example.com",
        password_hash="test-only",
        name="合成审核员",
    )
    session.add_all([store, user])
    await session.flush()
    campaign = MarketingCampaign(
        store_id=store.id,
        name="合成审核活动",
        trigger_type="cart_abandoned",
        action_type="send_message",
        content_mode="ai",
        status="active",
        created_by=user.id,
    )
    session.add(campaign)
    await session.flush()
    event = MarketingEvent(
        store_id=store.id,
        campaign_id=campaign.id,
        source_type="order",
        source_id=uuid.uuid4(),
        status="waiting_review",
        ai_draft_content="合成待审核文案",
        ai_review_status="pending",
        triggered_at=datetime.now(UTC),
    )
    session.add(event)
    await session.commit()
    return store, user, event


async def cleanup_review_fixture(
    session: AsyncSession,
    store_id: uuid.UUID,
    user_id: uuid.UUID,
    event_id: uuid.UUID,
) -> None:
    """删除当前用例的合成数据，审计日志需先于店铺显式清理。"""
    await session.execute(delete(AuditLog).where(AuditLog.resource_id == event_id))
    await session.execute(delete(Store).where(Store.id == store_id))
    await session.execute(delete(User).where(User.id == user_id))
    await session.commit()


@pytest.mark.asyncio
async def test_same_marketing_review_request_replays_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """同键同请求跨会话重放首次结果，同键不同决定返回 409。"""
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    store_id: uuid.UUID | None = None
    user_id: uuid.UUID | None = None
    event_id: uuid.UUID | None = None
    try:
        async with sessions() as setup_session:
            store, user, event = await create_pending_review(setup_session)
            store_id, user_id, event_id = store.id, user.id, event.id

        async def stores(*_args: object) -> set[uuid.UUID]:
            assert store_id is not None
            return {store_id}

        monkeypatch.setattr(marketing_service, "allowed_store_ids", stores)
        payload = MarketingDraftReview(decision="approve", comment="合成审核意见")
        async with sessions() as first_session:
            reviewer = await first_session.get(User, user_id)
            assert reviewer is not None and event_id is not None
            first = await marketing_service.review_marketing_draft(
                first_session,
                reviewer,
                event_id,
                payload,
                "stable-review-key",
            )
            assert first.ai_review_status == "approved"

        async with sessions() as replay_session:
            reviewer = await replay_session.get(User, user_id)
            assert reviewer is not None and event_id is not None
            replay = await marketing_service.review_marketing_draft(
                replay_session,
                reviewer,
                event_id,
                payload,
                "stable-review-key",
            )
            assert replay.ai_review_status == "approved"
            with pytest.raises(AppError) as conflict:
                await marketing_service.review_marketing_draft(
                    replay_session,
                    reviewer,
                    event_id,
                    MarketingDraftReview(decision="reject", comment="合成审核意见"),
                    "stable-review-key",
                )
            assert conflict.value.status_code == 409

        async with sessions() as verify_session:
            audit_count = await verify_session.scalar(
                select(func.count())
                .select_from(AuditLog)
                .where(
                    AuditLog.resource_type == "marketing_event",
                    AuditLog.resource_id == event_id,
                    AuditLog.action == "marketing.ai_draft.review",
                )
            )
            assert audit_count == 1
    finally:
        if store_id is not None and user_id is not None and event_id is not None:
            async with sessions() as cleanup_session:
                await cleanup_review_fixture(cleanup_session, store_id, user_id, event_id)
        await engine.dispose()


@pytest.mark.asyncio
async def test_concurrent_conflicting_marketing_reviews_allow_one_winner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """真实双事务并发批准和拒绝时，只允许一个终态和一条成功审计。"""
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    store_id: uuid.UUID | None = None
    user_id: uuid.UUID | None = None
    event_id: uuid.UUID | None = None
    try:
        async with sessions() as setup_session:
            store, user, event = await create_pending_review(setup_session)
            store_id, user_id, event_id = store.id, user.id, event.id

        ready_count = 0
        ready = asyncio.Event()

        async def stores(*_args: object) -> set[uuid.UUID]:
            nonlocal ready_count
            ready_count += 1
            if ready_count == 2:
                ready.set()
            await ready.wait()
            assert store_id is not None
            return {store_id}

        monkeypatch.setattr(marketing_service, "allowed_store_ids", stores)

        async def review(decision: str, idempotency_key: str) -> MarketingEvent:
            async with sessions() as review_session:
                reviewer = await review_session.get(User, user_id)
                assert reviewer is not None and event_id is not None
                return await marketing_service.review_marketing_draft(
                    review_session,
                    reviewer,
                    event_id,
                    MarketingDraftReview.model_validate({"decision": decision}),
                    idempotency_key,
                )

        results = await asyncio.gather(
            review("approve", "concurrent-approve"),
            review("reject", "concurrent-reject"),
            return_exceptions=True,
        )
        successful = [result for result in results if isinstance(result, MarketingEvent)]
        conflicts = [result for result in results if isinstance(result, AppError) and result.status_code == 409]
        assert len(successful) == 1
        assert len(conflicts) == 1

        async with sessions() as verify_session:
            assert event_id is not None
            stored = await verify_session.get(MarketingEvent, event_id)
            assert stored is not None
            assert stored.ai_review_status in {"approved", "rejected"}
            audit_count = await verify_session.scalar(
                select(func.count())
                .select_from(AuditLog)
                .where(
                    AuditLog.resource_type == "marketing_event",
                    AuditLog.resource_id == event_id,
                    AuditLog.action == "marketing.ai_draft.review",
                )
            )
            assert audit_count == 1
    finally:
        if store_id is not None and user_id is not None and event_id is not None:
            async with sessions() as cleanup_session:
                await cleanup_review_fixture(cleanup_session, store_id, user_id, event_id)
        await engine.dispose()
