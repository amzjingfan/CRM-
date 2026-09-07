"""Phase 3 知识、工具和营销领域的确定性测试。"""

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.conversations.models import Message
from app.integrations.adapters import MockHmacAdapter
from app.integrations.schemas import ReviewUpdatedEvent
from app.knowledge_base import service as knowledge_service
from app.knowledge_base.importer import parse_import
from app.knowledge_base.repository import list_documents
from app.knowledge_base.schemas import VectorChunkInput
from app.knowledge_base.service import content_hash
from app.main import app
from app.marketing.schemas import CampaignCreate
from app.marketing.worker import NON_RETRYABLE_ERRORS
from app.shared.exceptions.errors import AppError
from app.tools.contracts import TOOL_DEFINITIONS
from app.tools.models import ToolCall
from app.tools.repository import request_hash
from app.workspace import service as workspace_service
from app.workspace.schemas import ReconcileMessageRequest, SendMessageRequest
from scripts.verify_phase3_runtime import phase3_write_headers


def test_csv_import_accepts_minimum_headers() -> None:
    """CSV 只含问题和答案时也应可进入异步导入。"""
    rows = parse_import("question,answer\n如何查物流,请提供订单号\n".encode(), "text/csv")
    assert rows == [{"question": "如何查物流", "answer": "请提供订单号"}]


def test_manual_message_request_requires_explicit_true_confirmation() -> None:
    """缺少确认或传 false 时都不能进入真实平台工具层。"""
    with pytest.raises(ValidationError):
        SendMessageRequest(content="approved")  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        SendMessageRequest(content="approved", confirmed=False)  # type: ignore[arg-type]
    for invalid_value in (1, 0, "true", "false", None, [], {}):
        with pytest.raises(ValidationError):
            SendMessageRequest.model_validate({"content": "approved", "confirmed": invalid_value})
    assert SendMessageRequest(content="approved", confirmed=True).confirmed is True


def test_reconciliation_request_requires_platform_evidence_for_sent() -> None:
    """管理员不能把 unknown 直接改成 sent 而不登记平台消息 ID。"""
    with pytest.raises(ValidationError):
        ReconcileMessageRequest(resolution="sent")
    with pytest.raises(ValidationError):
        ReconcileMessageRequest(resolution="failed", external_message_id="722323407926368819")
    assert ReconcileMessageRequest(resolution="sent", external_message_id="722323407926368819").resolution == "sent"


@pytest.mark.asyncio
async def test_admin_reconciliation_closes_unknown_message_and_tool_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """人工对账应同步消息、工具终态并保留只追加审计。"""
    store_id = uuid.uuid4()
    message = Message(
        id=uuid.uuid4(),
        store_id=store_id,
        conversation_id=uuid.uuid4(),
        platform="tiktok",
        external_message_id=f"pending-{uuid.uuid4()}",
        role="agent",
        direction="outbound",
        content="approved message",
        idempotency_key=str(uuid.uuid4()),
        status="unknown",
        error_code="TOOL_RESULT_UNKNOWN",
        raw_payload={"delivery_mode": "unknown"},
        created_at=datetime.now(UTC),
    )
    tool_call = ToolCall(
        id=uuid.uuid4(),
        store_id=store_id,
        actor_type="user",
        tool_name="send_platform_message",
        idempotency_key=message.idempotency_key,
        request_hash="a" * 64,
        status="unknown",
        input_summary={"content_length": len(message.content)},
    )
    session = Mock(spec=AsyncSession)
    session.scalar = AsyncMock(side_effect=[message, tool_call, None])
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.refresh = AsyncMock()
    session.add = Mock()
    user = SimpleNamespace(id=uuid.uuid4())
    monkeypatch.setattr(workspace_service, "allowed_store_ids", AsyncMock(return_value={store_id}))

    result = await workspace_service.reconcile_unknown_message(
        session,
        user,  # type: ignore[arg-type]
        message.id,
        "sent",
        "722323407926368819",
    )

    assert result.status == "sent"
    assert result.delivery_mode == "real"
    assert message.external_message_id == "722323407926368819"
    assert tool_call.status == "succeeded"
    assert tool_call.output_summary == {"message_id": str(message.id), "status": "sent", "mocked": False}
    session.add.assert_called_once()
    session.commit.assert_awaited_once()


def test_csv_import_rejects_missing_required_header() -> None:
    """缺少答案列必须在写数据库前拒绝。"""
    with pytest.raises(ValueError, match="MISSING_REQUIRED_COLUMNS"):
        parse_import(b"question\nwhere\n", "text/csv")


def test_csv_import_rejects_unknown_columns_to_avoid_private_data() -> None:
    """未声明列可能含隐私数据，导入器应失败关闭。"""
    with pytest.raises(ValueError, match="UNSUPPORTED_COLUMNS"):
        parse_import(b"question,answer,password\nq,a,secret\n", "text/csv")


def test_vector_chunk_requires_exact_dimension() -> None:
    """向量维度错误必须在数据库写入前被拦截。"""
    with pytest.raises(ValidationError, match="1024"):
        VectorChunkInput(chunk_index=0, content="FAQ", token_count=1, embedding=[0.1])


def test_vector_chunk_rejects_non_finite_values() -> None:
    """确定性测试 Provider 也不能把 Infinity 写入 pgvector。"""
    vector = [0.1] * 1024
    vector[10] = float("inf")
    with pytest.raises(ValidationError, match="NaN 或 Infinity"):
        VectorChunkInput(chunk_index=0, content="FAQ", token_count=1, embedding=vector)


def test_content_hash_changes_when_answer_changes() -> None:
    """正文变化应产生新摘要，以驱动文档版本和向量失效。"""
    assert content_hash("q", "a1") != content_hash("q", "a2")


def test_template_campaign_requires_message_content() -> None:
    """模板消息活动没有正文时不能创建。"""
    with pytest.raises(ValidationError, match="模板消息不能为空"):
        CampaignCreate(
            store_id=uuid.uuid4(),
            name="弃单提醒",
            trigger_type="cart_abandoned",
            action_type="send_message",
            content_mode="template",
        )


def test_ai_campaign_can_wait_without_fake_content() -> None:
    """AI 模式允许无模板创建，但 Worker 只会进入 waiting_ai。"""
    payload = CampaignCreate(
        store_id=uuid.uuid4(),
        name="AI 跟进",
        trigger_type="bad_review",
        action_type="send_message",
        content_mode="ai",
    )
    assert payload.content_mode == "ai"


def test_tool_request_hash_is_stable_and_content_sensitive() -> None:
    """参数顺序不影响幂等摘要，但业务内容变化必须产生不同摘要。"""
    first = request_hash("send_coupon", {"coupon": "A", "customer": "1"})
    reordered = request_hash("send_coupon", {"customer": "1", "coupon": "A"})
    changed = request_hash("send_coupon", {"coupon": "B", "customer": "1"})
    assert first == reordered
    assert first != changed


def test_all_write_tools_declare_idempotency() -> None:
    """外部写操作和状态变更工具必须声明幂等要求。"""
    for name in {"update_shipping_address", "send_coupon", "transfer_to_human", "send_platform_message"}:
        assert TOOL_DEFINITIONS[name].idempotency_required is True


def test_review_event_normalizes_through_mock_adapter() -> None:
    """契约级 Mock 适配器必须把中差评事件解析成统一类型。"""
    event = MockHmacAdapter("shopee", "secret").normalize_event(
        {
            "event_type": "review.updated",
            "event_id": "evt-1",
            "external_store_id": "store-1",
            "external_review_id": "review-1",
            "rating": 2,
            "reviewed_at": "2026-08-20T00:00:00Z",
        }
    )
    assert isinstance(event, ReviewUpdatedEvent)
    assert event.rating == 2


def test_phase3_routes_are_registered() -> None:
    """OpenAPI 应暴露知识库、工具和营销接口。"""
    paths = TestClient(app).get("/openapi.json").json()["paths"]
    assert "/v1/knowledge/entries" in paths
    assert "/v1/workspace/actions/order/{order_id}/logistics" in paths
    assert "/v1/marketing/campaigns" in paths


def test_knowledge_entries_openapi_exposes_layer_filter() -> None:
    """知识库层级按钮必须有正式查询参数，不能只在前端过滤当前页。"""
    operation = TestClient(app).get("/openapi.json").json()["paths"]["/v1/knowledge/entries"]["get"]
    assert any(parameter["name"] == "layer" for parameter in operation["parameters"])


@pytest.mark.asyncio
async def test_knowledge_layer_filter_is_applied_before_pagination() -> None:
    """层级条件必须同时进入总数和分页 SQL，保证切换后的数量与翻页一致。"""

    class EmptyScalars:
        def all(self) -> list[object]:
            return []

    class RecordingSession:
        def __init__(self) -> None:
            self.statements: list[object] = []

        async def scalar(self, statement: object) -> int:
            self.statements.append(statement)
            return 0

        async def scalars(self, statement: object) -> EmptyScalars:
            self.statements.append(statement)
            return EmptyScalars()

    store_id = uuid.uuid4()
    session = RecordingSession()
    items, total = await list_documents(
        session,  # type: ignore[arg-type]
        {store_id},
        store_id,
        None,
        "A",
        None,
        None,
        1,
        20,
    )
    assert items == [] and total == 0
    assert len(session.statements) == 2
    assert all("knowledge_categories.layer" in str(statement) for statement in session.statements)


def test_phase3_openapi_documents_write_contract() -> None:
    """知识库和营销写接口必须公开幂等键与全局安全契约。"""
    spec = TestClient(app).get("/openapi.json").json()
    write_operations = [
        ("/v1/knowledge/categories", "post"),
        ("/v1/knowledge/entries", "post"),
        ("/v1/knowledge/imports", "post"),
        ("/v1/marketing/campaigns", "post"),
        ("/v1/workspace/actions/order/{order_id}/shipping-address", "patch"),
    ]
    for path, method in write_operations:
        operation = spec["paths"][path][method]
        parameters = operation["parameters"]
        assert any(item["name"] == "Idempotency-Key" and item["required"] for item in parameters)
        assert "权限" in operation["description"]
    assert "store_id" in spec["info"]["description"]
    assert "40901" in spec["info"]["description"]


def test_manual_message_openapi_requires_idempotency_and_authentication() -> None:
    """人工发送和对账必须公开真实的幂等及认证契约，避免客户端误生成。"""
    spec = TestClient(app).get("/openapi.json").json()
    send_operation = spec["paths"]["/v1/workspace/sessions/{session_id}/messages"]["post"]
    idempotency_parameter = next(item for item in send_operation["parameters"] if item["name"] == "Idempotency-Key")
    assert idempotency_parameter["required"] is True
    assert "副作用" in idempotency_parameter["description"]

    expected_security = [{"BearerAuth": []}, {"CookieAuth": []}]
    assert send_operation["security"] == expected_security
    reconcile_operation = spec["paths"]["/v1/workspace/messages/{message_id}/reconcile"]["post"]
    assert reconcile_operation["security"] == expected_security
    assert set(spec["components"]["securitySchemes"]) >= {"BearerAuth", "CookieAuth"}


def test_unknown_platform_result_is_failure_closed() -> None:
    """外部结果未知时只能终止事件，不能进入自动重试成功路径。"""
    assert "PLATFORM_RESULT_UNKNOWN" in NON_RETRYABLE_ERRORS


@pytest.mark.asyncio
async def test_category_parent_rejects_descendant_cycle(monkeypatch: pytest.MonkeyPatch) -> None:
    """把后代分类设为父级时必须在服务层拒绝，不能只依赖前端选项过滤。"""
    category_id = uuid.uuid4()
    child_id = uuid.uuid4()

    async def fake_find_category(*_: object, **__: object) -> object:
        return SimpleNamespace(id=child_id, parent_id=category_id)

    monkeypatch.setattr(knowledge_service, "find_category", fake_find_category)
    with pytest.raises(AppError, match="循环"):
        await knowledge_service.validate_category_parent(object(), uuid.uuid4(), category_id, child_id)  # type: ignore[arg-type]


def test_runtime_write_headers_are_stable_and_operation_scoped() -> None:
    """运行验收脚本每个写动作应得到稳定且互不冲突的幂等键。"""
    auth = {"Authorization": "Bearer test"}
    first = phase3_write_headers(auth, "fixture", "category-create")
    replay = phase3_write_headers(auth, "fixture", "category-create")
    other = phase3_write_headers(auth, "fixture", "entry-create")
    assert first == replay
    assert first["Idempotency-Key"] != other["Idempotency-Key"]
    assert "Idempotency-Key" not in auth


def test_all_phase3_resource_writes_document_permission_and_store_isolation() -> None:
    """资源级写接口必须在 OpenAPI 中声明具体权限和店铺隔离。"""
    spec = TestClient(app).get("/openapi.json").json()
    operations = [
        ("/v1/knowledge/categories/{category_id}", "patch", "knowledge.manage"),
        ("/v1/knowledge/categories/{category_id}", "delete", "knowledge.manage"),
        ("/v1/knowledge/entries/{entry_id}", "patch", "knowledge.manage"),
        ("/v1/knowledge/entries/{entry_id}", "delete", "knowledge.manage"),
        ("/v1/knowledge/entries/{entry_id}/publish", "post", "knowledge.manage"),
        ("/v1/knowledge/entries/{entry_id}/archive", "post", "knowledge.manage"),
        ("/v1/marketing/campaigns/{campaign_id}", "patch", "marketing.manage"),
        ("/v1/marketing/campaigns/{campaign_id}", "delete", "marketing.manage"),
        ("/v1/marketing/campaigns/{campaign_id}/enable", "post", "marketing.manage"),
        ("/v1/marketing/campaigns/{campaign_id}/disable", "post", "marketing.manage"),
    ]
    for path, method, permission in operations:
        description = spec["paths"][path][method]["description"]
        assert permission in description
        assert "store_id" in description or "店铺" in description
