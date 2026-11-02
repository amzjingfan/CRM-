"""Live验收runner只验证离线安全边界，不连接服务或读取凭证。"""

import ast
import importlib.util
import json
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest


def runner():
    path = Path(__file__).resolve().parents[2] / "ai" / "agent_automation_full_chain_live.py"
    spec = importlib.util.spec_from_file_location("full_chain_live_runner", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
async def test_inventory_order_context_uses_the_real_sidebar_order_field():
    from unittest.mock import AsyncMock

    module = runner()
    conversation_id = str(uuid.uuid4())
    subject = module.Runner(SimpleNamespace(), {}, {}, None)
    subject.api = AsyncMock(
        side_effect=[
            {"session": {"store_id": module.STORES["us"], "status": "active"}},
            {"items": [{"id": "verified-order"}]},
            {"items": [{"skus": [{"quantity": 1}]}]},
        ]
    )
    result = await subject.context("us", conversation_id)
    assert result["orders"] == [{"id": "verified-order"}]
    assert subject.api.call_args_list[1].kwargs["payload"] == {"section": "orders", "field": "order", "query": ""}


def settings(**changes):
    return SimpleNamespace(
        **{
            "app_env": "staging",
            "real_tiktok_automation_enabled": False,
            "auto_reply_enabled": False,
            "llm_enabled": True,
            "agent_v2_formal_enabled": True,
            "agent_debug_enabled": True,
            "agent_v2_debug_enabled": True,
            "llm_primary_provider": "deepseek",
            "embedding_enabled": True,
            "embedding_provider": "local_bge",
            "real_tiktok_read_enabled": True,
            "allow_mock_platform_adapters": False,
            "public_base_url": "https://staging.overselfx.com",
            "cors_origin_list": ["https://staging.overselfx.com"],
            **changes,
        }
    )


@pytest.mark.parametrize(
    "changes", [{"app_env": "production"}, {"real_tiktok_automation_enabled": True}, {"auto_reply_enabled": True}]
)
def test_runtime_gate_refuses_unsafe_live_target(changes):
    module = runner()
    with pytest.raises(module.Blocked):
        module.runtime_guard(settings(**changes))


@pytest.mark.parametrize(
    "method,path",
    [
        ("POST", "/v1/workspace/sessions/00000000-0000-4000-8000-000000000001/messages"),
        ("POST", "/v1/workspace/sessions/00000000-0000-4000-8000-000000000001/reply-batches"),
        ("PUT", "/v1/agents/automation"),
        ("POST", "https://outside.example/v1/agents"),
        ("POST", "/v1/agents/../tools/send"),
    ],
)
def test_transport_never_exposes_platform_send_or_policy_paths(method, path):
    module = runner()
    with pytest.raises(module.Blocked):
        module.request_guard(method, path)


def test_transport_allows_only_expected_authenticated_acceptance_writes():
    module = runner()
    module.request_guard("POST", "/v1/workspace/sessions/00000000-0000-4000-8000-000000000001/suggest")
    module.request_guard("POST", "/v1/knowledge/files/imports")
    with pytest.raises(module.Blocked):
        module.validate_base_url("https://outside.example")
    assert module.validate_base_url("http://127.0.0.1:8000") == "http://127.0.0.1:8000"


def test_logistics_event_guard_matches_product_route_and_rejects_obsolete_path():
    module = runner()
    agent_id = "00000000-0000-4000-8000-000000000001"
    module.request_guard("POST", f"/v1/agents/{agent_id}/logistics-event-preview")
    with pytest.raises(module.Blocked):
        module.request_guard("POST", f"/v1/agents/{agent_id}/debug/logistics-event")


@pytest.mark.asyncio
async def test_logistics_event_debug_uses_real_route_and_request_schema(tmp_path, monkeypatch):
    import builtins
    from unittest.mock import AsyncMock

    from pydantic import BaseModel, Field

    module = runner()
    agent_id, conversation_id = str(uuid.uuid4()), str(uuid.uuid4())
    service = module.Runner(SimpleNamespace(entry="debug"), module.new_manifest("a" * 64), {}, None)
    service.state["contexts"]["us"] = {"conversation_id": conversation_id}
    reached_preview = RuntimeError("stop before any transport or database use")
    service.api = AsyncMock(side_effect=[{"agent_id": agent_id}, reached_preview])
    service.context = AsyncMock(
        return_value={"conversation_id": conversation_id, "orders": [{"external_order_id": "123456789"}]}
    )
    monkeypatch.setattr(module, "outbound_counts", AsyncMock(return_value={"us": 0}))
    original_import = builtins.__import__

    def offline_import(name, *args, **kwargs):
        if name == "app.knowledge_base.document_models":
            return SimpleNamespace(KnowledgeFileChunk=None)
        if name == "app.shared.database.session":
            return SimpleNamespace(session_factory=None)
        if name == "app" or name.startswith("app."):
            pytest.fail("event route contract imported application/settings")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", offline_import)
    with pytest.raises(RuntimeError, match="stop before"):
        await service.event_preview("us", {"id": "event_en"}, {"id": agent_id})
    call = service.api.await_args
    assert call.args == ("POST", f"/v1/agents/{agent_id}/logistics-event-preview")
    assert call.kwargs["payload"] == {"conversation_id": conversation_id, "external_order_id": "123456789"}
    # Load only the real Pydantic request class, without importing app/settings or opening a session.
    source = (module.TEST_ROOT.parent / "backend/app/agents/management/schemas.py").read_text(encoding="utf-8-sig")
    node = next(
        item
        for item in ast.parse(source).body
        if isinstance(item, ast.ClassDef) and item.name == "AgentLogisticsPreviewRequest"
    )
    namespace = {"uuid": uuid, "BaseModel": BaseModel, "Field": Field}
    exec(compile(ast.Module(body=[node], type_ignores=[]), "event-request-contract", "exec"), namespace)
    parsed = namespace["AgentLogisticsPreviewRequest"].model_validate(call.kwargs["payload"])
    assert str(parsed.conversation_id) == conversation_id and parsed.package_id is None


def test_manifest_requires_owned_prefix_exact_stores_and_artifact_path(tmp_path, monkeypatch):
    module = runner()
    monkeypatch.setattr(module, "ARTIFACT_ROOT", tmp_path)
    path = tmp_path / "owned.json"
    state = module.new_manifest("a" * 64)
    module.save_manifest(path, state)
    assert module.load_manifest(path, "a" * 64)["run_id"] == state["run_id"]
    bad = {
        **state,
        "assets": [
            {
                "kind": "agent",
                "id": str(uuid.uuid4()),
                "store_id": next(iter(module.STORES.values())),
                "code": "real_existing_agent",
            }
        ],
    }
    with pytest.raises(module.Blocked):
        module.save_manifest(path, bad)
    with pytest.raises(module.Blocked):
        module.save_manifest(tmp_path.parent / "outside.json", state)
    with pytest.raises(module.Blocked):
        module.save_manifest(path, {**state, "access_token": "never-write"})
    assert "never-write" not in path.read_text(encoding="utf-8")


def test_manifest_dataset_and_scope_mismatch_do_not_resume(tmp_path, monkeypatch):
    module = runner()
    monkeypatch.setattr(module, "ARTIFACT_ROOT", tmp_path)
    path = tmp_path / "owned.json"
    state = module.new_manifest("a" * 64)
    module.save_manifest(path, state)
    with pytest.raises(module.Blocked):
        module.load_manifest(path, "b" * 64)
    state["stores"] = {"unknown": str(uuid.uuid4())}
    path.write_text(json.dumps(state), encoding="utf-8")
    with pytest.raises(module.Blocked):
        module.load_manifest(path, "a" * 64)


def test_nonempty_answer_without_tool_and_owned_citation_is_not_pass():
    module = runner()
    case = {
        "language": "en",
        "required_tools": ["search_knowledge"],
        "knowledge": "product_guide",
        "expected_fact": "90 seconds",
    }
    answer = {"content": "Wait 90 seconds.", "send_performed": False, "citations": []}
    checks = module.answer_checks(case, answer, [], {"owned-file"}, "debug")
    assert checks["required_tools"] is False and checks["owned_citation"] is False
    answer["citations"] = [{"document_id": "owned-file", "chunk_id": str(uuid.uuid4())}]
    checks = module.answer_checks(
        case, answer, [{"name": "search_knowledge", "status": "retrieved", "mocked": False}], {"owned-file"}, "debug"
    )
    assert all(checks.values())
    answer["send_performed"] = True
    assert not module.answer_checks(
        case, answer, [{"name": "search_knowledge", "status": "retrieved", "mocked": False}], {"owned-file"}, "debug"
    )["no_send"]


def test_debug_internal_preview_is_distinct_from_persisted_formal_tool_success():
    module = runner()
    case = {"language": "en", "required_tools": ["create_handoff_request"]}
    answer = {"content": "We received your question.", "send_performed": False}
    tools = [{"name": "create_handoff_request", "status": "previewed", "mocked": False}]
    assert module.answer_checks(case, answer, tools, set(), "debug")["required_tools"]
    assert not module.answer_checks(case, answer, tools, set(), "suggest")["required_tools"]


def test_case_adapts_only_real_product_questions_and_keeps_synthetic_rag():
    module = runner()
    live = {"id": "presales_product_en", "language": "en", "input": "Is Orbit Lamp in stock?"}
    knowledge = {**live, "knowledge": "product_guide"}
    assert "Real Test Product" in module.case_question(live, "Real Test Product")
    assert module.case_question(knowledge, "Real Test Product") == knowledge["input"]


def test_cli_requires_explicit_live_and_limits_execution_budget(tmp_path):
    module = runner()
    base = ["--phase", "inventory", "--manifest", str(tmp_path / "x.json")]
    with pytest.raises(SystemExit):
        module.parse_args(base)
    with pytest.raises(SystemExit):
        module.parse_args([*base, "--enable-live", "--budget-seconds", "600"])
    args = module.parse_args([*base, "--enable-live", "--budget-seconds", "540"])
    assert args.budget_seconds == 540


@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint", ["suggest", "logistics-event-preview"])
async def test_unknown_model_response_is_not_replayed_and_public_approval_never_calls_transport(
    tmp_path, monkeypatch, endpoint
):
    from unittest.mock import AsyncMock

    import httpx

    module = runner()
    monkeypatch.setattr(module, "ARTIFACT_ROOT", tmp_path)
    state = module.new_manifest("a" * 64)
    args = SimpleNamespace(manifest=tmp_path / "state.json")
    client = SimpleNamespace(request=AsyncMock(side_effect=httpx.ReadTimeout("synthetic private detail")))
    service = module.Runner(args, state, {}, client)
    path = (
        "/v1/workspace/sessions/00000000-0000-4000-8000-000000000001/suggest"
        if endpoint == "suggest"
        else "/v1/agents/00000000-0000-4000-8000-000000000001/logistics-event-preview"
    )
    with pytest.raises(module.Blocked, match="api_transport_unknown"):
        await service.api("POST", path, operation="suggest:owned", payload={"trigger_message_id": str(uuid.uuid4())})
    with pytest.raises(module.Blocked, match="model_response_unknown"):
        await service.api("POST", path, operation="suggest:owned", payload={"trigger_message_id": str(uuid.uuid4())})
    with pytest.raises(module.Blocked, match="synthetic_public_approval_forbidden"):
        await service.api(
            "POST",
            "/v1/knowledge/files/00000000-0000-4000-8000-000000000001/versions/1/approve",
            payload={"purpose": "public_reply"},
        )
    assert client.request.await_count == 1
    assert "Idempotency-Key" in client.request.await_args.kwargs["headers"]
    assert "synthetic private detail" not in args.manifest.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_cleanup_unknown_creation_blocks_before_touching_any_asset(tmp_path, monkeypatch):
    from unittest.mock import AsyncMock

    module = runner()
    monkeypatch.setattr(module, "ARTIFACT_ROOT", tmp_path)
    state = module.new_manifest("a" * 64)
    state["operations"]["apply:us:template"] = {"state": "unknown", "idempotency_key": str(uuid.uuid4())}
    client = SimpleNamespace(request=AsyncMock())
    service = module.Runner(SimpleNamespace(manifest=tmp_path / "state.json"), state, {}, client)
    import builtins

    original_import = builtins.__import__

    def offline_import(name, *args, **kwargs):
        if name == "app" or name.startswith("app."):
            pytest.fail("offline cleanup imported application/settings")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", offline_import)
    with pytest.raises(module.Blocked, match="unresolved_creations"):
        await service.cleanup()
    client.request.assert_not_awaited()


@pytest.mark.asyncio
async def test_fallback_reset_uses_a_versioned_resolved_shipping_question():
    from unittest.mock import AsyncMock

    module = runner()
    config_id = str(uuid.uuid4())
    asset = {
        "kind": "agent",
        "key": "reply_fallback_v1",
        "store_id": module.STORES["us"],
        "id": config_id,
        "code": "owned",
        "revision": 1,
        "version": 1,
        "prepared": True,
    }
    state = {"assets": [asset], "contexts": {"us": {"conversation_id": str(uuid.uuid4()), "unavailable_tools": []}}}
    dataset = json.loads(module.DATASET.read_text(encoding="utf-8"))
    subject = module.Runner(SimpleNamespace(entry="suggest"), state, dataset, None)
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
    subject.suggest = AsyncMock(side_effect=module.Blocked("stop_before_any_model_call"))
    case = next(item for item in dataset["cases"] if item["id"] == "fallback_en")
    with pytest.raises(module.Blocked, match="stop_before_any_model_call"):
        await subject.run_case("us", case)
    expected = next(item for item in dataset["cases"] if item["id"] == "order_knowledge_en")
    assert subject.suggest.await_args.args == (
        "us",
        f"{subject.case_key('fallback_en', 'us')}:verified-order-reset-v2",
        expected["input"],
        "en",
    )
