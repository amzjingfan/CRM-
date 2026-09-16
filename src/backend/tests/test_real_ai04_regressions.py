"""REAL-AI-04 正式测试报告中两项 P1 缺陷的回归测试。"""

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import Request

from app.chat import router as chat_router
from app.chat.schemas import ChatQueryRequest, SuggestionView
from app.chat.service import mark_suggestion_delivery_interrupted
from app.main import app
from app.marketing import service as marketing_service
from app.marketing import worker as marketing_worker
from app.marketing.schemas import MarketingDraftReview
from app.shared.config.settings import Settings


class MarketingCycleSession:
    """只提供营销 Worker 回归测试所需的最小异步会话端口。"""

    def __init__(self, event: SimpleNamespace, campaign: SimpleNamespace) -> None:
        self.event = event
        self.campaign = campaign
        self.commit_count = 0

    async def scalar(self, _statement: object) -> SimpleNamespace:
        return self.event

    async def get(self, _model: object, _entity_id: uuid.UUID) -> SimpleNamespace:
        return self.campaign

    async def commit(self) -> None:
        self.commit_count += 1


class ReviewSession:
    """记录人工审核服务产生的审计对象和提交行为。"""

    def __init__(self) -> None:
        self.added: list[object] = []
        self.commit_count = 0

    def add(self, value: object) -> None:
        self.added.append(value)

    async def commit(self) -> None:
        self.commit_count += 1

    async def refresh(self, _value: object) -> None:
        return None


class AgentRunSession:
    """提供 AgentRun 交付终态测试所需的最小会话端口。"""

    def __init__(self, run: SimpleNamespace) -> None:
        self.run = run
        self.commit_count = 0

    async def get(self, _model: object, _entity_id: uuid.UUID) -> SimpleNamespace:
        return self.run

    async def commit(self) -> None:
        self.commit_count += 1


@pytest.mark.asyncio
async def test_safe_ai_marketing_draft_waits_for_review_without_side_effects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """安全候选必须持久化待审，审核前禁止发券和发送消息。"""
    agent_run_id = uuid.uuid4()
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
    session = MarketingCycleSession(event, campaign)
    side_effects: list[str] = []

    async def generate_content(*_args: object) -> SimpleNamespace:
        return SimpleNamespace(content="安全的弃单提醒", agent_run_id=agent_run_id)

    async def unexpected_side_effect(*_args: object, **_kwargs: object) -> uuid.UUID:
        side_effects.append("called")
        return uuid.uuid4()

    monkeypatch.setattr(marketing_worker, "_generate_ai_content", generate_content)
    monkeypatch.setattr(marketing_worker, "_send_coupon", unexpected_side_effect)
    monkeypatch.setattr(marketing_worker, "_send_message", unexpected_side_effect)
    settings = Settings(
        _env_file=None,
        JWT_SECRET_KEY="test-secret-key-with-32-characters",
        LLM_ENABLED=True,
        AI_MARKETING_ENABLED=True,
    )

    processed = await marketing_worker._execute_due_event(session, datetime.now(UTC), settings)  # noqa: SLF001

    assert processed is True
    assert side_effects == []
    assert event.status == "waiting_review"
    assert event.ai_review_status == "pending"
    assert event.ai_draft_content == "安全的弃单提醒"
    assert event.ai_draft_agent_run_id == agent_run_id
    assert event.next_attempt_at is None
    assert event.completed_at is None
    assert event.tool_call_ids == []


def test_marketing_review_contract_is_explicit_and_does_not_authorize_sending() -> None:
    """批准/拒绝请求只表达人工决策，不携带任何发送指令。"""
    approved = MarketingDraftReview(decision="approve", comment="内容可用")
    assert approved.decision == "approve"
    assert "send" not in approved.model_dump()
    assert "/v1/marketing/events/{event_id}/review" in app.openapi()["paths"]


@pytest.mark.asyncio
async def test_marketing_draft_approval_is_audited_but_never_sends(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """人工批准只改变审核状态并写审计，不产生工具调用 ID。"""
    store_id = uuid.uuid4()
    user = SimpleNamespace(id=uuid.uuid4())
    event = SimpleNamespace(
        id=uuid.uuid4(),
        store_id=store_id,
        status="waiting_review",
        ai_review_status="pending",
        ai_draft_content="待审核文案",
        ai_draft_agent_run_id=uuid.uuid4(),
        ai_reviewed_by=None,
        ai_reviewed_at=None,
        ai_review_idempotency_key=None,
        ai_review_request_hash=None,
        completed_at=None,
        error_code=None,
        tool_call_ids=[],
    )
    session = ReviewSession()

    async def stores(*_args: object) -> set[uuid.UUID]:
        return {store_id}

    async def find(*_args: object) -> SimpleNamespace:
        return event

    async def claim(*_args: object, **kwargs: object) -> SimpleNamespace:
        event.status = str(kwargs["review_status"])
        event.ai_review_status = str(kwargs["review_status"])
        event.ai_reviewed_by = user.id
        event.ai_reviewed_at = kwargs["reviewed_at"]
        event.ai_review_idempotency_key = str(kwargs["idempotency_key"])
        event.ai_review_request_hash = str(kwargs["request_hash"])
        event.completed_at = kwargs["reviewed_at"]
        return event

    monkeypatch.setattr(marketing_service, "allowed_store_ids", stores)
    monkeypatch.setattr(marketing_service, "claim_event_review", claim)
    monkeypatch.setattr(marketing_service, "find_event", find)

    result = await marketing_service.review_marketing_draft(
        session,  # type: ignore[arg-type]
        user,  # type: ignore[arg-type]
        event.id,
        MarketingDraftReview(decision="approve", comment="内容可用"),
    )

    assert result.status == "approved"
    assert result.ai_review_status == "approved"
    assert result.ai_reviewed_by == user.id
    assert result.tool_call_ids == []
    assert session.commit_count == 1
    assert len(session.added) == 1
    audit = session.added[0]
    assert audit.action == "marketing.ai_draft.review"
    assert audit.after_data["send_performed"] is False
    assert "comment_sha256" in audit.after_data


@pytest.mark.asyncio
async def test_sse_disconnect_before_result_marks_delivery_interrupted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """工作流完成后、result 交付前断开，运行记录不能保留单一成功语义。"""
    run_id = uuid.uuid4()
    marked: list[tuple[uuid.UUID, str]] = []
    released: list[uuid.UUID] = []
    user = SimpleNamespace(id=uuid.uuid4())
    request = SimpleNamespace(
        state=SimpleNamespace(trace_id=str(uuid.uuid4())),
        client=SimpleNamespace(host="127.0.0.1"),
        is_disconnected=_always_disconnected,
    )

    async def allow_limits(_request: Request, _user: object) -> None:
        return None

    async def acquire(_user_id: uuid.UUID, _limit: int, _lease_seconds: int) -> str:
        return "test-lease"

    async def release(user_id: uuid.UUID, lease_token: str) -> None:
        assert lease_token == "test-lease"
        released.append(user_id)

    async def suggest(*_args: object, **_kwargs: object) -> SuggestionView:
        return SuggestionView(
            agent_run_id=run_id,
            content="不会被交付的草稿",
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

    async def no_latency(*_args: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr(chat_router, "_enforce_chat_limits", allow_limits)
    monkeypatch.setattr(chat_router, "acquire_chat_stream", acquire)
    monkeypatch.setattr(chat_router, "release_chat_stream", release)
    monkeypatch.setattr(chat_router, "suggest_for_user", suggest)
    monkeypatch.setattr(chat_router, "record_first_output_latency", no_latency)
    monkeypatch.setattr(chat_router, "mark_suggestion_delivery_interrupted", mark)

    response = await chat_router.chat_query(
        ChatQueryRequest(session_id=uuid.uuid4()),
        request,  # type: ignore[arg-type]
        SimpleNamespace(),  # type: ignore[arg-type]
        user,  # type: ignore[arg-type]
    )
    body = "".join([chunk async for chunk in response.body_iterator])

    assert "event: result" not in body
    assert '"reason": "disconnected"' in body
    assert marked == [(run_id, "SSE_DELIVERY_INTERRUPTED")]
    assert released == [user.id]


@pytest.mark.asyncio
async def test_delivery_interruption_preserves_computation_audit_summary() -> None:
    """交付失败覆盖成功终态时，仍保留工作流计算已完成的审计事实。"""
    run = SimpleNamespace(status="succeeded", error_code=None, output_summary="intent=faq")
    session = AgentRunSession(run)

    await mark_suggestion_delivery_interrupted(
        session,  # type: ignore[arg-type]
        uuid.uuid4(),
        "SSE_DELIVERY_CANCELLED",
    )

    assert run.status == "failed"
    assert run.error_code == "SSE_DELIVERY_CANCELLED"
    assert "intent=faq" in run.output_summary
    assert "computation_status=succeeded" in run.output_summary
    assert "delivery_status=interrupted" in run.output_summary
    assert session.commit_count == 1


async def _always_disconnected() -> bool:
    return True
