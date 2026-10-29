"""顺序交付状态机；先持久化未知状态，再进入外部写入。"""

import hashlib
import uuid
from collections.abc import Awaitable, Callable
from copy import deepcopy
from typing import Literal, Protocol, cast

from app.agents.delivery.contracts import ReplyBatchRequest, ReplyBatchView, ReplyPart, ReplyPartResult
from app.shared.exceptions.errors import AppError, ErrorCode
from app.workspace.delivery_errors import DeliveryNotStarted
from app.workspace.schemas import MessageView

BatchState = dict[str, object]
PartState = dict[str, object]


def request_hash(payload: ReplyBatchRequest) -> str:
    return hashlib.sha256(payload.model_dump_json().encode()).hexdigest()


def new_state(payload: ReplyBatchRequest) -> BatchState:
    return {
        "id": str(uuid.uuid4()),
        "request_hash": request_hash(payload),
        "preview_only": payload.preview_only,
        "parts": [
            {
                "index": index,
                "kind": part.kind,
                "status": "previewed" if payload.preview_only else "pending",
                "attempt": 0,
                "message_id": None,
                "error_code": None,
            }
            for index, part in enumerate(payload.parts)
        ],
        "messages": [],
    }


def view(state: BatchState) -> ReplyBatchView:
    parts = [ReplyPartResult.model_validate(part) for part in cast(list[object], state["parts"])]
    statuses = {part.status for part in parts}
    status: str = (
        "previewed"
        if state["preview_only"]
        else "unknown"
        if "unknown" in statuses
        else "completed"
        if statuses == {"sent"}
        else "partial"
        if "sent" in statuses
        else "failed"
    )
    return ReplyBatchView(
        id=uuid.UUID(cast(str, state["id"])),
        preview_only=bool(state["preview_only"]),
        status=cast("Literal['previewed', 'completed', 'partial', 'failed', 'unknown']", status),
        parts=parts,
        messages=[MessageView.model_validate(value) for value in cast(list[object], state["messages"])],
    )


class BatchStore(Protocol):
    async def start(self, scope: str, key: str, payload: ReplyBatchRequest) -> BatchState: ...
    async def read(self, scope: str, key: str) -> BatchState: ...
    async def claim(self, scope: str, key: str, index: int) -> str | None: ...
    async def finish(self, scope: str, key: str, index: int, attempt_key: str, message: MessageView) -> None: ...
    async def reject(self, scope: str, key: str, index: int, attempt_key: str, code: str) -> None: ...


def check_request(state: BatchState, payload: ReplyBatchRequest) -> None:
    if state["request_hash"] != request_hash(payload):
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "幂等键已用于其他交付计划", 409)


def claim_part(state: BatchState, index: int) -> str | None:
    parts = cast(list[PartState], state["parts"])
    part = parts[index]
    if state["preview_only"] or part["status"] not in {"pending", "failed"}:
        return None
    if any(previous["status"] != "sent" for previous in parts[:index]):
        return None
    part["attempt"] = int(cast(int, part["attempt"])) + 1
    # 未知状态先提交，进程中断或客户端取消也不会重发可能已写入的平台消息。
    part["status"] = "unknown"
    part["error_code"] = "DELIVERY_RESULT_UNKNOWN"
    return f"reply:{state['id']}:{index}:{part['attempt']}"


def finish_part(state: BatchState, index: int, attempt_key: str, message: MessageView) -> None:
    part = cast(list[PartState], state["parts"])[index]
    if attempt_key != f"reply:{state['id']}:{index}:{part['attempt']}" or part["status"] != "unknown":
        # 对账可能已经推进到下一次明确重试；迟到的上次结果不能覆盖新领取状态。
        return
    part.update(
        status=message.status if message.status in {"sent", "failed"} else "unknown",
        message_id=str(message.id),
        error_code=message.error_code,
    )
    messages = cast(list[dict[str, object]], state["messages"])
    # 重试只保留本段最新结果，不能把失败的旧消息混入待展示成功序列。
    messages[:] = [value for value in messages if value.get("index") != index]
    messages.append({**message.model_dump(mode="json"), "index": index})


def reject_part(state: BatchState, index: int, attempt_key: str, code: str) -> None:
    part = cast(list[PartState], state["parts"])[index]
    if attempt_key == f"reply:{state['id']}:{index}:{part['attempt']}" and part["status"] == "unknown":
        part.update(status="failed", message_id=None, error_code=code)


class MemoryBatchStore:
    """无外部副作用的状态机替身；HTTP生产入口使用SQL持久化。"""

    def __init__(self) -> None:
        self.states: dict[tuple[str, str], BatchState] = {}

    async def start(self, scope: str, key: str, payload: ReplyBatchRequest) -> BatchState:
        state = self.states.setdefault((scope, key), new_state(payload))
        check_request(state, payload)
        return deepcopy(state)

    async def read(self, scope: str, key: str) -> BatchState:
        return deepcopy(self.states[(scope, key)])

    async def claim(self, scope: str, key: str, index: int) -> str | None:
        return claim_part(self.states[(scope, key)], index)

    async def finish(self, scope: str, key: str, index: int, attempt_key: str, message: MessageView) -> None:
        finish_part(self.states[(scope, key)], index, attempt_key, message)

    async def reject(self, scope: str, key: str, index: int, attempt_key: str, code: str) -> None:
        reject_part(self.states[(scope, key)], index, attempt_key, code)


class BatchRunner:
    def __init__(self, store: BatchStore, send: Callable[[ReplyPart, str], Awaitable[MessageView]]) -> None:
        self.store, self.send = store, send

    async def run(self, scope: str, key: str, payload: ReplyBatchRequest) -> ReplyBatchView:
        state = await self.store.start(scope, key, payload)
        if payload.preview_only:
            return view(state)
        for index, part in enumerate(payload.parts):
            attempt = await self.store.claim(scope, key, index)
            if attempt is None:
                current = view(await self.store.read(scope, key))
                if current.parts[index].status == "sent":
                    continue
                return current
            try:
                result = await self.send(part, attempt)
            except DeliveryNotStarted as error:
                await self.store.reject(scope, key, index, attempt, error.code.value)
                return view(await self.store.read(scope, key))
            except Exception:
                # 未证实是否写入的平台错误保留unknown；异常内容不能进入审阅栏或日志。
                return view(await self.store.read(scope, key))
            await self.store.finish(scope, key, index, attempt, result)
            if result.status != "sent":
                break
        return view(await self.store.read(scope, key))
