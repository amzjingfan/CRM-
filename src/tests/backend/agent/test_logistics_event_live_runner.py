"""物流真实模型组件 runner 的离线边界；这些测试绝不调用模型或数据库。"""

import importlib.util
import os
import subprocess
import sys
from types import SimpleNamespace

import pytest
from _support import SOURCE_ROOT

RUNNER = SOURCE_ROOT / "tests/ai/logistics_event_model_live.py"


def load_runner():
    spec = importlib.util.spec_from_file_location("logistics_event_model_live", RUNNER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_no_opt_in_exits_before_app_import_or_environment_access(tmp_path):
    result = subprocess.run(
        [sys.executable, str(RUNNER), "--output", str(tmp_path / "denied.json")],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
        env={key: os.environ[key] for key in ("SystemRoot", "WINDIR", "PATH") if key in os.environ},
    )
    assert result.returncode == 2
    assert "explicit_live_opt_in_required" in result.stderr
    assert not (tmp_path / "denied.json").exists()


@pytest.mark.parametrize(
    "database",
    [
        "postgresql+asyncpg://test:unused@staging.example/crm_test",
        "postgresql+asyncpg://test:unused@127.0.0.1/crm",
        "postgresql+asyncpg://test:unused@127.0.0.1/crm_production",
        "postgresql+asyncpg://test:unused@127.0.0.1/crm_test?host=staging.example",
        "sqlite:///crm_test",
        "",
    ],
)
def test_database_guard_refuses_remote_or_unapproved_database(database):
    runner = load_runner()
    with pytest.raises(runner.Blocked):
        runner.validate_database_environment({"TEST_DATABASE_URL": database})


def test_database_guard_uses_test_url_and_rejects_staging_database_alias():
    runner = load_runner()
    target = "postgresql+asyncpg://test:unused@127.0.0.1:56876/crm_test"
    assert runner.validate_database_environment({"TEST_DATABASE_URL": target}) == target
    with pytest.raises(runner.Blocked):
        runner.validate_database_environment(
            {"TEST_DATABASE_URL": target, "DATABASE_URL": target.replace("crm_test", "crm")}
        )


def test_output_cannot_leave_owned_artifact_directory_or_overwrite(tmp_path):
    runner = load_runner()
    with pytest.raises(runner.Blocked):
        runner.validate_output(tmp_path / "foreign.json")
    with pytest.raises(runner.Blocked):
        runner.validate_output(RUNNER)
    runner.ARTIFACT_ROOT = tmp_path
    owned = tmp_path / "owned.json"
    assert runner.validate_output(owned) == owned.resolve()
    owned.write_text("previous evidence", encoding="utf-8")
    with pytest.raises(runner.Blocked):
        runner.validate_output(owned)


def test_live_opt_in_with_foreign_database_fails_before_app_import(tmp_path, monkeypatch, capsys):
    runner = load_runner()
    monkeypatch.setenv("TEST_DATABASE_URL", "postgresql+asyncpg://test:unused@staging.example/crm")
    assert runner.main(["--enable-live", "--output", str(tmp_path / "denied.json")]) == 2
    assert capsys.readouterr().err.strip() == "isolated_loopback_test_database_required"
    assert not (tmp_path / "denied.json").exists()


def test_exception_classification_never_echoes_third_party_payloads():
    runner = load_runner()
    assert runner.classify(ValueError("private-provider-response-token")) == "component_execution_failed"
    assert runner.classify(ValueError("notification_required_tool_missing")) == "notification_required_tool_missing"


@pytest.mark.parametrize(
    "unsafe",
    [
        "real_tiktok_read_enabled",
        "real_tiktok_message_write_enabled",
        "real_tiktok_automation_enabled",
        "auto_reply_enabled",
        "real_tiktok_logistics_notifications_enabled",
        "ai_marketing_enabled",
        "allow_mock_platform_adapters",
        "logistics_notifications_enabled",
    ],
)
def test_runtime_guard_refuses_any_external_platform_capability(unsafe):
    runner = load_runner()
    settings = SimpleNamespace(
        app_env="integration",
        llm_enabled=True,
        llm_primary_provider="deepseek",
        llm_primary_model="deepseek-chat",
        embedding_enabled=True,
        embedding_provider="local_bge",
        embedding_model="BAAI/bge-m3",
        embedding_dimensions=1024,
        real_tiktok_read_enabled=False,
        real_tiktok_webhook_enabled=False,
        real_tiktok_message_write_enabled=False,
        real_tiktok_high_risk_write_enabled=False,
        real_tiktok_automation_enabled=False,
        auto_reply_enabled=False,
        real_tiktok_logistics_notifications_enabled=False,
        ai_marketing_enabled=False,
        allow_mock_platform_adapters=False,
        logistics_notifications_enabled=False,
    )
    runner.validate_runtime(settings)
    setattr(settings, unsafe, True)
    with pytest.raises(runner.Blocked):
        runner.validate_runtime(settings)


@pytest.fixture
def relevant_case():
    runner = load_runner()
    events = [
        SimpleNamespace(name=name, status=status)
        for name, status in (
            ("query_order", "succeeded"),
            ("query_logistics", "succeeded"),
            ("search_knowledge", "retrieved"),
            ("notify_logistics_update", "proposed"),
        )
    ]
    chunk_map = {"first": runner.KNOWLEDGE, "second": runner.KNOWLEDGE_CONTEXT}
    hit = SimpleNamespace(
        chunk_id="second",
        document_id="owned-file",
        document_version=1,
        safety_metadata=SimpleNamespace(store_id="owned-store"),
        content=runner.KNOWLEDGE_CONTEXT,
    )
    return runner, dict(
        language="en",
        body="Your parcel arrived at Cedar Hub and remains in transit.",
        events=events,
        citations=("second",),
        evidence={"second": runner.KNOWLEDGE_CONTEXT},
        frozen_chunks=chunk_map,
        retrieved_hits=[hit],
        store_id="owned-store",
        file_id="owned-file",
        document_version=1,
        review_status="approved",
    )


@pytest.mark.parametrize("choice", ["first", "second", "both"])
@pytest.mark.parametrize(
    "language,body",
    [
        ("en", "Your parcel arrived at Cedar Hub and remains in transit."),
        ("zh", "您的包裹已到达雪松分拣中心，仍在运输中。"),
    ],
)
def test_second_relevant_chunk_alone_is_valid_when_exactly_retrieved(relevant_case, choice, language, body):
    runner, valid = relevant_case
    selected = ("first", "second") if choice == "both" else (choice,)
    valid.update(
        language=language,
        body=body,
        citations=selected,
        evidence={key: valid["frozen_chunks"][key] for key in selected},
        retrieved_hits=[
            SimpleNamespace(
                chunk_id=key,
                document_id="owned-file",
                document_version=1,
                safety_metadata=SimpleNamespace(store_id="owned-store"),
                content=valid["frozen_chunks"][key],
            )
            for key in selected
        ],
    )
    projection = runner.validate_case(**valid)
    assert projection["owned_file_fact_seen"] is True
    assert len(projection["citation_evidence"]) == len(selected)
    assert projection["citation_evidence"][0]["actually_retrieved"] is True
    assert all(key not in str(projection) for key in selected)


@pytest.mark.parametrize(
    "changed",
    [
        "foreign",
        "mixed_foreign",
        "same_file_unrelated",
        "empty",
        "wrong_text",
        "retrieved_wrong_text",
        "arbitrary_frozen_map",
        "not_retrieved",
        "wrong_file",
        "wrong_store",
        "wrong_version",
        "missing_tool",
        "review_rejected",
        "old_history",
        "wrong_language",
    ],
)
def test_case_rejects_unowned_unverified_or_unapproved_evidence(relevant_case, changed):
    runner, valid = relevant_case
    if changed in {"foreign", "same_file_unrelated"}:
        valid["citations"] = (changed,)
        valid["evidence"] = {changed: runner.KNOWLEDGE_CONTEXT}
        valid["retrieved_hits"] = [
            SimpleNamespace(
                chunk_id=changed,
                document_id="owned-file",
                document_version=1,
                safety_metadata=SimpleNamespace(store_id="owned-store"),
                content=runner.KNOWLEDGE_CONTEXT,
            )
        ]
    elif changed == "mixed_foreign":
        valid["citations"] = ("second", "foreign")
    elif changed == "empty":
        valid["citations"] = ()
    elif changed == "wrong_text":
        valid["evidence"] = {"second": "Unrelated policy, not the frozen paragraph."}
    elif changed == "retrieved_wrong_text":
        valid["retrieved_hits"][0].content = "An unrelated policy was returned by retrieval."
    elif changed == "arbitrary_frozen_map":
        valid["frozen_chunks"]["second"] = "An unrelated policy, not either frozen related paragraph."
    elif changed == "not_retrieved":
        valid["retrieved_hits"] = []
    elif changed == "wrong_file":
        valid["retrieved_hits"][0].document_id = "foreign-file"
    elif changed == "wrong_store":
        valid["retrieved_hits"][0].safety_metadata.store_id = "foreign-store"
    elif changed == "wrong_version":
        valid["retrieved_hits"][0].document_version = 2
    elif changed == "missing_tool":
        valid["events"] = valid["events"][:-1]
    elif changed == "review_rejected":
        valid["review_status"] = "rejected"
    elif changed == "old_history":
        valid["body"] = "OLD-HISTORY-DO-NOT-REPORT Cedar Hub"
    elif changed == "wrong_language":
        valid["body"] = "包裹已到达雪松分拣中心。"
    with pytest.raises(runner.Blocked):
        runner.validate_case(**valid)


def test_failed_case_keeps_only_safe_native_progress():
    runner = load_runner()
    model = SimpleNamespace(
        tool_events=[
            SimpleNamespace(name="query_order", status="succeeded"),
            SimpleNamespace(name="private-response", status="private-token"),
        ],
        input_tokens=31,
        output_tokens=17,
        citations=(),
        toolset=SimpleNamespace(citations=["private-chunk-identifier"]),
    )
    result = runner.case_progress(
        model, phase="generate", elapsed=1.25, error=ValueError("notification_required_tool_missing")
    )
    assert result["status"] == "failed"
    assert result["reason"] == "notification_required_tool_missing"
    assert result["phase"] == "generate"
    assert result["input_tokens"] == 31 and result["output_tokens"] == 17
    assert result["citation_count"] == 1
    assert result["tool_calls"] == [
        {"name": "query_order", "status": "succeeded"},
        {"name": "unavailable", "status": "unavailable"},
    ]
    assert "private" not in str(result)


def test_failed_case_preserves_shared_loop_failure_and_timeout_statuses():
    runner = load_runner()
    model = SimpleNamespace(
        tool_events=[
            SimpleNamespace(name="notify_logistics_update", status=status)
            for status in ("tool_failed", "tool_unavailable", "cancelled", "timeout", "tool_result_too_large")
        ],
        input_tokens=7,
        output_tokens=3,
        citations=(),
        toolset=None,
    )
    result = runner.case_progress(model, phase="generate", elapsed=2, error=TimeoutError("private-provider-body"))
    assert [event["status"] for event in result["tool_calls"]] == [
        "tool_failed",
        "tool_unavailable",
        "cancelled",
        "timeout",
        "tool_result_too_large",
    ]
    assert result["reason"] == "component_timeout"
    assert "private" not in str(result)


@pytest.mark.asyncio
async def test_two_fixture_paragraphs_need_two_real_provider_vectors():
    runner = load_runner()

    class Provider:
        async def embed(self, texts):
            return SimpleNamespace(
                provider="local_bge",
                model="BAAI/bge-m3",
                vectors=[[float(index)] * 1024 for index, _ in enumerate(texts)],
            )

    result = await runner.embed_fixture(Provider(), "BAAI/bge-m3")
    assert len(result.vectors) == 2
    assert result.vectors[0][0] == 0 and result.vectors[1][0] == 1

    class IncompleteProvider:
        async def embed(self, texts):
            return SimpleNamespace(provider="local_bge", model="BAAI/bge-m3", vectors=[[0.0] * 1024])

    with pytest.raises(runner.Blocked):
        await runner.embed_fixture(IncompleteProvider(), "BAAI/bge-m3")
