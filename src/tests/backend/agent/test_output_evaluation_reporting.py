"""预期拒绝的样例也必须完成语义判定，基础设施故障不能计为评测通过。"""

import json
import runpy
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.agents.safety.grounding import GroundingDecision


@pytest.mark.parametrize(
    "reason,complete",
    [
        ("answer_not_grounded", True),
        ("conflicting_verified_facts", True),
        ("deadline_exceeded", False),
        ("context_budget_exceeded", False),
        ("evidence_review_invalid", False),
        ("evidence_review_failed", False),
        (None, False),
    ],
)
def test_incomplete_review_cannot_pass_an_expected_rejection(reason, complete):
    script = Path(__file__).resolve().parents[2] / "ai" / "evaluate_output_review.py"
    helper = runpy.run_path(str(script))["semantic_review_completed"]
    assert helper(GroundingDecision(False, 0, 0, reason_code=reason)) is complete


@pytest.mark.asyncio
async def test_evaluation_report_marks_timeout_failed_even_for_expected_rejection(monkeypatch, tmp_path):
    script = Path(__file__).resolve().parents[2] / "ai" / "evaluate_output_review.py"
    evaluate = runpy.run_path(str(script))["evaluate"]

    @asynccontextmanager
    async def provider(*_args):
        yield SimpleNamespace(complete=AsyncMock(side_effect=TimeoutError))

    monkeypatch.setitem(evaluate.__globals__, "tool_provider", provider)
    monkeypatch.setitem(
        evaluate.__globals__,
        "get_settings",
        lambda: SimpleNamespace(
            app_env="test",
            agent_debug_enabled=True,
            llm_primary_model="fake",
            llm_primary_provider="fake",
            agent_debug_timeout_seconds=1,
            llm_max_output_tokens=100,
        ),
    )
    dataset = tmp_path / "synthetic.jsonl"
    dataset.write_text(
        json.dumps(
            {
                "id": "expected-rejection",
                "question": "Where is it?",
                "answer": "Shipped.",
                "evidence": {"status": "shipped"},
                "supported": False,
                "private_values": [],
                "preserve": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    output = tmp_path / "result.json"
    assert await evaluate(dataset, output) is False
    result = json.loads(output.read_text("utf-8"))["results"][0]
    assert result["passed"] is False and result["semantic_review_completed"] is False
    assert result["reason"] == "deadline_exceeded"
