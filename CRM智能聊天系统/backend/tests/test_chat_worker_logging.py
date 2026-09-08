"""Agent Worker 关键失败日志的结构化事件测试。"""

import json
import logging
import uuid
from io import StringIO
from types import SimpleNamespace

import pytest

from app.chat import worker
from app.shared.logging.setup import JsonFormatter, TraceIdFilter


class FakeSession:
    """只实现 ``process_one`` 异常分支使用的会话契约。"""

    def __init__(self, task: SimpleNamespace) -> None:
        self.task = task

    async def rollback(self) -> None:
        return None

    async def get(self, *_args: object, **_kwargs: object) -> SimpleNamespace:
        return self.task

    async def commit(self) -> None:
        return None


class FakeSessionContext:
    """提供异步上下文管理器，避免测试连接数据库。"""

    def __init__(self, session: FakeSession) -> None:
        self.session = session

    async def __aenter__(self) -> FakeSession:
        return self.session

    async def __aexit__(self, *_args: object) -> None:
        return None


@pytest.mark.asyncio
async def test_agent_task_failure_emits_stable_json_event(monkeypatch: pytest.MonkeyPatch) -> None:
    """自动任务异常必须输出可告警事件，不能退化为无语义占位符。"""
    trace_id = str(uuid.uuid4())
    task = SimpleNamespace(
        id=uuid.uuid4(),
        trace_id=trace_id,
        attempt_count=1,
        status="processing",
        error_code=None,
        next_attempt_at=None,
        processed_at=None,
    )
    session = FakeSession(task)

    async def fake_claim_task(_session: FakeSession, _settings: SimpleNamespace) -> SimpleNamespace:
        return task

    async def fail_process_task(*_args: object) -> None:
        raise ValueError("customer-message-sentinel")

    monkeypatch.setattr(worker, "session_factory", lambda: FakeSessionContext(session))
    monkeypatch.setattr(worker, "claim_task", fake_claim_task)
    monkeypatch.setattr(worker, "process_task", fail_process_task)

    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.addFilter(TraceIdFilter())
    handler.setFormatter(JsonFormatter())
    logger = worker.logger
    previous_handlers = logger.handlers[:]
    previous_level = logger.level
    previous_propagate = logger.propagate
    logger.handlers = [handler]
    logger.setLevel(logging.ERROR)
    logger.propagate = False
    try:
        processed = await worker.process_one(SimpleNamespace(auto_reply_max_attempts=3))
    finally:
        logger.handlers = previous_handlers
        logger.setLevel(previous_level)
        logger.propagate = previous_propagate

    payload = json.loads(stream.getvalue())
    assert processed is True
    assert payload["event"] == "agent_task_failed"
    assert payload["message"] == "agent_task_failed"
    assert payload["trace_id"] == trace_id
    assert payload["error_code"] == "ValueError"
    assert "customer-message-sentinel" not in stream.getvalue()
