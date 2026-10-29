"""显式评测合成七段配置的发布语义复核；不读写店铺或发送消息。"""

import argparse
import asyncio
import hashlib
import json
import logging
import time
from pathlib import Path

from langchain_core.tools import BaseTool
from pydantic import BaseModel, ConfigDict

from app.agents.orchestration.router import RouteModelPort
from app.agents.prompts.review import PROMPT_CONFIGURATION_REVIEW_VERSION, review_prompt_configuration
from app.agents.prompts.sections import SECTION_TITLES
from app.agents.providers.factory import tool_provider
from app.agents.providers.tool_calling import ToolTurn
from app.shared.config.settings import get_settings
from app.shared.exceptions.errors import AppError


class PromptCase(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    id: str
    sections: dict[str, str]
    publishable: bool


class UsageProvider:
    """在模型返回处累计用量，避免遗漏随后以 422 拒绝发布的调用。"""

    def __init__(self, inner: RouteModelPort) -> None:
        self.inner = inner
        self.input_tokens = 0
        self.output_tokens = 0
        self.unreported_calls = 0

    async def complete(
        self,
        *,
        messages: tuple[dict[str, object], ...],
        tools: tuple[BaseTool, ...],
        max_output_tokens: int,
    ) -> ToolTurn:
        try:
            turn = await self.inner.complete(messages=messages, tools=tools, max_output_tokens=max_output_tokens)
        except (Exception, asyncio.CancelledError):
            self.unreported_calls += 1
            raise
        self.input_tokens += turn.input_tokens
        self.output_tokens += turn.output_tokens
        return turn


def load_cases(data: bytes) -> list[PromptCase]:
    cases = [PromptCase.model_validate_json(line) for line in data.decode("utf-8").splitlines() if line.strip()]
    required_sections = {key for key, _ in SECTION_TITLES}
    if not cases or len({case.id for case in cases}) != len(cases):
        raise ValueError("invalid_dataset_cases")
    for case in cases:
        if (
            not case.id
            or len(case.id) > 80
            or not case.id.isascii()
            or not all(character.isalnum() or character in "-_" for character in case.id)
            or set(case.sections) != required_sections
            or not all(value.strip() for value in case.sections.values())
        ):
            raise ValueError("invalid_dataset_case")
    return cases


async def evaluate(dataset: Path, output: Path) -> bool:
    settings = get_settings()
    if settings.app_env == "production" or not settings.agent_debug_enabled:
        raise RuntimeError("仅允许明确开启 Agent 调试的非生产评测环境")
    if not settings.llm_primary_model:
        raise RuntimeError("未配置项目主模型")
    data = dataset.read_bytes()
    cases = load_cases(data)
    results: list[dict[str, object]] = []
    metered: UsageProvider | None = None
    provider_completed = True

    def record(case: PromptCase, status: int | str, approved: bool | None = None) -> None:
        # 只有语义复核完成的 200 / 422 可参与正确性判定；服务故障绝不冒充安全拒绝。
        passed = approved is not None and approved == case.publishable
        result: dict[str, object] = {"id": case.id, "passed": passed, "status": status}
        results.append(result)
        print(json.dumps(result), flush=True)

    try:
        async with tool_provider(settings, settings.llm_primary_provider, settings.llm_primary_model) as provider:
            metered = UsageProvider(provider)
            for case in cases:
                try:
                    await review_prompt_configuration(
                        sections=case.sections,
                        provider=metered,
                        deadline=time.monotonic() + settings.agent_debug_timeout_seconds,
                        max_output_tokens=settings.llm_max_output_tokens,
                    )
                except asyncio.CancelledError:
                    raise
                except AppError as error:
                    record(case, error.status_code, False if error.status_code == 422 else None)
                except Exception:
                    record(case, "error")
                else:
                    record(case, 200, True)
    except asyncio.CancelledError:
        raise
    except Exception:
        provider_completed = False
        for case in cases[len(results) :]:
            record(case, "provider_error")

    input_tokens = metered.input_tokens if metered else 0
    output_tokens = metered.output_tokens if metered else 0
    summary = {
        "dataset_sha256": hashlib.sha256(data).hexdigest(),
        "prompt_version": PROMPT_CONFIGURATION_REVIEW_VERSION,
        "provider": settings.llm_primary_provider,
        "model": settings.llm_primary_model,
        "max_output_tokens": settings.llm_max_output_tokens,
        "deadline_seconds": settings.agent_debug_timeout_seconds,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "usage_complete": metered is not None and metered.unreported_calls == 0,
        "provider_completed": provider_completed,
        "results": results,
        "passed": provider_completed and all(item["passed"] for item in results),
        "send_performed": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in summary.items() if key != "results"}), flush=True)
    return bool(summary["passed"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    logging.disable(logging.CRITICAL)
    try:
        passed = asyncio.run(evaluate(args.dataset, args.output))
    except Exception:
        print(json.dumps({"passed": False, "status": "evaluation_error"}), flush=True)
        raise SystemExit(1) from None
    raise SystemExit(0 if passed else 1)
