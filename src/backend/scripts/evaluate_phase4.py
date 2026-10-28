"""执行 Phase 4 确定性安全回归，不冒充真实模型质量评测。"""

import argparse
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from app.agents.core.reply_safety import ReplyEvidenceKind, ReplySafetyPolicy


class Phase4SafetyCase(BaseModel):
    """一条不含真实客户隐私的回复安全回归样本。"""

    case_id: str = Field(min_length=1, max_length=100)
    category: Literal["reply", "translation", "abandoned_cart", "bad_review"]
    message: str = Field(min_length=1, max_length=4000)
    candidate_answer: str = Field(min_length=1, max_length=4000)
    evidence_kind: ReplyEvidenceKind
    successful_tools: set[str] = Field(default_factory=set)
    has_mock_result: bool = False
    expected_safe: bool
    expected_reason_codes: set[str] = Field(default_factory=set)


def load_cases(path: Path) -> list[Phase4SafetyCase]:
    """逐行加载版本化样本，拒绝重复 case_id 和坏 JSON。"""
    cases = [Phase4SafetyCase.model_validate_json(line) for line in path.read_text("utf-8").splitlines() if line]
    if len({case.case_id for case in cases}) != len(cases):
        raise ValueError("Phase 4 评测集包含重复 case_id")
    return cases


def evaluate_safety_cases(cases: list[Phase4SafetyCase]) -> dict[str, object]:
    """运行代码安全门禁并统计准确率、原因码一致率和危险漏放数。"""
    policy = ReplySafetyPolicy()
    safe_correct = 0
    reason_correct = 0
    unsafe_escape_count = 0
    failed_case_ids: list[str] = []
    for case in cases:
        result = policy.evaluate(
            case.candidate_answer,
            evidence_kind=case.evidence_kind,
            successful_tools=case.successful_tools,
            has_mock_result=case.has_mock_result,
        )
        safe_matches = result.is_safe == case.expected_safe
        reasons_match = set(result.reason_codes) == case.expected_reason_codes
        safe_correct += int(safe_matches)
        reason_correct += int(reasons_match)
        unsafe_escape_count += int(not case.expected_safe and result.is_safe)
        if not safe_matches or not reasons_match:
            failed_case_ids.append(case.case_id)
    total = len(cases)
    return {
        "gate": "deterministic_safety_gate",
        "sample_count": total,
        "safety_accuracy": safe_correct / total if total else 0.0,
        "reason_code_accuracy": reason_correct / total if total else 0.0,
        "unsafe_escape_count": unsafe_escape_count,
        "failed_case_ids": failed_case_ids,
        "passed": total > 0 and safe_correct == total and reason_correct == total and unsafe_escape_count == 0,
        "live_model_evaluation": False,
    }


def main() -> None:
    """解析输入并输出不含样本正文的 JSON 报告。"""
    parser = argparse.ArgumentParser(description="执行 Phase 4 回复安全确定性回归")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = evaluate_safety_cases(load_cases(args.dataset))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
