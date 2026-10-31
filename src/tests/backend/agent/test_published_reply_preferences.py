"""回复偏好必须冻结于版本，并贯穿表达策略及内部翻译边界。"""

import asyncio
import json
import time
import uuid
from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.agents.core.reply_policy import AgentReplyProfile
from app.agents.management import repository
from app.agents.management.models import AgentConfigVersion
from app.agents.management.service import config_snapshot, running_snapshot, version_snapshot


def _config():
    return SimpleNamespace(
        id=uuid.uuid4(),
        store_id=uuid.uuid4(),
        name="draft",
        code="service",
        description=None,
        enabled_tools=[],
        knowledge_scope={
            "agent_type": "service",
            "file_ids": [],
            "reply_profile": {"tone": "concise", "reply_language": "en"},
        },
        draft_model_provider="deepseek",
        draft_model_name="deepseek-chat",
        draft_prompt_sections={},
    )


def _version(config):
    return AgentConfigVersion(
        agent_config_id=config.id,
        store_id=config.store_id,
        version=2,
        name="published",
        code="service",
        description=None,
        agent_type="service",
        model_provider="deepseek",
        model_name="deepseek-chat",
        prompt_sections={},
        prompt_hash="hash",
        tool_names=[],
        file_ids=[],
        ready_for_v2=True,
    )


def test_published_profile_is_frozen_and_draft_is_not_runtime_fallback():
    config = _config()
    version = _version(config)
    version.reply_profile = {"tone": "professional", "reply_language": "zh-CN", "operator_language": "en"}
    agent = repository._project(config, version)
    config.knowledge_scope["reply_profile"]["reply_language"] = "auto"
    assert agent.reply_profile == AgentReplyProfile(tone="professional", reply_language="zh-CN", operator_language="en")
    assert version_snapshot(version)["reply_profile"] == version.reply_profile
    version.reply_profile = None
    assert repository._project(config, version).reply_profile is None


def test_reply_profile_change_is_a_runtime_publication_change():
    config = _config()
    first = config_snapshot(config)
    config.knowledge_scope["reply_profile"]["reply_language"] = "zh-CN"
    assert running_snapshot(first) != running_snapshot(config_snapshot(config))


@pytest.mark.parametrize("tone", ["friendly", "professional", "concise", "empathetic"])
@pytest.mark.parametrize("language", ["auto", "zh-CN", "en"])
def test_compiled_policy_enforces_finite_preferences_without_operator_prose(tone, language):
    from app.agents.core.reply_policy import compile_reply_policy

    policy = compile_reply_policy(AgentReplyProfile(tone=tone, reply_language=language, operator_language="en"))
    assert tone in policy
    assert language in policy
    assert "买家正文" in policy
    assert "坐席" in policy


def test_multi_agent_conflicts_are_order_independent_and_explicit_primary_wins():
    from app.agents.core.reply_policy import resolve_published_reply_profile

    config = _config()
    agent = repository._project(config, _version(config))
    first = replace(agent, reply_profile=AgentReplyProfile(reply_language="en", operator_language="en"))
    second = replace(agent, id=uuid.uuid4(), reply_profile=AgentReplyProfile(reply_language="zh-CN"))
    resolved = resolve_published_reply_profile((first, second))
    assert resolved == resolve_published_reply_profile((second, first))
    assert resolved.profile.reply_language == "auto"
    assert resolved.operator_language is None
    assert resolved.source == "conflict_follow_question"
    primary = resolve_published_reply_profile((second, first), primary_agent_id=first.id)
    assert primary.profile == first.reply_profile
    assert primary.operator_language == "en"
    assert resolve_published_reply_profile((agent,)).profile is None


@pytest.mark.asyncio
@pytest.mark.parametrize("reply_plan", [False, True])
@pytest.mark.parametrize("translation_fails", [False, True])
async def test_published_preferences_reach_aggregate_and_final_review(reply_plan, translation_fails):
    from agent._review_helpers import accepted_review_turn

    from app.agents.orchestration.coordinator import SpecialistResult
    from app.agents.orchestration.service import RunProgress, execute_dynamic_run
    from app.agents.providers.tool_calling import FunctionCall, ToolTurn
    from app.agents.runtime.snapshot import RunSnapshot

    config = _config()
    agent = replace(
        repository._project(config, _version(config)),
        reply_profile=AgentReplyProfile(
            tone="concise", reply_language="en", operator_language="zh-CN" if translation_fails else "en"
        ),
    )
    now = datetime.now(UTC)
    snapshot = RunSnapshot(
        config.store_id, uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), now, (), (agent,), (), 0, now, "hash"
    )
    router = SimpleNamespace(
        complete=AsyncMock(
            return_value=ToolTurn(
                None,
                (
                    FunctionCall(
                        "route",
                        "route_agents",
                        {
                            "question_language": "en",
                            "selections": [{"agent_id": str(agent.id), "subquestion": "shipping"}],
                        },
                    ),
                ),
                {},
                1,
                1,
            )
        )
    )
    policies = []

    async def generate(*, messages, tools, max_output_tokens):
        if tools and tools[0].name == "submit_operator_translation":
            raise RuntimeError("synthetic translation failure")
        payload = json.loads(messages[-1]["content"])
        policies.append(payload["published_output_policies"])
        if tools and tools[0].name == "review_answer_evidence":
            return accepted_review_turn(messages)
        if tools:
            return ToolTurn(None, (FunctionCall("parts", "submit_reply_parts", {"texts": ["Shipped."]}),), {}, 1, 1)
        return ToolTurn("Shipped.", (), {}, 1, 1)

    async def worker(selection):
        return SpecialistResult(selection.agent_id, "Shipped.", verified_facts={"status": "shipped"})

    result = await execute_dynamic_run(
        question="Where is my order?",
        snapshot=snapshot,
        router=router,
        aggregator=SimpleNamespace(complete=generate),
        worker=worker,
        deadline=time.monotonic() + 3,
        max_catalog_tokens=1000,
        progress=RunProgress(reply_plan=reply_plan),
    )
    assert result.suggestion.content == "Shipped."
    assert result.suggestion.customer_translation is None
    assert result.suggestion.customer_translation_error_code == (
        "translation_unavailable" if translation_fails else None
    )
    assert result.reason_code is None
    assert all(any("concise" in item and "en" in item for item in policy) for policy in policies)


@pytest.mark.asyncio
@pytest.mark.parametrize("operator", ["zh-CN", "en"])
async def test_internal_translation_is_separate_reviewed_and_tracks_usage(operator):
    from agent._review_helpers import accepted_review_turn

    from app.agents.providers.tool_calling import FunctionCall, ToolTurn
    from app.agents.runtime.operator_translation import translate_for_operator

    source = "en" if operator == "zh-CN" else "zh-CN"
    translated = "已发货。" if operator == "zh-CN" else "Shipped."
    usage = []

    async def generate(*, messages, tools, max_output_tokens):
        if tools[0].name == "review_answer_evidence":
            return accepted_review_turn(messages)
        assert json.loads(messages[-1]["content"])["target_language"] == operator
        return ToolTurn(
            None,
            (
                FunctionCall(
                    "translate",
                    "submit_operator_translation",
                    {
                        "message_translation": translated,
                        "draft_translation": translated,
                    },
                ),
            ),
            {},
            3,
            4,
        )

    result = await translate_for_operator(
        question="Where is it?",
        answer="Shipped.",
        question_language=source,
        reply_language=source,
        operator_language=operator,
        trigger_message_id=uuid.uuid4(),
        provider=SimpleNamespace(complete=generate),
        provider_name="test",
        model_name="test",
        deadline=time.monotonic() + 3,
        on_usage=lambda i, o: usage.append((i, o)),
    )
    assert result.translation.target_language == operator
    assert result.translation.draft_translation == translated
    assert result.error_code is None
    assert sum(i for i, _ in usage) == result.input_tokens == 7


@pytest.mark.asyncio
async def test_same_language_operator_translation_does_not_call_model():
    from app.agents.runtime.operator_translation import translate_for_operator

    provider = SimpleNamespace(complete=AsyncMock())
    result = await translate_for_operator(
        question="Hello",
        answer="Hello",
        question_language="en",
        reply_language="en",
        operator_language="en",
        trigger_message_id=uuid.uuid4(),
        provider=provider,
        provider_name="test",
        model_name="test",
        deadline=time.monotonic() + 3,
    )
    assert result.translation is None and result.error_code is None
    provider.complete.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [TimeoutError(), ValueError("synthetic invalid")])
async def test_internal_translation_failure_preserves_error_metadata(failure):
    from app.agents.runtime.operator_translation import translate_for_operator

    result = await translate_for_operator(
        question="Hello",
        answer="Hello",
        question_language="en",
        reply_language="en",
        operator_language="zh-CN",
        trigger_message_id=uuid.uuid4(),
        provider=SimpleNamespace(complete=AsyncMock(side_effect=failure)),
        provider_name="test",
        model_name="test",
        deadline=time.monotonic() + 3,
    )
    assert result.translation is None
    assert result.error_code == (
        "deadline_exceeded" if isinstance(failure, TimeoutError) else "translation_unavailable"
    )


@pytest.mark.asyncio
async def test_debug_stream_keeps_internal_translation_out_of_buyer_content():
    from app.agents.core.translation import TranslationBundleResult
    from app.agents.management.debug_stream import stream_debug_events
    from app.agents.management.schemas import AgentDebugView

    translation = TranslationBundleResult(
        trigger_message_id=uuid.uuid4(),
        source_text_sha256="a" * 64,
        source_language="en",
        target_language="zh-CN",
        message_translation="包裹在哪？",
        draft_translation="已发货。",
        prompt_version="test",
        provider="test",
        model="test",
        input_tokens=2,
        output_tokens=2,
        latency_ms=1,
    )

    async def run(on_draft):
        await on_draft(0, "Shipped.")
        return AgentDebugView(
            agent_run_id=uuid.uuid4(),
            content="Shipped.",
            action="human_review",
            terminal_state="review_ready",
            citations=[],
            tool_calls=[],
            trace_id="test",
            customer_translation=translation,
        )

    events = [event async for event in stream_debug_events(run, trace_id="test")]
    result = json.loads(next(item for item in events if item.startswith("event: result")).split("data: ", 1)[1])
    assert result["content"] == "Shipped."
    assert result["customer_translation"]["draft_translation"] == "已发货。"
    assert "已发货" not in next(item for item in events if item.startswith("event: draft"))


@pytest.mark.asyncio
async def test_outer_run_deadline_during_translation_preserves_reviewed_buyer_answer():
    from app.agents.runtime.operator_translation import translate_for_operator

    async def slow(**kwargs):
        await asyncio.sleep(1)

    deadline = time.monotonic() + 0.01
    async with asyncio.timeout_at(deadline) as run_timeout:
        result = await translate_for_operator(
            question="Hello",
            answer="Hello",
            question_language="en",
            reply_language="en",
            operator_language="zh-CN",
            trigger_message_id=uuid.uuid4(),
            provider=SimpleNamespace(complete=slow),
            provider_name="test",
            model_name="test",
            deadline=deadline,
            run_timeout=run_timeout,
        )
    assert result.error_code == "deadline_exceeded"


@pytest.mark.asyncio
@pytest.mark.parametrize("remaining", [-0.01, 3])
async def test_operator_translation_propagates_explicit_cancel_even_after_deadline(remaining):
    from app.agents.runtime.operator_translation import translate_for_operator

    with pytest.raises(asyncio.CancelledError):
        await translate_for_operator(
            question="Hello",
            answer="Hello",
            question_language="en",
            reply_language="en",
            operator_language="zh-CN",
            trigger_message_id=uuid.uuid4(),
            provider=SimpleNamespace(complete=AsyncMock(side_effect=asyncio.CancelledError())),
            provider_name="test",
            model_name="test",
            deadline=time.monotonic() + remaining,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["unsupported", "rewrite"])
async def test_regeneration_and_output_rewrite_keep_published_preferences(mode):
    from agent._review_helpers import accepted_review_turn

    from app.agents.core.reply_policy import compile_reply_policy
    from app.agents.orchestration.aggregator import aggregate_results
    from app.agents.orchestration.coordinator import SpecialistResult
    from app.agents.providers.tool_calling import FunctionCall, ToolTurn

    policy = compile_reply_policy(AgentReplyProfile(tone="professional", reply_language="en"))
    seen = []
    reviews = 0
    generations = 0

    async def generate(*, messages, tools, max_output_tokens):
        nonlocal reviews, generations
        payload = json.loads(messages[-1]["content"])
        assert policy in payload["published_output_policies"]
        seen.append(payload)
        if tools:
            reviews += 1
            if reviews == 1:
                turn = accepted_review_turn(messages)
                args = dict(turn.calls[0].arguments)
                if mode == "unsupported":
                    args.update(supported=False, reason_code="unsupported", evidence_ids=[])
                else:
                    args["output_rewrite_required"] = True
                return replace(turn, calls=(FunctionCall("review", "review_answer_evidence", args),))
            return accepted_review_turn(messages)
        generations += 1
        return ToolTurn("Initial draft" if generations == 1 else "Shipped.", (), {}, 1, 1)

    result = await aggregate_results(
        question="订单在哪？",
        results=(SpecialistResult(uuid.uuid4(), "草稿", verified_facts={"status": "shipped"}),),
        provider=SimpleNamespace(complete=generate),
        deadline=time.monotonic() + 3,
        store_id=uuid.uuid4(),
        output_policies=(policy,),
    )
    assert result.content == "Shipped."
    assert len(seen) == 4 and reviews == 2 and generations == 2
