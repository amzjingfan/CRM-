"""Phase 4 SSE、看板、Agent 运营与团队契约测试。"""

import json
import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.agents.core.reply_policy import AgentReplyProfile, ReplyTone
from app.agents.management.schemas import AgentConfigCreate, AgentConfigUpdate
from app.agents.runtime.models import AgentRun
from app.chat.router import _event
from app.dashboard.aggregation import utc_bounds
from app.dashboard.models import MetricDaily
from app.integrations import adapters
from app.main import app
from app.shared.config.settings import Settings
from app.users.schemas import TeamRoleAssignment


def test_phase4_routes_are_registered() -> None:
    """OpenAPI 必须暴露 SSE 之外的全部 Phase 4 管理接口。"""
    paths = TestClient(app).get("/openapi.json").json()["paths"]
    for path in {
        "/v1/workspace/sessions/{session_id}/suggest",
        "/v1/chat/query",
        "/v1/dashboard/metrics",
        "/v1/dashboard/trend",
        "/v1/agents",
        "/v1/agents/{agent_id}/logs",
        "/v1/settings/team",
        "/v1/settings/team/{member_id}/permanent",
    }:
        assert path in paths


def test_agent_operational_schema_rejects_ai_runtime_fields() -> None:
    """运营 API 不能越权修改模型、Prompt 或阈值。"""
    with pytest.raises(ValidationError, match="extra_forbidden"):
        AgentConfigCreate.model_validate(
            {
                "store_id": str(uuid.uuid4()),
                "name": "客服 Agent",
                "code": "service_agent",
                "enabled_tools": [],
                "llm_model": "forbidden-model",
            }
        )


def test_agent_operational_schema_accepts_only_typed_store_reply_profile() -> None:
    """运营人员可设置受限回复画像，但不能写入任意 Prompt 或模型配置。"""
    profile = {
        "tone": "professional",
        "reply_language": "en",
        "operator_language": "zh-CN",
        "brand_name": "Northwind",
    }
    created = AgentConfigCreate(
        store_id=uuid.uuid4(),
        name="客服 Agent",
        code="service_agent",
        reply_profile=profile,
    )
    updated = AgentConfigUpdate(reply_profile=profile)

    assert created.reply_profile == AgentReplyProfile(
        tone=ReplyTone.PROFESSIONAL,
        reply_language="en",
        operator_language="zh-CN",
        brand_name="Northwind",
    )
    assert updated.reply_profile == created.reply_profile

    with pytest.raises(ValidationError, match="extra_forbidden"):
        AgentConfigUpdate.model_validate({"reply_profile": profile | {"system_prompt": "forbidden"}})


def test_agent_management_accepts_safe_type_and_file_bindings_only() -> None:
    file_id = uuid.uuid4()
    created = AgentConfigCreate(
        store_id=uuid.uuid4(),
        name="客服 Agent",
        code="service_agent",
        agent_type="operations",
        knowledge_file_ids=[file_id],
    )
    assert created.agent_type == "operations"
    assert created.knowledge_file_ids == [file_id]
    assert AgentConfigUpdate(knowledge_file_ids=[]).knowledge_file_ids == []
    with pytest.raises(ValidationError):
        AgentConfigCreate(
            store_id=uuid.uuid4(),
            name="客服 Agent",
            code="service_agent",
            agent_type="automatic_sender",
        )


def test_team_assignment_enforces_explicit_store_scope() -> None:
    """店铺角色缺少店铺范围时必须失败关闭。"""
    with pytest.raises(ValidationError, match="必须指定店铺"):
        TeamRoleAssignment(role="agent", store_id=None)
    with pytest.raises(ValidationError, match="系统级角色"):
        TeamRoleAssignment(role="admin", store_id=uuid.uuid4())


def test_sse_event_keeps_chinese_utf8_and_sequence() -> None:
    """SSE 事件使用 UTF-8 JSON，事件名和顺序号保持稳定。"""
    encoded = _event("delta", 7, {"text": "物流已发出"})
    assert encoded.startswith("id: 7\nevent: delta\n")
    data_line = next(line for line in encoded.splitlines() if line.startswith("data: "))
    assert json.loads(data_line.removeprefix("data: ")) == {"text": "物流已发出"}


def test_store_day_bounds_respect_timezone() -> None:
    """店铺自然日边界必须换算为 UTC，不能使用主机本地时区。"""
    start, end = utc_bounds(date(2026, 8, 22), "Asia/Shanghai")
    assert start.isoformat() == "2026-08-21T16:00:00+00:00"
    assert (end - start).total_seconds() == 86400


def test_mock_adapters_never_claim_real_write_capability(monkeypatch: pytest.MonkeyPatch) -> None:
    """契约级 Mock 在自动发送前必须被能力标识拦截。"""
    settings = Settings(
        _env_file=None,
        JWT_SECRET_KEY="test-secret-key-with-32-characters",
        ALLOW_MOCK_PLATFORM_ADAPTERS="true",
    )
    monkeypatch.setattr(adapters, "get_settings", lambda: settings)

    assert all(not adapters.get_platform_adapter(platform).real_writes for platform in ("tiktok", "shopee", "amazon"))


def test_auto_reply_is_disabled_by_default() -> None:
    """生产自动发送必须显式开启，默认配置保持关闭。"""
    settings = Settings(_env_file=None, jwt_secret_key="test-secret-key-with-32-characters")
    assert settings.auto_reply_enabled is False


def test_phase4_online_ai_metric_columns_and_pricing_configuration_exist() -> None:
    """线上聚合必须具备 RAG、工具、TTFT、Token 与成本的事实字段。"""
    metric_columns = set(MetricDaily.__table__.columns.keys())

    assert {
        "rag_run_count",
        "rag_hit_count",
        "tool_call_count",
        "tool_success_count",
        "first_output_count",
        "p95_first_output_latency_ms",
        "input_tokens",
        "output_tokens",
        "estimated_cost_usd",
        "intent_labeled_count",
        "intent_correct_count",
    } <= metric_columns
    assert "first_output_latency_ms" in AgentRun.__table__.columns

    settings = Settings(
        _env_file=None,
        JWT_SECRET_KEY="test-secret-key-with-32-characters",
        LLM_INPUT_COST_PER_MILLION_USD="0.50",
        LLM_OUTPUT_COST_PER_MILLION_USD="1.50",
    )
    assert str(settings.llm_input_cost_per_million_usd) == "0.50"
    assert str(settings.llm_output_cost_per_million_usd) == "1.50"
