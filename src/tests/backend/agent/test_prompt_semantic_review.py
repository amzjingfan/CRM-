"""运营规则由模型语义复核；程序只校验结构化结论及发布事务边界。"""

import asyncio
import time
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.agents.providers.tool_calling import FunctionCall, ToolTurn
from app.shared.exceptions.errors import AppError, ErrorCode


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome,status", [("safe", None), ("private_values", 422), ("uncertain", 422)])
async def test_semantic_verdict_controls_publication_without_keyword_matching(outcome, status):
    from app.agents.prompts.review import review_prompt_configuration

    provider = SimpleNamespace(
        complete=AsyncMock(
            return_value=ToolTurn(
                None,
                (
                    FunctionCall(
                        "review",
                        "review_agent_prompt_configuration",
                        {
                            "privacy_reviewed": True,
                            "outcome": outcome,
                        },
                    ),
                ),
                {},
                7,
                3,
            )
        )
    )
    call = review_prompt_configuration(
        sections={"tool_rules": "订单号、内部引用、时间时区和公共物流城市是不同字段。"},
        provider=provider,
        deadline=time.monotonic() + 2,
        max_output_tokens=900,
    )
    if status is None:
        assert await call == (7, 3)
    else:
        with pytest.raises(AppError) as error:
            await call
        assert error.value.status_code == status
    assert provider.complete.await_args.kwargs["max_output_tokens"] == 900


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "arguments",
    [
        {},
        {"privacy_reviewed": False, "outcome": "safe"},
        {"privacy_reviewed": True, "outcome": "allow_anything"},
    ],
)
async def test_missing_or_invalid_review_is_not_treated_as_approval(arguments):
    from app.agents.prompts.review import review_prompt_configuration

    provider = SimpleNamespace(
        complete=AsyncMock(
            return_value=ToolTurn(
                None,
                (FunctionCall("review", "review_agent_prompt_configuration", arguments),),
                {},
                0,
                0,
            )
        )
    )
    with pytest.raises(AppError) as error:
        await review_prompt_configuration(
            sections={"identity": "规则"},
            provider=provider,
            deadline=time.monotonic() + 2,
            max_output_tokens=900,
        )
    assert error.value.status_code == 503


@pytest.mark.asyncio
async def test_review_deadline_and_request_cancellation_do_not_allow_publication():
    from app.agents.prompts.review import review_prompt_configuration

    started = asyncio.Event()

    async def complete(**_kwargs):
        started.set()
        await asyncio.Future()

    provider = SimpleNamespace(complete=complete)
    with pytest.raises(AppError) as error:
        await review_prompt_configuration(
            sections={"identity": "规则"},
            provider=provider,
            deadline=time.monotonic() + 0.01,
            max_output_tokens=900,
        )
    assert error.value.status_code == 504
    task = asyncio.create_task(
        review_prompt_configuration(
            sections={"identity": "规则"},
            provider=provider,
            deadline=time.monotonic() + 3,
            max_output_tokens=900,
        )
    )
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_rejected_semantic_review_does_not_change_published_version(monkeypatch):
    from app.agents.management import service
    from app.agents.management.config_models import AgentConfig
    from app.agents.prompts.sections import legacy_safe_sections

    config = AgentConfig(
        id=uuid.uuid4(),
        store_id=uuid.uuid4(),
        name="测试",
        code="test",
        draft_revision=2,
        published_version=1,
        draft_model_provider="deepseek",
        draft_model_name="configured",
        draft_prompt_sections=legacy_safe_sections(),
    )
    session = SimpleNamespace(scalar=AsyncMock(return_value=config), add=Mock(), commit=AsyncMock())
    monkeypatch.setattr(service, "get_settings", lambda: SimpleNamespace())
    monkeypatch.setattr(service, "validate_tool_model", lambda *_: None)
    monkeypatch.setattr(
        service,
        "review_configured_prompt",
        AsyncMock(side_effect=AppError(ErrorCode.VALIDATION_ERROR, "语义复核不通过", 422)),
    )
    with pytest.raises(AppError):
        await service.publish_agent(
            session,
            store_id=config.store_id,
            config_id=config.id,
            expected_revision=2,
            publisher_id=None,
        )
    assert config.published_version == 1 and config.draft_revision == 2
    session.add.assert_not_called()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_late_model_approval_cannot_publish_after_its_deadline():
    from app.agents.prompts.review import review_prompt_configuration

    async def complete(**_kwargs):
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            return ToolTurn(
                None,
                (
                    FunctionCall(
                        "review",
                        "review_agent_prompt_configuration",
                        {
                            "privacy_reviewed": True,
                            "outcome": "safe",
                        },
                    ),
                ),
                {},
                2,
                1,
            )

    with pytest.raises(AppError) as error:
        await review_prompt_configuration(
            sections={"identity": "规则"},
            provider=SimpleNamespace(complete=complete),
            deadline=time.monotonic() + 0.01,
            max_output_tokens=900,
        )
    assert error.value.status_code == 504
