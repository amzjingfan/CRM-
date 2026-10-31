"""只供已授权坐席查看的调试草稿流；终态仍以完整复核结果为准。"""

import asyncio
import json
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import suppress

import anyio

from app.agents.delivery.reply_parts import DraftPartSink
from app.agents.management.schemas import AgentDebugView
from app.shared.exceptions.errors import AppError


async def stream_debug_events(
    run: Callable[[DraftPartSink], Awaitable[AgentDebugView]], *, trace_id: str
) -> AsyncGenerator[str, None]:
    drafts: asyncio.Queue[tuple[int, str]] = asyncio.Queue(maxsize=64)

    async def on_draft(index: int, text: str) -> None:
        # 每条事件是完整快照，慢客户端只保留近期草稿，不无限堆积。
        if drafts.full():
            drafts.get_nowait()
        drafts.put_nowait((index, text))

    def event(name: str, payload: dict[str, object]) -> str:
        return f"event: {name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"

    async def workflow() -> AgentDebugView:
        return await run(on_draft)

    task = asyncio.create_task(workflow())
    try:
        yield event("accepted", {"trace_id": trace_id})
        while True:
            await asyncio.wait({task}, timeout=0.25)
            while not drafts.empty():
                index, text = drafts.get_nowait()
                yield event("draft", {"part_index": index, "text": text, "unverified": True, "sendable": False})
            if task.done():
                break
            yield ": keepalive\n\n"
        result = await task
        yield event("result", result.model_dump(mode="json"))
    except AppError as error:
        yield event("error", {"code": error.code, "message": error.message, "trace_id": trace_id})
    except Exception:
        # 第三方异常内容可能带凭据/买家正文，不向浏览器透出。
        yield event("error", {"message": "Agent 动态调试失败", "trace_id": trace_id})
    finally:
        # ASGI 断连会在每次 await 再次取消；必须等取消审计落库后才关闭流。
        with anyio.CancelScope(shield=True):
            if not task.done():
                task.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await task
    yield event("done", {"trace_id": trace_id})
