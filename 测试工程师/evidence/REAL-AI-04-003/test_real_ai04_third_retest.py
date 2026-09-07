"""REAL-AI-04 第三次独立复测探针。

本探针由测试工程师维护，不属于产品测试集。它使用隔离 PostgreSQL 验证
AI 营销草稿审核的幂等重放、冲突检测、并发唯一终态、店铺隔离与审计
原子性；同时检查 HTTP/前端契约仍明确保持“审核不发送”。
"""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.audit.models import AuditLog
from app.main import app
from app.marketing import service as marketing_service
from app.marketing.models import MarketingCampaign, MarketingEvent
from app.marketing.schemas import MarketingDraftReview
from app.shared.database import models as _models  # noqa: F401
from app.shared.database.base import User
from app.shared.exceptions.errors import AppError
from app.stores.models import Store

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
PROJECT_ROOT = Path(__file__).resolve().parents[3] / "CRM智能聊天系统"


async def create_review_fixture(
    session: AsyncSession,
    *,
    stores_count: int,
    events_per_store: int,
) -> tuple[User, list[Store], list[list[MarketingEvent]]]:
    """创建不包含真实客户信息的店铺、审核员和待审核事件。"""
    user = User(
        email=f"real-ai04-tester-{uuid.uuid4().hex}@example.com",
        password_hash="test-only-not-a-real-password",
        name="第三轮合成审核员",
    )
    session.add(user)
    await session.flush()
    stores: list[Store] = []
    event_groups: list[list[MarketingEvent]] = []
    for store_index in range(stores_count):
        store = Store(
            name=f"REAL-AI-04 third retest {store_index}",
            code=f"real-ai04-third-{uuid.uuid4().hex}",
        )
        session.add(store)
        await session.flush()
        campaign = MarketingCampaign(
            store_id=store.id,
            name=f"第三轮合成活动 {store_index}",
            trigger_type="cart_abandoned",
            action_type="send_message",
            content_mode="ai",
            status="active",
            created_by=user.id,
        )
        session.add(campaign)
        await session.flush()
        events: list[MarketingEvent] = []
        for event_index in range(events_per_store):
            event = MarketingEvent(
                store_id=store.id,
                campaign_id=campaign.id,
                source_type="order",
                source_id=uuid.uuid4(),
                status="waiting_review",
                ai_draft_content=f"第三轮合成待审核文案 {store_index}-{event_index}",
                ai_review_status="pending",
                triggered_at=datetime.now(UTC),
            )
            session.add(event)
            events.append(event)
        stores.append(store)
        event_groups.append(events)
    await session.commit()
    return user, stores, event_groups


async def cleanup_review_fixture(
    session: AsyncSession,
    *,
    store_ids: list[uuid.UUID],
    user_id: uuid.UUID,
) -> None:
    """仅删除本探针创建的合成数据，避免影响任何现有项目数据。"""
    await session.execute(delete(AuditLog).where(AuditLog.store_id.in_(store_ids)))
    await session.execute(delete(Store).where(Store.id.in_(store_ids)))
    await session.execute(delete(User).where(User.id == user_id))
    await session.commit()


async def execute_review(
    sessions: async_sessionmaker[AsyncSession],
    *,
    user_id: uuid.UUID,
    event_id: uuid.UUID,
    decision: str,
    idempotency_key: str,
    comment: str | None = None,
) -> MarketingEvent:
    """在独立数据库会话中执行一次人工审核。"""
    async with sessions() as session:
        reviewer = await session.get(User, user_id)
        assert reviewer is not None
        payload = MarketingDraftReview.model_validate(
            {"decision": decision, "comment": comment}
        )
        return await marketing_service.review_marketing_draft(
            session,
            reviewer,
            event_id,
            payload,
            idempotency_key,
        )


def test_review_contract_requires_stable_key_and_never_claims_to_send() -> None:
    """HTTP 与前端契约必须要求稳定键，并明确审核不触发平台写操作。"""
    operation = app.openapi()["paths"][
        "/v1/marketing/events/{event_id}/review"
    ]["post"]
    idempotency_headers = [
        parameter
        for parameter in operation["parameters"]
        if parameter["in"] == "header" and parameter["name"] == "Idempotency-Key"
    ]
    assert len(idempotency_headers) == 1
    assert idempotency_headers[0]["required"] is True
    assert "不执行发券、消息或任何平台写操作" in operation["description"]

    api_source = (PROJECT_ROOT / "frontend/lib/api.ts").read_text(encoding="utf-8")
    page_source = (PROJECT_ROOT / "frontend/app/marketing/page.tsx").read_text(
        encoding="utf-8"
    )
    assert "const stableInit = withStableIdempotencyKey(init)" in api_source
    assert "response = await rawRequest(path, stableInit)" in api_source
    assert "reviewMarketingDraft(item.id, decision, createIdempotencyKey())" in page_source
    assert "仅记录审核结论，不会发送消息或发放优惠券" in page_source


@pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="未提供隔离的 PostgreSQL 测试数据库",
)
@pytest.mark.asyncio
async def test_persistent_replay_conflict_and_store_scoped_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """同店铺同键只对应一个请求；跨店铺相同键互不串扰。"""
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    user_id: uuid.UUID | None = None
    store_ids: list[uuid.UUID] = []
    try:
        async with sessions() as setup_session:
            user, stores, event_groups = await create_review_fixture(
                setup_session,
                stores_count=2,
                events_per_store=2,
            )
            user_id = user.id
            store_ids = [store.id for store in stores]
            first_event = event_groups[0][0]
            same_store_other_event = event_groups[0][1]
            other_store_event = event_groups[1][0]

        async def allowed(*_args: object) -> set[uuid.UUID]:
            return set(store_ids)

        monkeypatch.setattr(marketing_service, "allowed_store_ids", allowed)
        first = await execute_review(
            sessions,
            user_id=user_id,
            event_id=first_event.id,
            decision="approve",
            comment="第三轮合成审核意见",
            idempotency_key="third-stable-key",
        )
        replay = await execute_review(
            sessions,
            user_id=user_id,
            event_id=first_event.id,
            decision="approve",
            comment="第三轮合成审核意见",
            idempotency_key="third-stable-key",
        )
        assert first.ai_review_status == replay.ai_review_status == "approved"

        with pytest.raises(AppError) as changed_payload:
            await execute_review(
                sessions,
                user_id=user_id,
                event_id=first_event.id,
                decision="reject",
                comment="第三轮合成审核意见",
                idempotency_key="third-stable-key",
            )
        assert changed_payload.value.status_code == 409

        with pytest.raises(AppError) as changed_event:
            await execute_review(
                sessions,
                user_id=user_id,
                event_id=same_store_other_event.id,
                decision="approve",
                idempotency_key="third-stable-key",
            )
        assert changed_event.value.status_code == 409

        cross_store = await execute_review(
            sessions,
            user_id=user_id,
            event_id=other_store_event.id,
            decision="approve",
            idempotency_key="third-stable-key",
        )
        assert cross_store.ai_review_status == "approved"

        async with sessions() as verify_session:
            first_audits = await verify_session.scalar(
                select(func.count())
                .select_from(AuditLog)
                .where(AuditLog.resource_id == first_event.id)
            )
            changed_event_audits = await verify_session.scalar(
                select(func.count())
                .select_from(AuditLog)
                .where(AuditLog.resource_id == same_store_other_event.id)
            )
            cross_store_audits = await verify_session.scalar(
                select(func.count())
                .select_from(AuditLog)
                .where(AuditLog.resource_id == other_store_event.id)
            )
            assert (first_audits, changed_event_audits, cross_store_audits) == (
                1,
                0,
                1,
            )
    finally:
        if user_id is not None and store_ids:
            async with sessions() as cleanup_session:
                await cleanup_review_fixture(
                    cleanup_session,
                    store_ids=store_ids,
                    user_id=user_id,
                )
        await engine.dispose()


@pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="未提供隔离的 PostgreSQL 测试数据库",
)
@pytest.mark.asyncio
async def test_concurrent_terminal_decision_and_same_request_replay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """并发相反决定仅一方成功；同请求并发重放只生成一条审计。"""
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    user_id: uuid.UUID | None = None
    store_ids: list[uuid.UUID] = []
    try:
        async with sessions() as setup_session:
            user, stores, event_groups = await create_review_fixture(
                setup_session,
                stores_count=1,
                events_per_store=2,
            )
            user_id = user.id
            store_ids = [stores[0].id]
            conflict_event = event_groups[0][0]
            replay_event = event_groups[0][1]

        gate_count = 0
        gate = asyncio.Event()

        async def allowed(*_args: object) -> set[uuid.UUID]:
            nonlocal gate_count
            gate_count += 1
            if gate_count >= 2:
                gate.set()
            await gate.wait()
            return set(store_ids)

        monkeypatch.setattr(marketing_service, "allowed_store_ids", allowed)
        conflict_results = await asyncio.gather(
            execute_review(
                sessions,
                user_id=user_id,
                event_id=conflict_event.id,
                decision="approve",
                idempotency_key="third-concurrent-approve",
            ),
            execute_review(
                sessions,
                user_id=user_id,
                event_id=conflict_event.id,
                decision="reject",
                idempotency_key="third-concurrent-reject",
            ),
            return_exceptions=True,
        )
        winners = [item for item in conflict_results if isinstance(item, MarketingEvent)]
        conflicts = [
            item
            for item in conflict_results
            if isinstance(item, AppError) and item.status_code == 409
        ]
        assert (len(winners), len(conflicts)) == (1, 1)

        gate_count = 0
        gate = asyncio.Event()
        replay_results = await asyncio.gather(
            execute_review(
                sessions,
                user_id=user_id,
                event_id=replay_event.id,
                decision="approve",
                comment="完全相同的并发请求",
                idempotency_key="third-concurrent-replay",
            ),
            execute_review(
                sessions,
                user_id=user_id,
                event_id=replay_event.id,
                decision="approve",
                comment="完全相同的并发请求",
                idempotency_key="third-concurrent-replay",
            ),
            return_exceptions=True,
        )
        assert all(isinstance(item, MarketingEvent) for item in replay_results)

        async with sessions() as verify_session:
            conflict_audits = await verify_session.scalar(
                select(func.count())
                .select_from(AuditLog)
                .where(AuditLog.resource_id == conflict_event.id)
            )
            replay_audits = await verify_session.scalar(
                select(func.count())
                .select_from(AuditLog)
                .where(AuditLog.resource_id == replay_event.id)
            )
            assert (conflict_audits, replay_audits) == (1, 1)
            audit_rows = list(
                (
                    await verify_session.scalars(
                        select(AuditLog).where(
                            AuditLog.resource_id.in_(
                                [conflict_event.id, replay_event.id]
                            )
                        )
                    )
                ).all()
            )
            assert all(row.after_data["send_performed"] is False for row in audit_rows)
            assert all("idempotency_key_sha256" in row.after_data for row in audit_rows)
    finally:
        if user_id is not None and store_ids:
            async with sessions() as cleanup_session:
                await cleanup_review_fixture(
                    cleanup_session,
                    store_ids=store_ids,
                    user_id=user_id,
                )
        await engine.dispose()


@pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="未提供隔离的 PostgreSQL 测试数据库",
)
@pytest.mark.asyncio
async def test_cross_store_review_returns_not_found_without_audit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """未授权店铺资源必须返回 404，且不能产生审核终态或审计。"""
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    user_id: uuid.UUID | None = None
    store_ids: list[uuid.UUID] = []
    try:
        async with sessions() as setup_session:
            user, stores, event_groups = await create_review_fixture(
                setup_session,
                stores_count=2,
                events_per_store=1,
            )
            user_id = user.id
            store_ids = [store.id for store in stores]
            forbidden_event = event_groups[1][0]

        async def allowed(*_args: object) -> set[uuid.UUID]:
            return {store_ids[0]}

        monkeypatch.setattr(marketing_service, "allowed_store_ids", allowed)
        with pytest.raises(AppError) as not_found:
            await execute_review(
                sessions,
                user_id=user_id,
                event_id=forbidden_event.id,
                decision="approve",
                idempotency_key="third-cross-store-denied",
            )
        assert not_found.value.status_code == 404

        async with sessions() as verify_session:
            stored = await verify_session.get(MarketingEvent, forbidden_event.id)
            assert stored is not None
            assert (stored.status, stored.ai_review_status) == (
                "waiting_review",
                "pending",
            )
            audit_count = await verify_session.scalar(
                select(func.count())
                .select_from(AuditLog)
                .where(AuditLog.resource_id == forbidden_event.id)
            )
            assert audit_count == 0
    finally:
        if user_id is not None and store_ids:
            async with sessions() as cleanup_session:
                await cleanup_review_fixture(
                    cleanup_session,
                    store_ids=store_ids,
                    user_id=user_id,
                )
        await engine.dispose()
