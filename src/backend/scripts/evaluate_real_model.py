"""执行 REAL-AI-05 版本化 DeepSeek 合成评测并输出低敏 JSON 证据。"""

import argparse
import asyncio
import json
import sys
import uuid
from pathlib import Path

from app.agent.errors import LLMProviderError
from app.agent.providers.factory import build_provider
from app.agent.real_model_evaluation import (
    load_verified_real_model_evaluation_dataset,
    run_real_model_evaluation,
)
from app.shared.config.settings import get_settings

TESTS_ROOT = Path(__file__).resolve().parents[2] / "tests"
DATASETS_ROOT = TESTS_ROOT / "ai" / "datasets"
DEFAULT_DATASET = DATASETS_ROOT / "real-model-v1.0.0.jsonl"
DEFAULT_MANIFEST = DATASETS_ROOT / "real-model-v1.0.0.manifest.json"


def parse_args() -> argparse.Namespace:
    """解析评测路径；默认拒绝覆盖历史结果以保留每轮证据。"""
    parser = argparse.ArgumentParser(description="执行 REAL-AI-05 版本化 DeepSeek 真实模型评测")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run-id", type=uuid.UUID, default=None)
    return parser.parse_args()


async def main() -> int:
    """校验开关和 DeepSeek 配置后运行评测，退出码 1 表示质量门禁未通过。"""
    args = parse_args()
    if args.output.exists():
        raise ValueError("评测结果文件已存在，禁止覆盖历史证据")
    settings = get_settings()
    if not settings.llm_live_eval:
        raise RuntimeError("真实模型评测未启用，请显式设置 LLM_LIVE_EVAL=true")
    if settings.llm_primary_provider.strip().lower() != "deepseek":
        raise RuntimeError("REAL-AI-05 当前只允许使用 DeepSeek 主模型")
    provider = build_provider(settings.llm_primary_provider, settings.llm_primary_model, settings)
    dataset = load_verified_real_model_evaluation_dataset(args.dataset, args.manifest)
    report = await run_real_model_evaluation(
        dataset,
        provider,
        run_id=args.run_id or uuid.uuid4(),
        app_env=settings.app_env,
        input_cost_per_million_usd=settings.llm_input_cost_per_million_usd,
        output_cost_per_million_usd=settings.llm_output_cost_per_million_usd,
        pricing_version=settings.llm_pricing_version,
        pricing_currency=settings.llm_pricing_currency,
        pricing_basis=settings.llm_pricing_basis,
    )
    write_report_exclusively(args.output, report.model_dump(mode="json"))
    # 控制台只输出聚合指标和版本，不输出逐样本正文或模型原文。
    print(
        json.dumps(
            {
                "run_id": str(report.run_id),
                "model": report.model,
                "prompt_version": report.prompt_version,
                "policy_version": report.policy_version,
                "dataset_version": report.dataset_version,
                "passed": report.passed,
                "metrics": report.metrics.model_dump(mode="json"),
            },
            ensure_ascii=False,
            default=str,
        )
    )
    return 0 if report.passed else 1


def write_report_exclusively(output: Path, report: dict[str, object]) -> None:
    """使用排他创建保存低敏结果，消除 exists 检查后的并发覆盖窗口。"""
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, default=str)
        stream.write("\n")


def cli() -> int:
    """把配置、数据集和 Provider 错误收敛为低敏终端消息。"""
    try:
        return asyncio.run(main())
    except LLMProviderError as error:
        print(f"评测未完成：{error.code.value}", file=sys.stderr)
        return 2
    except RuntimeError:
        print("评测未完成：EVALUATION_CONFIGURATION_INVALID", file=sys.stderr)
        return 2
    except (ValueError, OSError):
        # Pydantic 的输入错误可能包含 input_value；终端和 CI 只允许稳定低敏码。
        print("评测未完成：EVALUATION_INPUT_INVALID", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(cli())
