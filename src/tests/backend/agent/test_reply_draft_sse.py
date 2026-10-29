"""坐席草稿在最终复核结果之前到达，取消和错误仍终止生成。"""

import asyncio
import json
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from agent.test_sse_stream_early_close import _prepare_stream

from app.chat import router as chat_router
from app.chat.schemas import ChatQueryRequest, SuggestionView


def data(frame):
    return json.loads(next(line[6:] for line in frame.splitlines() if line.startswith("data: ")))


@pytest.mark.asyncio
async def test_unverified_draft_precedes_final_and_is_bound_to_one_message(monkeypatch):
    released = []
    user, request = _prepare_stream(monkeypatch, released)
    release = asyncio.Event()
    trigger = uuid.uuid4()
    called = []

    async def suggest(*args, reply_progress, **kwargs):
        called.append(args)
        assert reply_progress.reply_plan
        await reply_progress.on_draft(0, "A partial draft")
        await release.wait()
        return SuggestionView(
            agent_run_id=uuid.uuid4(),
            content="A reviewed reply.",
            reply_parts=["A reviewed reply."],
            trigger_message_id=trigger,
            intent=None,
            confidence=0,
            action="human_review",
            terminal_state="human_review",
            requires_human=True,
            transfer_performed=False,
            citations=[],
            trace_id="test",
        )

    monkeypatch.setattr(chat_router, "suggest_for_user", suggest)
    monkeypatch.setattr(chat_router, "record_first_output_latency", AsyncMock())
    response = await chat_router.chat_query(
        ChatQueryRequest(session_id=uuid.uuid4(), trigger_message_id=trigger, reply_mode="review_plan"),
        request,
        SimpleNamespace(),
        user,
    )
    frames = []
    while True:
        frame = await asyncio.wait_for(anext(response.body_iterator), 2)
        frames.append(frame)
        if "event: draft\n" in frame:
            break
    assert len(called) == 1 and not release.is_set()
    payload = data(frames[-1])
    assert (
        payload["text"] == "A partial draft"
        and payload["sendable"] is False
        and payload["unverified"] is True
        and payload["trigger_message_id"] == str(trigger)
    )
    release.set()
    rest = [x async for x in response.body_iterator]
    result = data(next(x for x in rest if "event: result\n" in x))
    assert result["reply_parts"] == ["A reviewed reply."] and result["send_performed"] is False
    assert released == [user.id]


@pytest.mark.asyncio
async def test_closing_operator_stream_cancels_generation_without_sending(monkeypatch):
    released = []
    user, request = _prepare_stream(monkeypatch, released)
    cancelled = asyncio.Event()

    async def suggest(*args, reply_progress, **kwargs):
        try:
            await reply_progress.on_draft(0, "Pending review")
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    monkeypatch.setattr(chat_router, "suggest_for_user", suggest)
    response = await chat_router.chat_query(
        ChatQueryRequest(session_id=uuid.uuid4(), reply_mode="review_plan"), request, SimpleNamespace(), user
    )
    while "event: draft\n" not in await asyncio.wait_for(anext(response.body_iterator), 2):
        pass
    await response.body_iterator.aclose()
    assert cancelled.is_set() and released == [user.id]
