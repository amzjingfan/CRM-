"""批次边界 DTO、后台生命周期与低敏失败策略。"""

import asyncio
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from app.agents.management.templates.batch_schemas import BatchConfirmation
from app.agents.management.templates.processor import TemplateBatchProcessor
from app.shared.config.settings import get_settings


def test_confirmation_requires_exact_json_true_and_forbids_extra():
    for confirmation in (False, 1, "true"):
        with pytest.raises(ValidationError):
            BatchConfirmation(preview_id=uuid.uuid4(), confirmation=confirmation)
    with pytest.raises(ValidationError):
        BatchConfirmation(preview_id=uuid.uuid4(), confirmation=True, config={})


async def test_processor_loop_drains_work_without_extra_poll_and_stop_cancels():
    processor = TemplateBatchProcessor(None, SimpleNamespace(agent_template_processor_poll_seconds=0.001))
    entered = asyncio.Event()
    calls = 0

    async def once():
        nonlocal calls
        calls += 1
        if calls < 3:
            return True
        entered.set()
        await asyncio.Event().wait()

    processor.run_once = once
    processor.start()
    await asyncio.wait_for(entered.wait(), 1)
    task = processor._task
    await processor.stop()
    assert calls == 3 and task.cancelled() and processor._task is None
    await processor.stop()


async def test_disabled_and_short_lifespan_do_not_poll():
    processor = TemplateBatchProcessor(
        None, get_settings().model_copy(update={"agent_template_processor_enabled": False})
    )
    processor.run_once = AsyncMock()
    processor.start()
    assert processor._task is None
    processor = TemplateBatchProcessor(None, get_settings())
    processor.run_once = AsyncMock()
    processor.start()
    await processor.stop()
    processor.run_once.assert_not_awaited()


async def test_main_lifespan_stops_processor_then_all_existing_resources(monkeypatch):
    from app import main

    events = []

    class Processor:
        def __init__(self, *_):
            pass

        def start(self):
            events.append("start")

        async def stop(self):
            events.append("stop")

    async def close_runtime():
        events.append("runtime")

    async def close_http():
        events.append("http")

    async def dispose():
        events.append("engine")

    monkeypatch.setattr(main, "TemplateBatchProcessor", Processor)
    monkeypatch.setattr(main, "build_shared_agent_runtime", lambda _: SimpleNamespace(aclose=close_runtime))
    monkeypatch.setattr(main, "close_tiktok_read_http_pool", close_http)
    monkeypatch.setattr(main, "engine", SimpleNamespace(dispose=dispose))
    async with main.lifespan(main.app):
        assert events == ["start"]
    assert events == ["start", "stop", "runtime", "http", "engine"]
    assert main.app.state.agent_runtime is None and main.app.state.template_batch_processor is None
