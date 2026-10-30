"""审阅计划先真实流式生成，再按完整独立答复逐条复核。"""

import asyncio
import json
import time
import uuid

import pytest
from agent._review_helpers import accepted_review_turn

from app.agents.delivery.generation import aggregate_reply_plan
from app.agents.orchestration.coordinator import SpecialistResult
from app.agents.providers.text_streaming import ModelStreamDelta
from app.agents.providers.tool_calling import FunctionCall, ToolTurn


class BatchModel:
    def __init__(self, parts):
        self.parts = parts
        self.release = asyncio.Event()
        self.reviewed = []

    async def complete_streaming(self, *, messages, tools, max_output_tokens, on_delta):
        assert tools[0].name == "submit_reply_parts"
        text = json.dumps({"texts": self.parts})
        await on_delta(
            ModelStreamDelta(kind="tool_arguments", tool_index=0, tool_name="submit_reply_parts", arguments_delta=text)
        )
        await self.release.wait()
        return ToolTurn(None, (FunctionCall("parts", "submit_reply_parts", {"texts": self.parts}),), {}, 7, 5)

    async def complete(self, *, messages, tools, max_output_tokens):
        assert tools[0].name == "review_answer_evidence"
        self.reviewed.append(json.loads(messages[-1]["content"])["answer"])
        return accepted_review_turn(messages)


@pytest.mark.asyncio
async def test_live_draft_arrives_before_final_plan_and_each_part_is_reviewed():
    model = BatchModel(["The parcel is in transit.", "The policy requires human verification."])
    seen = []
    first = asyncio.Event()

    async def draft(index, text):
        seen.append((index, text))
        first.set()

    task = asyncio.create_task(
        aggregate_reply_plan(
            question="Tracking and policy?",
            results=(SpecialistResult(uuid.uuid4(), "facts", verified_facts={"status": "in_transit"}),),
            provider=model,
            deadline=time.monotonic() + 3,
            store_id=uuid.uuid4(),
            on_draft=draft,
        )
    )
    await asyncio.wait_for(first.wait(), 1)
    assert seen and not task.done()
    model.release.set()
    result = await task
    assert result.reply_parts == tuple(model.parts)
    assert result.content == model.parts[0]
    assert model.reviewed == model.parts
    assert (result.input_tokens, result.output_tokens) == (11, 9)


@pytest.mark.asyncio
async def test_conflicting_facts_never_start_streaming():
    model = BatchModel(["unsafe"])
    model.release.set()
    result = await aggregate_reply_plan(
        question="Status?",
        results=(
            SpecialistResult(uuid.uuid4(), "a", verified_facts={"status": "sent"}),
            SpecialistResult(uuid.uuid4(), "b", verified_facts={"status": "not_sent"}),
        ),
        provider=model,
        deadline=time.monotonic() + 2,
        store_id=uuid.uuid4(),
    )
    assert result.reason_code == "conflicting_verified_facts" and result.reply_parts == ()


@pytest.mark.asyncio
async def test_unsupported_streamed_draft_never_becomes_final_reply_parts():
    class Rejected(BatchModel):
        async def complete(self, **kwargs):
            if not kwargs["tools"]:
                return ToolTurn("I cannot verify this.", (), {}, 2, 1)
            result = accepted_review_turn(kwargs["messages"])
            result.calls[0].arguments.update(supported=False, reason_code="unsupported", evidence_ids=[])
            return result

    model = Rejected(["A guaranteed refund."])
    model.release.set()
    seen = []

    async def draft(index, text):
        seen.append(text)

    result = await aggregate_reply_plan(
        question="Refund?",
        results=(SpecialistResult(uuid.uuid4(), "fact", verified_facts={"status": "in_transit"}),),
        provider=model,
        deadline=time.monotonic() + 2,
        store_id=uuid.uuid4(),
        on_draft=draft,
    )
    assert seen == ["A guaranteed refund."]
    assert result.content is None and result.reply_parts == ()


@pytest.mark.asyncio
async def test_rejected_part_rebuilds_one_complete_answer_instead_of_repeating_it_per_part():
    class Regenerating(BatchModel):
        def __init__(self):
            super().__init__(["Rejected partial delivery answer.", "Rejected partial policy answer."])
            self.generations = []

        async def complete(self, *, messages, tools, max_output_tokens):
            payload = json.loads(messages[-1]["content"])
            if not tools:
                self.generations.append(payload)
                return ToolTurn("Latest delivery is verified. The guide lists three materials.", (), {}, 2, 1)
            result = accepted_review_turn(messages)
            if payload["answer"] in self.parts:
                result.calls[0].arguments.update(supported=False, reason_code="unsupported", evidence_ids=[])
            return result

    model = Regenerating()
    model.release.set()
    result = await aggregate_reply_plan(
        question="Latest delivery and guide materials?",
        results=(SpecialistResult(uuid.uuid4(), "Expert draft", verified_facts={"status": "delivered"}),),
        provider=model,
        deadline=time.monotonic() + 3,
        store_id=uuid.uuid4(),
        on_draft=lambda *_: asyncio.sleep(0),
    )
    assert result.reply_parts == ("Latest delivery is verified. The guide lists three materials.",)
    assert len(model.generations) == 1
    assert model.generations[0]["question"] == "Latest delivery and guide materials?"
    assert "Rejected partial" not in json.dumps(model.generations)
