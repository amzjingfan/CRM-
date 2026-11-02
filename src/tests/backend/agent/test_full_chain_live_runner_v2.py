"""v2 验收判据离线行为，不读取凭证或连接应用/模型。"""

import json
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from test_full_chain_live_runner_contract import runner


@pytest.mark.parametrize(
    "body",
    [
        "Warm up for 90 seconds.",
        "Allow a 90-second warm-up.",
        "Warm up for 90 sec.",
        "Warm up for 1.5 minutes.",
        "Warm up for 1 minute 30 seconds.",
        "预热90秒钟。",
        "预热一分半。",
    ],
)
def test_duration_equivalents_pass_without_requiring_literal_words(body):
    module = runner()
    assert module.answer_checks(
        {"language": "en", "expected_fact": "90 seconds"},
        {"content": body, "send_performed": False},
        [],
        set(),
        "debug",
    )["expected_fact"]


@pytest.mark.parametrize(
    "body",
    [
        "Warm up for 190 seconds.",
        "Warm up for 90 minutes.",
        "Warm up for 0.15 minutes.",
        "Do not warm up for 90 seconds; use 30 seconds.",
        "Warm up for 60–90 seconds.",
        "Warm up for 90 or 120 seconds.",
        "TEST-CALIBRATION-90",
        "Wait 90 seconds or 30 seconds.",
        "无需预热90秒，等待30秒即可。",
        "Warm up for about 90 seconds.",
        "Warm up for -90 seconds.",
        "Warm up for over 90 seconds.",
        "预热超过90秒。",
    ],
)
def test_wrong_or_ambiguous_duration_does_not_pass(body):
    module = runner()
    assert not module.answer_checks(
        {"language": "en", "expected_fact": "90 seconds"},
        {"content": body, "send_performed": False},
        [],
        set(),
        "debug",
    )["expected_fact"]


@pytest.mark.parametrize(
    "fact,role,body",
    [
        ("45 seconds", "reset", "To reset it, disconnect power for 0.75 minutes."),
        ("45秒", "reset", "重置时断电45秒再接通。"),
        ("72 hours", "tracking_idle", "After 3 days without a tracking event, support reviews the parcel."),
        ("72 hours", "tracking_idle", "Support reviews the parcel after 72 hours with no new tracking events."),
        ("72小时", "tracking_idle", "连续3天没有新物流节点时请客服核查。"),
    ],
)
def test_other_frozen_duration_facts_remain_equivalent(fact, role, body):
    module = runner()
    assert module.duration_check(body, fact, role) == "equivalent"


def test_duration_correct_number_in_wrong_role_needs_review():
    module = runner()
    assert module.duration_check("Shipping takes 90 seconds.", "90 seconds", "warmup") == "ambiguous"


@pytest.mark.parametrize(
    "body",
    [
        "Warm up for 1,090 seconds.",
        "Warm up for 90 seconds is unnecessary.",
        "Warm up instantly. Shipping takes 90 seconds.",
    ],
)
def test_reviewed_duration_false_positives_require_manual_review(body):
    module = runner()
    assert module.duration_check(body, "90 seconds", "warmup") != "equivalent"


def test_v2_preserves_frozen_documents_cases_and_tools_and_adds_real_discovery():
    module = runner()
    v1 = json.loads(module.DATASET.with_name("agent-automation-full-chain-v1.json").read_text(encoding="utf-8"))
    v2 = json.loads(module.DATASET.read_text(encoding="utf-8"))
    assert v2["version"] == "agent-automation-full-chain-v2"
    assert v2["documents"] == v1["documents"]
    cases = {case["id"]: case for case in v2["cases"]}
    for old in v1["cases"]:
        assert set(old["required_tools"]) <= set(cases[old["id"]]["required_tools"])
    assert "before buying" in cases["presales_knowledge_en"]["input"]
    assert "售前" in cases["presales_knowledge_zh"]["input"]
    assert "received" in cases["aftersales_product_en"]["input"]
    assert "使用排查" in cases["aftersales_product_zh"]["input"]
    for language in ("en", "zh"):
        case = cases[f"order_discovery_{language}"]
        assert case["order_mode"] == "discovery"
        assert case["required_tools"] == ["search_customer_orders"]
        assert "123456789" not in module.case_question(case, "Actual product", "123456789")
        detail = cases[f"order_detail_{language}"]
        question = module.case_question(detail, "Actual product", "123456789")
        assert question.count("123456789") == 1
        assert ("订单号：" if language == "zh" else "Order number:") in question
        assert "search_customer_orders" in detail["required_tools"]


@pytest.mark.asyncio
@pytest.mark.parametrize("status,code,retryable", [(429, 42901, True), (429, 0, False), (503, 50301, False)])
async def test_only_verified_pre_model_rate_limit_can_be_retried(tmp_path, monkeypatch, status, code, retryable):
    module = runner()
    monkeypatch.setattr(module, "ARTIFACT_ROOT", tmp_path)
    clock = [1000.0]
    monkeypatch.setattr(module, "time", SimpleNamespace(time=lambda: clock[0]))
    state = module.new_manifest("a" * 64)
    client = SimpleNamespace(
        request=AsyncMock(
            side_effect=[
                httpx.Response(status, json={"code": code}, headers={"Retry-After": "60"}),
                httpx.Response(200, json={"code": 0, "data": {"ok": True}}),
            ]
        )
    )
    subject = module.Runner(SimpleNamespace(manifest=tmp_path / "state.json"), state, {}, client)
    endpoint = "/v1/agents/00000000-0000-4000-8000-000000000001/debug"
    with pytest.raises(module.Blocked):
        await subject.api("POST", endpoint, operation="one-run")
    record = state["operations"]["one-run"]
    assert record["last_http_status"] == status
    assert record["state"] == ("failed_known_not_executed" if retryable else "unknown")
    original_key = record["idempotency_key"]
    with pytest.raises(module.Blocked):
        await subject.api("POST", endpoint, operation="one-run")
    assert client.request.await_count == 1
    clock[0] += 61
    if retryable:
        assert await subject.api("POST", endpoint, operation="one-run") == {"ok": True}
        assert record["idempotency_key"] != original_key
    else:
        with pytest.raises(module.Blocked, match="unknown"):
            await subject.api("POST", endpoint, operation="one-run")
        assert client.request.await_count == 1


@pytest.mark.asyncio
async def test_current_standard_latest_scope_result_controls_resume_without_rewriting_history(tmp_path, monkeypatch):
    module = runner()
    monkeypatch.setattr(module, "ARTIFACT_ROOT", tmp_path)
    state = module.new_manifest("b" * 64)
    state["contexts"]["us"] = {"conversation_id": "00000000-0000-4000-8000-000000000001"}
    legacy = {"store": "us", "case": "one", "entry": "debug", "status": "pass"}
    state["results"] = [legacy.copy(), {**legacy, "status": "fail", "entry": "suggest"}]
    args = SimpleNamespace(manifest=tmp_path / "state.json", store=["us"], case=["one"], entry="debug")
    dataset = {"version": "agent-automation-full-chain-v2", "cases": [{"id": "one"}, {"id": "other"}]}
    subject = module.Runner(args, state, dataset, None)
    subject.run_case = AsyncMock(return_value={**legacy, "status": "pass"})
    await subject.run()
    subject.run_case.assert_awaited_once()  # v1 的 pass 不能跳过新标准。
    result = state["results"][-1]
    assert result["dataset_version"] == dataset["version"]
    assert result["dataset_sha256"] == "b" * 64
    assert len(result["criterion_sha256"]) == 64
    assert module.CRITERION_VERSION == result["criterion_version"]
    assert state["results"][0] == legacy
    assert [row["status"] for row in subject.current_results()] == ["pass"]
    await subject.run()
    assert subject.run_case.await_count == 1
    state["results"].append({**result, "status": "fail"})
    assert subject.current_results()[0]["status"] == "fail"  # 旧 pass 不能遮住更新的失败。
    await subject.run()
    assert subject.run_case.await_count == 2
    assert subject.current_results()[0]["status"] == "pass"
    state["contexts"]["us"]["conversation_id"] = "00000000-0000-4000-8000-000000000002"
    assert subject.current_results()[0]["status"] == "missing"
    await subject.run()
    assert subject.run_case.await_count == 3
    # 即使版本标签相同，显式登记的新数据 hash 也必须重新验收。
    changed = module.Runner(args, {**state, "dataset_sha256": "c" * 64}, dataset, None)
    assert changed.current_results()[0]["status"] == "missing"


def test_case_operation_keys_isolate_dataset_and_criterion():
    module = runner()
    dataset = {"version": "agent-automation-full-chain-v2"}
    subject = module.Runner(SimpleNamespace(entry="debug"), module.new_manifest("b" * 64), dataset, None)
    key = subject.case_key("order_detail_en")
    assert dataset["version"] in key and "debug:order_detail_en" in key
    changed = module.Runner(SimpleNamespace(entry="debug"), module.new_manifest("c" * 64), dataset, None)
    assert changed.case_key("order_detail_en") != key
    subject.state["contexts"]["us"] = {"conversation_id": str(uuid.uuid4())}
    scoped = subject.case_key("order_detail_en", "us")
    subject.state["contexts"]["us"]["conversation_id"] = str(uuid.uuid4())
    assert subject.case_key("order_detail_en", "us") != scoped


@pytest.mark.parametrize(
    "citations",
    [
        [],
        [{"document_id": "owned"}],
        [
            {"document_id": "owned", "chunk_id": "00000000-0000-4000-8000-000000000001"},
            {"document_id": "foreign", "chunk_id": "00000000-0000-4000-8000-000000000002"},
        ],
    ],
)
def test_knowledge_cannot_pass_missing_or_mixed_foreign_citations(citations):
    module = runner()
    checks = module.answer_checks(
        {"knowledge": "product_guide", "language": "en"},
        {"content": "Warm up for 90 seconds.", "send_performed": False, "citations": citations},
        [],
        {"owned"},
        "debug",
    )
    assert checks["owned_citation"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize("extra", ["none", "same_store_unowned", "other_store_owned"])
async def test_formal_routing_never_accepts_foreign_or_unowned_participants(tmp_path, extra):
    module = runner()
    target, stranger = str(uuid.uuid4()), str(uuid.uuid4())
    dataset = json.loads(module.DATASET.read_text(encoding="utf-8"))
    case = next(item for item in dataset["cases"] if item["id"] == "aftersales_product_en")
    asset = {
        "kind": "agent",
        "key": case["agent"],
        "id": target,
        "store_id": module.STORES["us"],
        "code": "owned",
        "revision": 1,
        "version": 1,
        "prepared": True,
    }
    state = module.new_manifest("b" * 64)
    state["assets"] = [asset]
    if extra == "other_store_owned":
        state["assets"].append({**asset, "id": stranger, "store_id": module.STORES["xbm"]})
    state["contexts"]["us"] = {"conversation_id": str(uuid.uuid4()), "unavailable_tools": []}
    subject = module.Runner(SimpleNamespace(entry="suggest"), state, dataset, None)
    subject.live["us"] = {"product": {"title": "Actual product"}, "orders": []}
    subject.api = AsyncMock(
        side_effect=[
            {
                "store_id": asset["store_id"],
                "code": "owned",
                "draft_revision": 1,
                "published_version": 1,
                "status": "enabled",
            },
            {"global_enabled": False},
        ]
    )
    subject.suggest = AsyncMock(
        return_value={"agent_run_id": str(uuid.uuid4()), "content": "The listed model is X.", "send_performed": False}
    )
    tools = [{"name": name, "status": "succeeded", "mocked": False} for name in case["required_tools"]]
    subject.traces = AsyncMock(return_value=(tools, {target} if extra == "none" else {target, stranger}, None))
    result = await subject.run_case("us", case)
    assert result["status"] == ("pass" if extra == "none" else "fail")
    assert result["assertions"]["owned_target_participated"]
