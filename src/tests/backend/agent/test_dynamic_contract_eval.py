"""版本化动态 Agent 样例验证协议与边界，不模拟真实语义准确率。"""

import pytest
from _support import SOURCE_ROOT

from scripts.evaluate_dynamic_agents import evaluate_dataset


@pytest.mark.asyncio
async def test_versioned_dynamic_contract_dataset_passes_all_boundary_cases() -> None:
    report = await evaluate_dataset(SOURCE_ROOT / "tests/ai/datasets/agent-dynamic-contract-v1.0.0.jsonl")
    assert report["passed"] is True
    assert report["sample_count"] == 16
    assert report["live_model_evaluation"] is False
