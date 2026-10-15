"""单样本真实模型诊断的调用上限与低敏结果契约。"""

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from openai import AsyncOpenAI
from pydantic import SecretStr

from app.agent.errors import LLMErrorCode, LLMProviderError
from app.agent.providers.deepseek_provider import DeepSeekProvider
from app.agent.real_model_evaluation import load_verified_real_model_evaluation_dataset
from scripts.diagnose_deepseek_canary import CANARY_SAMPLE_ID, CanaryTiming, run_one_canary, validate_canary_runtime

ROOT = Path(__file__).resolve().parents[4]
DATASET = ROOT / "release/evidence/ai/real-model-independent-v1.0.0.jsonl"
MANIFEST = ROOT / "release/evidence/ai/real-model-independent-v1.0.0.manifest.json"


class FakeProvider:
    model_name = "deepseek-v4-flash"

    def __init__(self, *, error: LLMProviderError | None = None) -> None:
        self.calls: list[object] = []
        self.error = error

    async def generate_structured(self, request: object, response_schema: object) -> SimpleNamespace:
        self.calls.append((request, response_schema))
        if self.error is not None:
            raise self.error
        return SimpleNamespace(input_tokens=17, output_tokens=9, parsed_output=object())


def test_canary_uses_one_frozen_case_and_emits_only_fixed_fields() -> None:
    dataset = load_verified_real_model_evaluation_dataset(DATASET, MANIFEST)
    provider = FakeProvider()
    timing = CanaryTiming()
    evidence = asyncio.run(run_one_canary(dataset, provider, timing))

    assert CANARY_SAMPLE_ID == "order-open-001"
    assert len(provider.calls) == 1
    request, _ = provider.calls[0]
    assert json.loads(request.user_prompt)["sample_id"] == CANARY_SAMPLE_ID
    assert evidence == {
        "schema_version": 1,
        "sample_id": CANARY_SAMPLE_ID,
        "dataset_sha256": dataset.manifest.dataset_sha256,
        "model": "deepseek-v4-flash",
        "sdk_timeout_seconds": 15,
        "hard_timeout_seconds": 20,
        "sdk_call_count": 1,
        "request_hook_seen": False,
        "response_headers_seen": False,
        "request_to_headers": "not_reached",
        "total_duration": evidence["total_duration"],
        "result": "completed",
        "error_code": None,
        "input_tokens": 17,
        "output_tokens": 9,
        "service_mutation": False,
        "production_release": False,
    }
    assert evidence["total_duration"] in {
        "0-100ms",
        "101-500ms",
        "501-2000ms",
        "2001-7000ms",
        "7001-15000ms",
        ">15000ms",
    }
    assert "content" not in json.dumps(evidence)
    assert "request_id" not in json.dumps(evidence)


def test_canary_records_provider_timeout_without_retry_or_exception_text() -> None:
    dataset = load_verified_real_model_evaluation_dataset(DATASET, MANIFEST)
    provider = FakeProvider(error=LLMProviderError(LLMErrorCode.LLM_TIMEOUT, "secret raw error", retriable=True))
    evidence = asyncio.run(run_one_canary(dataset, provider, CanaryTiming()))

    assert len(provider.calls) == 1
    assert evidence["result"] == "provider_failure"
    assert evidence["error_code"] == "LLM_TIMEOUT"
    assert evidence["input_tokens"] == 0
    assert "secret raw error" not in json.dumps(evidence)


def test_canary_observes_response_headers_through_the_real_sdk_without_network() -> None:
    dataset = load_verified_real_model_evaluation_dataset(DATASET, MANIFEST)
    timing = CanaryTiming()
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "id": "synthetic-response",
                "object": "chat.completion",
                "created": 0,
                "model": "deepseek-v4-flash",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": json.dumps(
                                {
                                    "decision": "human_review",
                                    "content": "Synthetic internal draft",
                                    "language": "zh-CN",
                                    "reason_code": "grounded_draft",
                                    "business_claims": [],
                                    "send_performed": False,
                                }
                            ),
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 17, "completion_tokens": 9, "total_tokens": 26},
            },
        )

    async def exercise() -> dict[str, object]:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(respond),
            event_hooks={"request": [timing.on_request], "response": [timing.on_response]},
        ) as http_client:
            client = AsyncOpenAI(
                api_key="test-only-key",
                base_url="https://api.deepseek.com",
                timeout=15,
                max_retries=0,
                http_client=http_client,
            )
            provider = DeepSeekProvider(
                api_key="test-only-key",
                model_name="deepseek-v4-flash",
                base_url="https://api.deepseek.com",
                timeout_seconds=15,
                client=client,
            )
            return await run_one_canary(dataset, provider, timing)

    evidence = asyncio.run(exercise())
    assert len(requests) == 1, evidence
    assert requests[0].url.path == "/chat/completions"
    assert evidence["result"] == "completed"
    assert evidence["request_hook_seen"] is True
    assert evidence["response_headers_seen"] is True
    assert evidence["request_to_headers"] != "not_reached"
    assert evidence["input_tokens"] == 17
    assert evidence["output_tokens"] == 9
    assert "Synthetic internal draft" not in json.dumps(evidence)


@pytest.mark.parametrize(
    ("override", "value"),
    [
        ("app_env", "production"),
        ("llm_live_eval", False),
        ("llm_timeout_seconds", 30.0),
        ("deepseek_base_url", "https://example.com"),
        ("deepseek_base_url", "https://api.deepseek.com/v1"),
        ("real_tiktok_message_write_enabled", True),
        ("auto_reply_enabled", True),
    ],
)
def test_canary_rejects_unsafe_runtime_before_network(
    monkeypatch: pytest.MonkeyPatch, override: str, value: object
) -> None:
    for name in ("HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy"):
        monkeypatch.delenv(name, raising=False)
    settings = SimpleNamespace(
        app_env="staging",
        llm_enabled=True,
        llm_live_eval=True,
        llm_primary_provider="deepseek",
        llm_primary_model="deepseek-v4-flash",
        llm_timeout_seconds=15.0,
        deepseek_base_url="https://api.deepseek.com",
        deepseek_api_key=SecretStr("test-only-key"),
        real_tiktok_message_write_enabled=False,
        auto_reply_enabled=False,
    )
    validate_canary_runtime(settings)
    setattr(settings, override, value)
    with pytest.raises(ValueError, match="CANARY_RUNTIME_INVALID"):
        validate_canary_runtime(settings)
