"""有序人工交付：前序成功不重发，未知结果不盲重试。"""

import asyncio
import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.agents.delivery.batches import BatchRunner, MemoryBatchStore
from app.agents.delivery.contracts import ReplyBatchRequest
from app.workspace.schemas import MessageView


def request(**updates):
    return ReplyBatchRequest.model_validate(
        {
            "preview_only": False,
            "confirmed": True,
            "parts": [
                {"kind": "text", "content": "Your parcel was delivered."},
                {"kind": "logistics_card", "order_id": "600001", "package_id": "123"},
            ],
            **updates,
        }
    )


def message(status):
    return MessageView(
        id=uuid.uuid4(),
        role="assistant",
        content="Reviewed",
        status=status,
        created_at=datetime.now(UTC),
        error_code=None,
        delivery_mode="mock",
    )


@pytest.mark.asyncio
async def test_card_retry_uses_new_attempt_but_never_repeats_successful_text():
    store = MemoryBatchStore()
    calls = []

    async def send(part, key):
        calls.append((part.kind, key))
        return message("failed" if len(calls) == 2 else "sent")

    runner = BatchRunner(store, send)
    first = await runner.run("scope", "key", request())
    assert first.status == "partial"
    second = await runner.run("scope", "key", request())
    assert second.status == "completed"
    assert [kind for kind, _ in calls] == ["text", "logistics_card", "logistics_card"]
    assert calls[1][1] != calls[2][1]
    assert len((await runner.run("scope", "key", request())).messages) == 2
    assert len(calls) == 3


@pytest.mark.asyncio
async def test_unknown_or_cancelled_send_blocks_later_parts_and_duplicate():
    entered = asyncio.Event()
    calls = []

    async def send(part, key):
        calls.append(key)
        entered.set()
        await asyncio.Event().wait()

    runner = BatchRunner(MemoryBatchStore(), send)
    task = asyncio.create_task(runner.run("scope", "key", request()))
    await entered.wait()
    assert (await runner.run("scope", "key", request())).status == "unknown"
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert (await runner.run("scope", "key", request())).status == "unknown"
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_preview_never_calls_sender_and_cannot_be_reused_for_actual_send():
    async def send(*_):
        raise AssertionError("preview sent a message")

    runner = BatchRunner(MemoryBatchStore(), send)
    assert (await runner.run("scope", "key", request(preview_only=True, confirmed=False))).status == "previewed"
    from app.shared.exceptions.errors import AppError

    with pytest.raises(AppError):
        await runner.run("scope", "key", request())


@pytest.mark.parametrize(
    "updates",
    [
        {"confirmed": 1},
        {"confirmed": False},
        {"parts": [{"kind": "text", "content": "😀" * 1001}]},
        {"parts": [{"kind": "logistics_card", "order_id": "6"}, {"kind": "text", "content": "late"}]},
    ],
)
def test_boundary_rejects_unconfirmed_oversized_or_unordered_parts(updates):
    with pytest.raises(ValidationError):
        request(**updates)


@pytest.mark.asyncio
async def test_late_previous_attempt_cannot_overwrite_current_unknown_claim():
    store = MemoryBatchStore()
    payload = request(parts=[{"kind": "text", "content": "Delivered"}])
    await store.start("scope", "key", payload)
    first = await store.claim("scope", "key", 0)
    await store.finish("scope", "key", 0, first, message("failed"))
    second = await store.claim("scope", "key", 0)
    await store.finish("scope", "key", 0, first, message("failed"))
    assert await store.claim("scope", "key", 0) is None
    await store.finish("scope", "key", 0, second, message("sent"))
    assert (await store.read("scope", "key"))["parts"][0]["status"] == "sent"


@pytest.mark.asyncio
async def test_known_not_started_can_retry_but_other_platform_errors_stay_unknown():
    from app.workspace.delivery_errors import DeliveryNotStarted
    from app.shared.exceptions.errors import ErrorCode

    calls = []

    async def send(part, key):
        calls.append(key)
        if len(calls) == 1:
            raise DeliveryNotStarted(ErrorCode.RESOURCE_CONFLICT, "先核对另一条消息", 409)
        return message("sent")

    runner = BatchRunner(MemoryBatchStore(), send)
    first = await runner.run("scope", "key", request())
    assert first.status == "failed" and first.parts[0].message_id is None
    assert (await runner.run("scope", "key", request())).status == "completed"
    assert calls[0] != calls[1]
