"""AI 营销草稿人工审核的幂等和并发状态机回归测试。"""

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.marketing import service as marketing_service
from app.marketing.schemas import MarketingDraftReview
from app.shared.exceptions.errors import AppError


class ReviewSession:
    """记录审核事务的审计写入和提交次数。"""

    def __init__(self) -> None:
        self.added: list[object] = []
        self.commit_count = 0

    def add(self, value: object) -> None:
        """记录待提交对象。"""
        self.added.append(value)

    async def commit(self) -> None:
        """记录一次完整审核事务提交。"""
        self.commit_count += 1

    async def rollback(self) -> None:
        """模拟事务回滚。"""

    async def refresh(self, _value: object) -> None:
        """内存对象无需刷新。"""


def pending_event(store_id: uuid.UUID) -> SimpleNamespace:
    """构造不含真实客户数据的待审核事件。"""
    return SimpleNamespace(
        id=uuid.uuid4(),
        store_id=store_id,
        status="waiting_review",
        ai_review_status="pending",
        ai_draft_content="合成待审核文案",
        ai_draft_agent_run_id=uuid.uuid4(),
        ai_reviewed_by=None,
        ai_reviewed_at=None,
        ai_review_idempotency_key=None,
        ai_review_request_hash=None,
        completed_at=None,
        error_code=None,
        tool_call_ids=[],
    )


@pytest.mark.asyncio
async def test_same_review_key_and_payload_replays_without_duplicate_audit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """同键同请求必须重放首次审核结果，且不能重复写成功审计。"""
    store_id = uuid.uuid4()
    user = SimpleNamespace(id=uuid.uuid4())
    event = pending_event(store_id)
    session = ReviewSession()

    async def stores(*_args: object) -> set[uuid.UUID]:
        return {store_id}

    async def claim(*_args: object, **kwargs: object) -> SimpleNamespace | None:
        if event.status != "waiting_review":
            return None
        event.status = str(kwargs["review_status"])
        event.ai_review_status = str(kwargs["review_status"])
        event.ai_reviewed_by = user.id
        event.ai_reviewed_at = datetime.now(UTC)
        event.ai_review_idempotency_key = str(kwargs["idempotency_key"])
        event.ai_review_request_hash = str(kwargs["request_hash"])
        return event

    async def find(*_args: object, **_kwargs: object) -> SimpleNamespace:
        return event

    monkeypatch.setattr(marketing_service, "allowed_store_ids", stores)
    monkeypatch.setattr(marketing_service, "claim_event_review", claim)
    monkeypatch.setattr(marketing_service, "find_event", find)
    payload = MarketingDraftReview(decision="approve", comment="合成审核意见")

    first = await marketing_service.review_marketing_draft(
        session,  # type: ignore[arg-type]
        user,  # type: ignore[arg-type]
        event.id,
        payload,
        "stable-review-key",
    )
    replay = await marketing_service.review_marketing_draft(
        session,  # type: ignore[arg-type]
        user,  # type: ignore[arg-type]
        event.id,
        payload,
        "stable-review-key",
    )

    assert first.ai_review_status == "approved"
    assert replay.ai_review_status == "approved"
    assert session.commit_count == 1
    assert len(session.added) == 1


@pytest.mark.asyncio
async def test_same_review_key_with_different_payload_returns_conflict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """同一幂等键改为相反审核决定时必须返回冲突。"""
    store_id = uuid.uuid4()
    user = SimpleNamespace(id=uuid.uuid4())
    event = pending_event(store_id)
    session = ReviewSession()

    async def stores(*_args: object) -> set[uuid.UUID]:
        return {store_id}

    async def claim(*_args: object, **kwargs: object) -> SimpleNamespace | None:
        if event.status != "waiting_review":
            return None
        event.status = str(kwargs["review_status"])
        event.ai_review_status = str(kwargs["review_status"])
        event.ai_reviewed_by = user.id
        event.ai_review_idempotency_key = str(kwargs["idempotency_key"])
        event.ai_review_request_hash = str(kwargs["request_hash"])
        return event

    async def find(*_args: object, **_kwargs: object) -> SimpleNamespace:
        return event

    monkeypatch.setattr(marketing_service, "allowed_store_ids", stores)
    monkeypatch.setattr(marketing_service, "claim_event_review", claim)
    monkeypatch.setattr(marketing_service, "find_event", find)

    await marketing_service.review_marketing_draft(
        session,  # type: ignore[arg-type]
        user,  # type: ignore[arg-type]
        event.id,
        MarketingDraftReview(decision="approve"),
        "reused-review-key",
    )
    with pytest.raises(AppError) as caught:
        await marketing_service.review_marketing_draft(
            session,  # type: ignore[arg-type]
            user,  # type: ignore[arg-type]
            event.id,
            MarketingDraftReview(decision="reject"),
            "reused-review-key",
        )

    assert caught.value.status_code == 409
    assert session.commit_count == 1
    assert len(session.added) == 1
