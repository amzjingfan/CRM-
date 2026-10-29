"""有序答复由模型结构化提交；生成中仅供坐席审阅，不能变成已核验输出。"""

import pytest
from pydantic import ValidationError

from app.agents.delivery.reply_parts import ReplyDraftCollector, ReplyPartsOutput, parts_from_turn
from app.agents.providers.text_streaming import ModelStreamDelta
from app.agents.providers.tool_calling import FunctionCall, ToolTurn


def turn(arguments, name="submit_reply_parts"):
    return ToolTurn(None, (FunctionCall("batch", name, arguments),), {}, 2, 3)


def test_model_parts_preserve_order_and_do_not_split_by_business_keywords():
    assert parts_from_turn(
        turn({"texts": ["Your parcel is in transit.", "The warranty policy is not available."]})
    ) == ("Your parcel is in transit.", "The warranty policy is not available.")


@pytest.mark.parametrize(
    "arguments",
    [
        {"texts": []},
        {"texts": [""]},
        {"texts": ["ok"], "customer_id": "someone"},
        {"texts": ["x" * 16001]},
        {"texts": [123]},
    ],
)
def test_invalid_reply_parts_cannot_become_review_plan(arguments):
    with pytest.raises((ValueError, ValidationError)):
        parts_from_turn(turn(arguments))


def test_wrong_tool_or_multiple_submissions_are_not_customer_text():
    with pytest.raises(ValueError):
        parts_from_turn(turn({"texts": ["ok"]}, "query_order"))
    t = turn({"texts": ["ok"]})
    with pytest.raises(ValueError):
        parts_from_turn(ToolTurn(None, t.calls + t.calls, {}, 2, 3))


@pytest.mark.asyncio
async def test_partial_tool_json_only_emits_whitelisted_plain_draft_parts():
    seen = []

    async def emit(index, text):
        seen.append((index, text))

    c = ReplyDraftCollector(emit)
    await c(
        ModelStreamDelta(
            kind="tool_arguments", tool_index=0, tool_name="submit_reply_parts", arguments_delta='{"texts":["Hel'
        )
    )
    assert seen == [(0, "Hel")]
    await c(ModelStreamDelta(kind="tool_arguments", tool_index=0, arguments_delta='lo", "Your parcel is in tr'))
    assert seen[-2:] == [(0, "Hello"), (1, "Your parcel is in tr")]
    await c(ModelStreamDelta(kind="tool_arguments", tool_index=0, arguments_delta='ansit."]}'))
    assert seen[-1] == (1, "Your parcel is in transit.")
    assert all("texts" not in text and "{" not in text for _, text in seen)


@pytest.mark.asyncio
async def test_non_reply_tool_and_unstructured_model_text_are_not_streamed_as_reply():
    seen = []

    async def emit(index, text):
        seen.append((index, text))

    c = ReplyDraftCollector(emit)
    await c(ModelStreamDelta(kind="text", text="Internal planning text"))
    await c(
        ModelStreamDelta(
            kind="tool_arguments", tool_index=0, tool_name="query_order", arguments_delta='{"texts":["private"]}'
        )
    )
    assert seen == []


@pytest.mark.asyncio
async def test_streaming_draft_is_never_reported_as_final_validated_parts():
    seen = []

    async def emit(index, text):
        seen.append((index, text))

    c = ReplyDraftCollector(emit)
    await c(
        ModelStreamDelta(
            kind="tool_arguments", tool_index=0, tool_name="submit_reply_parts", arguments_delta='{"texts":["partial'
        )
    )
    assert seen == [(0, "partial")]
    with pytest.raises(ValidationError):
        ReplyPartsOutput.model_validate_json('{"texts":["partial')


@pytest.mark.asyncio
async def test_split_json_unicode_surrogate_does_not_leak_invalid_utf8():
    seen = []

    async def emit(index, text):
        text.encode("utf-8")
        seen.append(text)

    collector = ReplyDraftCollector(emit)
    await collector(
        ModelStreamDelta(
            kind="tool_arguments", tool_index=0, tool_name="submit_reply_parts", arguments_delta='{"texts":["\\ud83d'
        )
    )
    await collector(ModelStreamDelta(kind="tool_arguments", tool_index=0, arguments_delta='\\udce6"]}'))
    assert seen == ["📦"]


@pytest.mark.asyncio
async def test_anthropic_text_before_tool_still_streams_only_first_reply_submission():
    seen = []

    async def emit(index, text):
        seen.append((index, text))

    collector = ReplyDraftCollector(emit)
    await collector(ModelStreamDelta(kind="text", text="Internal explanation"))
    await collector(
        ModelStreamDelta(
            kind="tool_arguments",
            tool_index=1,
            tool_name="submit_reply_parts",
            arguments_delta='{"texts":["Your parcel',
        )
    )
    await collector(
        ModelStreamDelta(
            kind="tool_arguments",
            tool_index=2,
            tool_name="submit_reply_parts",
            arguments_delta='{"texts":["Second call must not replace"]}',
        )
    )
    assert seen == [(0, "Your parcel")]
