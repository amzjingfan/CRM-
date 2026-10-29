"""显式运行合成数据的真实模型输出复核评测，不访问真实店铺或发送消息。"""

import argparse
import asyncio
import hashlib
import json
import logging
import time
from pathlib import Path

from app.agents.providers.factory import tool_provider
from app.agents.runtime.output import plain_text_answer
from app.agents.safety.grounding import GROUNDING_PROMPT_VERSION, GroundingDecision, review_final_answer
from app.agents.tools.business_identifiers import business_identifier_values
from app.shared.config.settings import get_settings


def semantic_review_completed(decision: GroundingDecision) -> bool:
    """超时、无效协议和提供方故障不等于模型已明确拒绝候选。"""
    return (decision.supported and decision.reason_code is None) or (
        not decision.supported and decision.reason_code in {"answer_not_grounded", "conflicting_verified_facts"}
    )


async def evaluate(dataset: Path, output: Path) -> bool:
    settings = get_settings()
    if settings.app_env == "production" or not settings.agent_debug_enabled:
        raise RuntimeError("仅允许已明确开启 Agent 调试的非生产评测环境")
    if not settings.llm_primary_model:
        raise RuntimeError("未配置模型")
    data = dataset.read_bytes()
    cases = [json.loads(line) for line in data.decode("utf-8").splitlines() if line.strip()]
    results = []
    async with tool_provider(settings, settings.llm_primary_provider, settings.llm_primary_model) as provider:
        for case in cases:
            literals = tuple(value for item in case["evidence"].values() for value in business_identifier_values(item))
            decision = await review_final_answer(
                question=case["question"],
                answer=plain_text_answer(case["answer"], literal_values=literals),
                evidence=case["evidence"],
                provider=provider,
                deadline=time.monotonic() + settings.agent_debug_timeout_seconds,
                privacy_policies=(
                    "过滤个人联系资料、私人精确地址和凭证；保留本次已核验的订单号、运单号、SKU、商品编号以及日期、金额和状态。",
                ),
                max_output_tokens=settings.llm_max_output_tokens,
                literal_values=literals,
            )
            text = decision.answer or ""
            passed = (
                semantic_review_completed(decision)
                and decision.supported == case["supported"]
                and all(value not in text for value in case["private_values"])
                and (not case["supported"] or (bool(text.strip()) and all(value in text for value in case["preserve"])))
                and "敏感信息已隐藏" not in text
                and "**" not in text
            )
            result = {
                "id": case["id"],
                "passed": passed,
                "supported": decision.supported,
                "answer_length": len(text),
                "semantic_review_completed": semantic_review_completed(decision),
                "reason": decision.reason_code,
            }
            results.append(result)
            print(json.dumps(result), flush=True)
    summary = {
        "dataset_sha256": hashlib.sha256(data).hexdigest(),
        "prompt_version": GROUNDING_PROMPT_VERSION,
        "provider": settings.llm_primary_provider,
        "model": settings.llm_primary_model,
        "results": results,
        "passed": all(item["passed"] for item in results),
        "send_performed": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return bool(summary["passed"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    logging.disable(logging.CRITICAL)
    raise SystemExit(0 if asyncio.run(evaluate(args.dataset, args.output)) else 1)
