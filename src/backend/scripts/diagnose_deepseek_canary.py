"""对一条冻结合成样本执行一次 DeepSeek 请求并输出固定低敏诊断。"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx
from openai import AsyncOpenAI

from app.agent.errors import LLMProviderError
from app.agent.providers.base import LLMProvider
from app.agent.providers.deepseek_provider import DeepSeekProvider
from app.agent.real_model_evaluation import (
    RealModelEvaluationOutput,
    VerifiedRealModelEvaluationDataset,
    build_real_model_evaluation_request,
    load_verified_real_model_evaluation_dataset,
    validate_real_model_evaluation_environment,
)
from app.shared.config.settings import Settings, get_settings

CANARY_SAMPLE_ID = "order-open-001"
DATASET_SHA256 = "7f7c7084ac37e9aef5c9b1a947a9f44250cd89e290f5ae18990ec558e5c6df94"
SDK_TIMEOUT_SECONDS = 15
HARD_TIMEOUT_SECONDS = 20


def validate_canary_runtime(settings: Settings) -> None:
    """只在精确 staging 配置下允许触达付费 Provider。"""
    parsed = urlsplit(settings.deepseek_base_url)
    fixed_base_url = (
        parsed.scheme == "https"
        and parsed.hostname == "api.deepseek.com"
        and parsed.port in (None, 443)
        and parsed.path in ("", "/")
        and not parsed.query
        and not parsed.fragment
        and not parsed.username
        and not parsed.password
    )
    if (
        settings.app_env != "staging"
        or not settings.llm_enabled
        or not settings.llm_live_eval
        or settings.llm_primary_provider != "deepseek"
        or settings.llm_primary_model != "deepseek-v4-flash"
        or settings.llm_timeout_seconds != SDK_TIMEOUT_SECONDS
        or not fixed_base_url
        or settings.deepseek_api_key is None
        or not settings.deepseek_api_key.get_secret_value().strip()
        or settings.real_tiktok_message_write_enabled
        or settings.auto_reply_enabled
        or any(
            os.environ.get(name)
            for name in ("HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy")
        )
    ):
        raise ValueError("CANARY_RUNTIME_INVALID")


def timing_bucket(milliseconds: float | None) -> str:
    """只发布固定耗时分档，不暴露精确网络时序。"""
    if milliseconds is None:
        return "not_reached"
    if milliseconds <= 100:
        return "0-100ms"
    if milliseconds <= 500:
        return "101-500ms"
    if milliseconds <= 2000:
        return "501-2000ms"
    if milliseconds <= 7000:
        return "2001-7000ms"
    if milliseconds <= 15000:
        return "7001-15000ms"
    return ">15000ms"


class CanaryTiming:
    """HTTPX 钩子仅记录进入请求与收到响应头的时点。"""

    def __init__(self, clock: Callable[[], float] = time.perf_counter) -> None:
        self.clock = clock
        self.request_at: float | None = None
        self.headers_at: float | None = None

    async def on_request(self, _request: httpx.Request) -> None:
        self.request_at = self.clock()

    async def on_response(self, _response: httpx.Response) -> None:
        self.headers_at = self.clock()


async def run_one_canary(
    dataset: VerifiedRealModelEvaluationDataset,
    provider: LLMProvider,
    timing: CanaryTiming,
) -> dict[str, Any]:
    """只发起一次首稿调用；不触发评测器的修复或重生成分支。"""
    if dataset.manifest.source != "independent_test" or dataset.manifest.dataset_sha256 != DATASET_SHA256:
        raise ValueError("CANARY_DATASET_INVALID")
    if len(dataset.cases) != 36 or provider.model_name != "deepseek-v4-flash":
        raise ValueError("CANARY_RUNTIME_INVALID")
    selected = [case for case in dataset.cases if case.sample_id == CANARY_SAMPLE_ID]
    if len(selected) != 1 or selected[0].dependency_state == "model_timeout":
        raise ValueError("CANARY_CASE_INVALID")

    request = build_real_model_evaluation_request(selected[0], dataset, run_id=uuid.uuid4())
    started = timing.clock()
    result = "completed"
    error_code: str | None = None
    input_tokens = 0
    output_tokens = 0
    try:
        response = await asyncio.wait_for(
            provider.generate_structured(request, RealModelEvaluationOutput),
            timeout=HARD_TIMEOUT_SECONDS,
        )
        input_tokens = max(0, response.input_tokens)
        output_tokens = max(0, response.output_tokens)
    except LLMProviderError as error:
        result = "provider_failure"
        error_code = error.code.value
    except TimeoutError:
        result = "hard_timeout"
        error_code = "CANARY_HARD_TIMEOUT"
    except Exception:
        result = "internal_failure"
        error_code = "CANARY_INTERNAL_FAILURE"
    finished = timing.clock()
    request_to_headers = None
    if timing.request_at is not None and timing.headers_at is not None:
        request_to_headers = max(0.0, (timing.headers_at - timing.request_at) * 1000)
    return {
        "schema_version": 1,
        "sample_id": CANARY_SAMPLE_ID,
        "dataset_sha256": dataset.manifest.dataset_sha256,
        "model": provider.model_name,
        "sdk_timeout_seconds": SDK_TIMEOUT_SECONDS,
        "hard_timeout_seconds": HARD_TIMEOUT_SECONDS,
        "sdk_call_count": 1,
        "request_hook_seen": timing.request_at is not None,
        "response_headers_seen": timing.headers_at is not None,
        "request_to_headers": timing_bucket(request_to_headers),
        "total_duration": timing_bucket(max(0.0, (finished - started) * 1000)),
        "result": result,
        "error_code": error_code,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "service_mutation": False,
        "production_release": False,
    }


async def main() -> int:
    parser = argparse.ArgumentParser(description="Run one bounded staging DeepSeek canary")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("CANARY_OUTPUT_EXISTS")

    settings = get_settings()
    dataset = load_verified_real_model_evaluation_dataset(args.dataset, args.manifest)
    validate_real_model_evaluation_environment(dataset, settings.app_env)
    validate_canary_runtime(settings)
    api_key = settings.deepseek_api_key
    model_name = settings.llm_primary_model
    if api_key is None or model_name is None:
        raise ValueError("CANARY_RUNTIME_INVALID")

    timing = CanaryTiming()
    logging.disable(logging.CRITICAL)
    async with httpx.AsyncClient(
        timeout=SDK_TIMEOUT_SECONDS,
        trust_env=False,
        event_hooks={"request": [timing.on_request], "response": [timing.on_response]},
    ) as http_client:
        client = AsyncOpenAI(
            api_key=api_key.get_secret_value(),
            base_url=settings.deepseek_base_url,
            timeout=SDK_TIMEOUT_SECONDS,
            max_retries=0,
            http_client=http_client,
        )
        provider = DeepSeekProvider(
            api_key=api_key.get_secret_value(),
            model_name=model_name,
            base_url=settings.deepseek_base_url,
            timeout_seconds=SDK_TIMEOUT_SECONDS,
            thinking_enabled=settings.deepseek_thinking_enabled,
            client=client,
        )
        evidence = await run_one_canary(dataset, provider, timing)

    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(evidence, stream, separators=(",", ":"))
        stream.write("\n")
    print("CANARY_EVIDENCE_WRITTEN")
    return 0


def cli() -> int:
    try:
        return asyncio.run(main())
    except Exception:
        # 不允许库异常将 URL、Token、请求 ID 或模型正文带入 Runner 日志。
        print("CANARY_SETUP_FAILED", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(cli())
