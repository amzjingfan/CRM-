"""REAL-AI-04 第二次独立复测探针。

本文件位于测试工程师证据目录，不属于产品测试集。探针只使用内存替身，
验证 SSE 交付终态、AI 营销待审、店铺隔离以及审核幂等/并发语义，不连接
真实平台、不调用真实模型，也不产生任何外部写操作。
"""

import asyncio
import os
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import Request
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.audit.models import AuditLog
from app.chat import router as chat_router
from app.chat.schemas import ChatQueryRequest, SuggestionView
from app.marketing import service as marketing_service
from app.marketing import worker as marketing_worker
from app.marketing.models import MarketingCampaign, MarketingEvent
from app.marketing.repository import find_event as find_event_in_database
from app.marketing.schemas import MarketingDraftReview
from app.shared.config.settings import Settings
from app.shared.database.base import User
from app.shared.exceptions.errors import AppError
from app.stores.models import Store

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")


class MarketingCycleSession:
    """只暴露营销 Worker 认领安全草稿所需的最小会话端口。"""

    def __init__(self, event: SimpleNamespace, campaign: SimpleNamespace) -> None:
        self.event = event
        self.campaign = campaign

    async def scalar(self, _statement: object) -> SimpleNamespace:
        return self.event

    async def get(self, _model: object, _entity_id: uuid.UUID) -> SimpleNamespace:
        return self.campaign

    async def commit(self) -> None:
        return None


class ReviewSession:
    """保存独立事务快照，并记录人工审核产生的审计对象。"""

    def __init__(self, event: SimpleNamespace, barrier: "CommitBarrier | None" = None) -> None:
        self.event = event
        self.barrier = barrier
        self.added: list[object] = []

    def add(self, value: object) -> None:
        self.added.append(value)

    async def commit(self) -> None:
        if self.barrier is not None:
            await self.barrier.wait()

    async def refresh(self, _value: object) -> None:
        return None


class CommitBarrier:
    """让两个审核事务都在提交前完成状态检查，稳定复现并发竞争。"""

    def __init__(self, parties: int = 2) -> None:
        self.parties = parties
        self.arrived = 0
        self.ready = asyncio.Event()

    async def wait(self) -> None:
        self.arrived += 1
        if self.arrived >= self.parties:
            self.ready.set()
        await self.ready.wait()


def build_pending_review_event(store_id: uuid.UUID) -> SimpleNamespace:
    """构造不包含真实客户数据的待审核营销事件。"""
    return SimpleNamespace(
        id=uuid.uuid4(),
        store_id=store_id,
        status="waiting_review",
        ai_review_status="pending",
        ai_draft_content="合成待审核文案",
        ai_draft_agent_run_id=uuid.uuid4(),
        ai_reviewed_by=None,
        ai_reviewed_at=None,
        completed_at=None,
        error_code=None,
        tool_call_ids=[],
    )


@pytest.mark.asyncio
async def test_sse_disconnect_before_result_records_delivery_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """工作流成功但结果未交给传输层时，断开必须补记交付失败。"""
    run_id = uuid.uuid4()
    marked: list[tuple[uuid.UUID, str]] = []
    user = SimpleNamespace(id=uuid.uuid4())
    request = SimpleNamespace(
        state=SimpleNamespace(trace_id=str(uuid.uuid4())),
        client=SimpleNamespace(host="127.0.0.1"),
        is_disconnected=_always_disconnected,
    )

    async def allow_limits(_request: Request, _user: object) -> None:
        return None

    async def acquire(_user_id: uuid.UUID, _limit: int) -> bool:
        return True

    async def release(_user_id: uuid.UUID) -> None:
        return None

    async def suggest(*_args: object, **_kwargs: object) -> SuggestionView:
        return SuggestionView(
            agent_run_id=run_id,
            content="不会被交付的合成草稿",
            intent="faq",
            confidence=0.9,
            action="human_review",
            terminal_state="HUMAN_REVIEW",
            requires_human=True,
            transfer_performed=False,
            citations=[],
            trace_id=str(uuid.uuid4()),
        )

    async def mark(_session: Any, agent_run_id: uuid.UUID, error_code: str) -> None:
        marked.append((agent_run_id, error_code))

    monkeypatch.setattr(chat_router, "_enforce_chat_limits", allow_limits)
    monkeypatch.setattr(chat_router, "acquire_chat_stream", acquire)
    monkeypatch.setattr(chat_router, "release_chat_stream", release)
    monkeypatch.setattr(chat_router, "suggest_for_user", suggest)
    monkeypatch.setattr(chat_router, "mark_suggestion_delivery_interrupted", mark)

    response = await chat_router.chat_query(
        ChatQueryRequest(session_id=uuid.uuid4()),
        request,  # type: ignore[arg-type]
        SimpleNamespace(),  # type: ignore[arg-type]
        user,  # type: ignore[arg-type]
    )
    body = "".join([chunk async for chunk in response.body_iterator])

    assert "event: result" not in body
    assert marked == [(run_id, "SSE_DELIVERY_INTERRUPTED")]


@pytest.mark.asyncio
async def test_sse_cancel_after_workflow_result_records_cancelled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """结果对象已经产生后发生取消，必须使用稳定取消错误码补记。"""
    run_id = uuid.uuid4()
    marked: list[tuple[uuid.UUID, str]] = []
    user = SimpleNamespace(id=uuid.uuid4())
    request = SimpleNamespace(
        state=SimpleNamespace(trace_id=str(uuid.uuid4())),
        client=SimpleNamespace(host="127.0.0.1"),
        is_disconnected=_never_disconnected,
    )

    async def allow_limits(_request: Request, _user: object) -> None:
        return None

    async def acquire(_user_id: uuid.UUID, _limit: int) -> bool:
        return True

    async def release(_user_id: uuid.UUID) -> None:
        return None

    async def suggest(*_args: object, **_kwargs: object) -> SuggestionView:
        return SuggestionView(
            agent_run_id=run_id,
            content="合成草稿",
            intent="faq",
            confidence=0.9,
            action="human_review",
            terminal_state="HUMAN_REVIEW",
            requires_human=True,
            transfer_performed=False,
            citations=[],
            trace_id=str(uuid.uuid4()),
        )

    async def cancel_before_output(*_args: object, **_kwargs: object) -> None:
        raise asyncio.CancelledError

    async def mark(_session: Any, agent_run_id: uuid.UUID, error_code: str) -> None:
        marked.append((agent_run_id, error_code))

    monkeypatch.setattr(chat_router, "_enforce_chat_limits", allow_limits)
    monkeypatch.setattr(chat_router, "acquire_chat_stream", acquire)
    monkeypatch.setattr(chat_router, "release_chat_stream", release)
    monkeypatch.setattr(chat_router, "suggest_for_user", suggest)
    monkeypatch.setattr(chat_router, "record_first_output_latency", cancel_before_output)
    monkeypatch.setattr(chat_router, "mark_suggestion_delivery_interrupted", mark)

    response = await chat_router.chat_query(
        ChatQueryRequest(session_id=uuid.uuid4()),
        request,  # type: ignore[arg-type]
        SimpleNamespace(),  # type: ignore[arg-type]
        user,  # type: ignore[arg-type]
    )
    body = "".join([chunk async for chunk in response.body_iterator])

    assert "event: result" not in body
    assert marked == [(run_id, "SSE_DELIVERY_CANCELLED")]


@pytest.mark.asyncio
async def test_safe_marketing_candidate_stops_at_waiting_review(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """安全候选必须持久化待审，不能在同一 Worker 周期调用平台工具。"""
    event = SimpleNamespace(
        id=uuid.uuid4(),
        campaign_id=uuid.uuid4(),
        status="waiting_ai",
        attempt_count=0,
        next_attempt_at=datetime.now(UTC),
        tool_call_ids=[],
        error_code=None,
        completed_at=None,
        ai_draft_content=None,
        ai_draft_agent_run_id=None,
        ai_review_status=None,
        ai_reviewed_by=None,
        ai_reviewed_at=None,
    )
    campaign = SimpleNamespace(
        id=event.campaign_id,
        status="active",
        content_mode="ai",
        action_type="send_coupon_and_message",
        template_content=None,
    )
    side_effects: list[str] = []

    async def generate(*_args: object) -> SimpleNamespace:
        return SimpleNamespace(content="合成安全营销草稿", agent_run_id=uuid.uuid4())

    async def forbidden_side_effect(*_args: object, **_kwargs: object) -> uuid.UUID:
        side_effects.append("called")
        return uuid.uuid4()

    monkeypatch.setattr(marketing_worker, "_generate_ai_content", generate)
    monkeypatch.setattr(marketing_worker, "_send_coupon", forbidden_side_effect)
    monkeypatch.setattr(marketing_worker, "_send_message", forbidden_side_effect)
    settings = Settings(
        _env_file=None,
        JWT_SECRET_KEY="test-secret-key-with-32-characters",
        LLM_ENABLED=True,
        AI_MARKETING_ENABLED=True,
    )

    await marketing_worker._execute_due_event(  # noqa: SLF001
        MarketingCycleSession(event, campaign),  # type: ignore[arg-type]
        datetime.now(UTC),
        settings,
    )

    assert event.status == "waiting_review"
    assert event.ai_review_status == "pending"
    assert event.ai_draft_content == "合成安全营销草稿"
    assert event.tool_call_ids == []
    assert side_effects == []


@pytest.mark.asyncio
async def test_cross_store_marketing_review_fails_as_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """审核资源不属于当前授权店铺时必须返回不存在，避免泄漏资源事实。"""
    user = SimpleNamespace(id=uuid.uuid4())

    async def stores(*_args: object) -> set[uuid.UUID]:
        return {uuid.uuid4()}

    async def find(*_args: object) -> None:
        return None

    monkeypatch.setattr(marketing_service, "allowed_store_ids", stores)
    monkeypatch.setattr(marketing_service, "find_event", find)

    with pytest.raises(AppError) as caught:
        await marketing_service.review_marketing_draft(
            ReviewSession(build_pending_review_event(uuid.uuid4())),  # type: ignore[arg-type]
            user,  # type: ignore[arg-type]
            uuid.uuid4(),
            MarketingDraftReview(decision="approve"),
        )

    assert caught.value.status_code == 404


@pytest.mark.asyncio
async def test_same_marketing_review_retry_replays_original_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """同一审核请求重试应重放原结果，而不是把网络重试转换为 409。"""
    store_id = uuid.uuid4()
    user = SimpleNamespace(id=uuid.uuid4())
    event = build_pending_review_event(store_id)
    session = ReviewSession(event)

    async def stores(*_args: object) -> set[uuid.UUID]:
        return {store_id}

    async def find(*_args: object) -> SimpleNamespace:
        return event

    monkeypatch.setattr(marketing_service, "allowed_store_ids", stores)
    monkeypatch.setattr(marketing_service, "find_event", find)
    payload = MarketingDraftReview(decision="approve", comment="合成审核意见")

    first = await marketing_service.review_marketing_draft(
        session,  # type: ignore[arg-type]
        user,  # type: ignore[arg-type]
        event.id,
        payload,
    )
    replay = await marketing_service.review_marketing_draft(
        session,  # type: ignore[arg-type]
        user,  # type: ignore[arg-type]
        event.id,
        payload,
    )

    assert first.ai_review_status == "approved"
    assert replay.ai_review_status == "approved"
    assert len(session.added) == 1


@pytest.mark.asyncio
async def test_concurrent_conflicting_reviews_allow_only_one_terminal_decision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """并发批准和拒绝只能有一个成功，避免末次提交覆盖首个审核事实。"""
    store_id = uuid.uuid4()
    user = SimpleNamespace(id=uuid.uuid4())
    event_id = uuid.uuid4()
    barrier = CommitBarrier()
    approve_event = build_pending_review_event(store_id)
    reject_event = build_pending_review_event(store_id)
    approve_event.id = event_id
    reject_event.id = event_id
    approve_session = ReviewSession(approve_event, barrier)
    reject_session = ReviewSession(reject_event, barrier)

    async def stores(*_args: object) -> set[uuid.UUID]:
        return {store_id}

    async def find(session: ReviewSession, *_args: object) -> SimpleNamespace:
        return session.event

    monkeypatch.setattr(marketing_service, "allowed_store_ids", stores)
    monkeypatch.setattr(marketing_service, "find_event", find)

    results = await asyncio.gather(
        marketing_service.review_marketing_draft(
            approve_session,  # type: ignore[arg-type]
            user,  # type: ignore[arg-type]
            event_id,
            MarketingDraftReview(decision="approve"),
        ),
        marketing_service.review_marketing_draft(
            reject_session,  # type: ignore[arg-type]
            user,  # type: ignore[arg-type]
            event_id,
            MarketingDraftReview(decision="reject"),
        ),
        return_exceptions=True,
    )

    successful = [result for result in results if not isinstance(result, BaseException)]
    rejected = [result for result in results if isinstance(result, AppError)]
    assert len(successful) == 1
    assert len(rejected) == 1


@pytest.mark.skipif(not TEST_DATABASE_URL, reason="未提供隔离的 PostgreSQL 测试数据库")
@pytest.mark.asyncio
async def test_postgres_concurrent_conflicting_reviews_are_serialized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """真实 PostgreSQL 中并发审核也必须原子化，只允许一个终态和一条审计。"""
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    store_id: uuid.UUID | None = None
    user_id: uuid.UUID | None = None
    event_id: uuid.UUID | None = None
    try:
        async with sessions() as setup_session:
            store = Store(name="REAL-AI-04 review", code=f"real-ai04-review-{uuid.uuid4().hex}")
            user = User(
                email=f"real-ai04-{uuid.uuid4().hex}@example.com",
                password_hash="not-a-real-password-hash",
                name="合成审核员",
            )
            setup_session.add_all([store, user])
            await setup_session.flush()
            campaign = MarketingCampaign(
                store_id=store.id,
                name="合成审核活动",
                trigger_type="cart_abandoned",
                action_type="send_message",
                content_mode="ai",
                status="active",
                created_by=user.id,
            )
            setup_session.add(campaign)
            await setup_session.flush()
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
            setup_session.add(event)
            await setup_session.commit()
            store_id = store.id
            user_id = user.id
            event_id = event.id

        barrier = CommitBarrier()

        async def stores(*_args: object) -> set[uuid.UUID]:
            assert store_id is not None
            return {store_id}

        async def find_and_wait(
            session: Any,
            requested_event_id: uuid.UUID,
            store_ids: set[uuid.UUID],
        ) -> MarketingEvent | None:
            selected = await find_event_in_database(session, requested_event_id, store_ids)
            await barrier.wait()
            return selected

        monkeypatch.setattr(marketing_service, "allowed_store_ids", stores)
        monkeypatch.setattr(marketing_service, "find_event", find_and_wait)

        async with sessions() as approve_session, sessions() as reject_session:
            approve_user = await approve_session.get(User, user_id)
            reject_user = await reject_session.get(User, user_id)
            assert approve_user is not None and reject_user is not None and event_id is not None
            results = await asyncio.gather(
                marketing_service.review_marketing_draft(
                    approve_session,
                    approve_user,
                    event_id,
                    MarketingDraftReview(decision="approve"),
                ),
                marketing_service.review_marketing_draft(
                    reject_session,
                    reject_user,
                    event_id,
                    MarketingDraftReview(decision="reject"),
                ),
                return_exceptions=True,
            )

        successful = [result for result in results if not isinstance(result, BaseException)]
        rejected = [result for result in results if isinstance(result, AppError)]
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

        actual = (len(successful), len(rejected), audit_count)
        assert actual == (1, 1, 1), (
            "并发审核实际结果应为 1 个成功、1 个冲突、1 条审计；"
            f"当前得到 successful={actual[0]}, rejected={actual[1]}, audit_count={actual[2]}"
        )
    finally:
        async with sessions() as cleanup_session:
            if store_id is not None:
                await cleanup_session.execute(delete(Store).where(Store.id == store_id))
            if user_id is not None:
                await cleanup_session.execute(delete(User).where(User.id == user_id))
            await cleanup_session.commit()
        await engine.dispose()


async def _always_disconnected() -> bool:
    return True


async def _never_disconnected() -> bool:
    return False
