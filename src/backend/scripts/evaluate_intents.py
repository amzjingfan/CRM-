"""运行真实模型意图评测，并输出不含客户原文或密钥的 Markdown 报告。"""

import argparse
import asyncio
import json
import logging
import sys
import time
import uuid
from dataclasses import asdict
from pathlib import Path

from pydantic import TypeAdapter

from app.agents.core.errors import LLMProviderError
from app.agents.core.evaluation import EvaluationCase, EvaluationMetrics, EvaluationPrediction, calculate_metrics
from app.agents.core.providers.factory import build_provider_pair
from app.agents.core.repository import NullAgentRunRecorder
from app.agents.core.schemas import ClassificationCommand, MessageContext
from app.agents.core.service import IntentClassificationService
from app.shared.config.settings import get_settings

CLASSIFIED_ACCURACY_GATE = 0.85
ABSTENTION_ACCURACY_GATE = 0.90
TESTS_ROOT = Path(__file__).resolve().parents[2] / "tests"
DATASETS_ROOT = TESTS_ROOT / "ai" / "datasets"
DEFAULT_DATASET = DATASETS_ROOT / "intent-classifier-v1.0.0.jsonl"
logger = logging.getLogger(__name__)


def build_evaluation_trace_id(case_id: str) -> str:
    """为合成评测样本生成可复算且符合生产日志约束的 UUID。"""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"intent-live-eval:{case_id}"))


def parse_args() -> argparse.Namespace:
    """解析评测输入和报告路径，默认不覆盖历史结果。"""
    parser = argparse.ArgumentParser(description="运行 AI 意图分类真实模型评测")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def load_cases(path: Path) -> list[EvaluationCase]:
    """逐行校验版本化 JSONL，遇到坏样本立即停止。"""
    adapter = TypeAdapter(EvaluationCase)
    cases: list[EvaluationCase] = []
    with path.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            try:
                cases.append(adapter.validate_python(json.loads(line)))
            except (json.JSONDecodeError, ValueError) as error:
                raise ValueError(f"评测集第 {line_number} 行无效") from error
    if len(cases) != 130:
        raise ValueError(f"评测集必须为 130 条，实际为 {len(cases)} 条")
    return cases


async def evaluate(cases: list[EvaluationCase]) -> tuple[EvaluationMetrics, str, str]:
    """调用真实 Provider；NullRecorder 明确避免评测数据写入业务数据库。"""
    settings = get_settings()
    if not settings.llm_live_eval:
        raise RuntimeError("真实模型评测未启用，请显式设置 LLM_LIVE_EVAL=true")
    primary, fallback = build_provider_pair(settings)
    service = IntentClassificationService(
        primary,
        fallback,
        NullAgentRunRecorder(),
        max_attempts=settings.llm_max_attempts,
        max_output_tokens=settings.llm_max_output_tokens,
    )
    predictions: list[EvaluationPrediction] = []
    for case in cases:
        started_at = time.perf_counter()
        try:
            result = await service.classify(
                ClassificationCommand(
                    store_id=uuid.uuid5(uuid.NAMESPACE_URL, f"eval-store:{case.case_id}"),
                    conversation_id=uuid.uuid5(uuid.NAMESPACE_URL, f"eval-conversation:{case.case_id}"),
                    trigger_message_id=uuid.uuid5(uuid.NAMESPACE_URL, f"eval-message:{case.case_id}"),
                    message=case.message,
                    history=[MessageContext.model_validate(item) for item in case.history],
                    language=case.language,
                    # case_id 仍单独保存在低敏评测结果中，Trace 只承担跨日志关联。
                    trace_id=build_evaluation_trace_id(case.case_id),
                )
            )
            predictions.append(
                EvaluationPrediction(
                    case_id=case.case_id,
                    intent=result.intent,
                    classification_state=result.classification_state,
                    confidence=result.confidence,
                    input_tokens=result.input_tokens,
                    output_tokens=result.output_tokens,
                    latency_ms=result.latency_ms,
                )
            )
        except LLMProviderError as error:
            # 单条供应商失败必须计入质量结果，但不能阻止其余 129 条样本完成。
            # 日志只包含合成 case_id 和稳定错误码，不包含消息、Prompt 或模型正文。
            logger.error(
                "intent_evaluation_case_failed",
                extra={"case_id": case.case_id, "error_code": error.code.value},
            )
            predictions.append(
                EvaluationPrediction(
                    case_id=case.case_id,
                    intent=None,
                    classification_state=case.expected_state,
                    confidence=0.0,
                    input_tokens=0,
                    output_tokens=0,
                    latency_ms=max(0, int((time.perf_counter() - started_at) * 1000)),
                    error_code=error.code.value,
                )
            )
    return calculate_metrics(cases, predictions), primary.model_name, fallback.model_name if fallback else "none"


def render_report(metrics: EvaluationMetrics, primary_model: str, fallback_model: str) -> str:
    """生成聚合报告；不输出原始样本、Prompt、模型正文或 API Key。"""
    passed = (
        metrics.provider_failure_count == 0
        and metrics.classified_accuracy >= CLASSIFIED_ACCURACY_GATE
        and metrics.abstention_accuracy >= ABSTENTION_ACCURACY_GATE
    )
    lines = [
        "# 意图分类真实模型评测报告",
        "",
        f"- 结果：{'通过' if passed else '未通过'}",
        f"- 主模型：`{primary_model}`",
        f"- 备用模型：`{fallback_model}`",
        f"- 五类准确率：{metrics.classified_accuracy:.2%}（门槛 {CLASSIFIED_ACCURACY_GATE:.0%}）",
        f"- 边界正确拒判率：{metrics.abstention_accuracy:.2%}（门槛 {ABSTENTION_ACCURACY_GATE:.0%}）",
        f"- 输入 Token：{metrics.total_input_tokens}",
        f"- 输出 Token：{metrics.total_output_tokens}",
        f"- 平均端到端耗时：{metrics.average_latency_ms:.1f} ms",
        f"- Provider 失败数：{metrics.provider_failure_count}",
        f"- Provider 错误分布：`{json.dumps(metrics.provider_error_counts, ensure_ascii=False)}`",
        "",
        "## 各意图指标",
        "",
        "| 意图 | Precision | Recall | F1 | Support |",
        "| :--- | ---: | ---: | ---: | ---: |",
    ]
    for intent, metric in metrics.per_intent.items():
        lines.append(
            f"| {intent.value} | {metric.precision:.3f} | {metric.recall:.3f} | {metric.f1:.3f} | {metric.support} |"
        )
    lines.extend(
        [
            "",
            "## 混淆矩阵",
            "",
            "```json",
            json.dumps(metrics.confusion_matrix, ensure_ascii=False, indent=2),
            "```",
            "",
            "## 未通过样本（仅合成编号与标签）",
            "",
            "| Case ID | 期望 | 实际 |",
            "| :--- | :--- | :--- |",
            *[f"| {item['case_id']} | {item['expected']} | {item['actual']} |" for item in metrics.incorrect_cases],
            "",
            "说明：报告只包含聚合指标，不包含客户原文、Prompt、模型原始输出或密钥。",
        ]
    )
    return "\n".join(lines) + "\n"


async def main() -> int:
    """执行评测、写入报告，并以退出码表达质量门禁结果。"""
    args = parse_args()
    cases = load_cases(args.dataset)
    metrics, primary_model, fallback_model = await evaluate(cases)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_report(metrics, primary_model, fallback_model), encoding="utf-8")
    print(json.dumps(asdict(metrics), ensure_ascii=False, default=str))
    return int(
        metrics.provider_failure_count > 0
        or metrics.classified_accuracy < CLASSIFIED_ACCURACY_GATE
        or metrics.abstention_accuracy < ABSTENTION_ACCURACY_GATE
    )


def cli() -> int:
    """把配置和模型错误收敛为简洁退出信息，避免打印 SDK 堆栈。"""
    try:
        return asyncio.run(main())
    except (LLMProviderError, RuntimeError, ValueError) as error:
        print(f"评测未完成：{error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(cli())
