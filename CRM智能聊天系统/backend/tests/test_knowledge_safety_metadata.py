"""验证架构批准的知识语义类型与发布审批安全边界。"""

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

from app.agent.business_claims import BusinessClaimInventory
from app.agent.reply_safety import ReplyContentOrigin, ReplyEvidenceKind, ReplySafetyPolicy
from app.audit.models import AuditLog
from app.knowledge_base import service as knowledge_service
from app.knowledge_base.schemas import (
    KnowledgeCustomerScope,
    KnowledgeEntryCreate,
    KnowledgeEntryUpdate,
    KnowledgePublicationApproval,
    KnowledgeSafetyMetadata,
    KnowledgeStatementType,
)
from app.knowledge_base.vector_port import _row_safety_metadata
from app.shared.exceptions.errors import AppError


class MemorySession:
    """为知识发布和更新规则提供最小异步会话端口。"""

    def __init__(self) -> None:
        self.added: list[object] = []
        self.commits = 0

    def add(self, value: object) -> None:
        self.added.append(value)

    async def commit(self) -> None:
        self.commits += 1

    async def refresh(self, _value: object) -> None:
        return None


@pytest.mark.asyncio
async def test_create_entry_audit_uses_the_created_document_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """创建审计必须绑定预先生成的资源 ID，不能依赖提交时才执行的 ORM 默认值。"""
    store_id = uuid.uuid4()
    user = SimpleNamespace(id=uuid.uuid4())
    session = MemorySession()

    async def allow(*_: object) -> None:
        return None

    monkeypatch.setattr(knowledge_service, "ensure_store_access", allow)

    document = await knowledge_service.create_entry(
        session,  # type: ignore[arg-type]
        user,  # type: ignore[arg-type]
        KnowledgeEntryCreate(
            store_id=store_id,
            question="如何退货？",
            answer="请按页面指引提交申请。",
            statement_type=KnowledgeStatementType.POLICY,
            customer_scope=KnowledgeCustomerScope.GENERIC,
        ),
    )

    audit = session.added[1]
    assert document.id is not None
    assert isinstance(audit, AuditLog)
    assert audit.resource_id == document.id
    assert session.commits == 1


def document_namespace(
    *,
    statement_type: str = "technical_artifact",
    customer_scope: str = "none",
) -> SimpleNamespace:
    """构造已审批知识当前版本，不依赖数据库连接。"""
    approved_at = datetime.now(UTC)
    return SimpleNamespace(
        id=uuid.uuid4(),
        store_id=uuid.uuid4(),
        category_id=None,
        question="退款接口契约是什么？",
        answer="该契约用于开发联调。",
        title="退款接口契约是什么？",
        content_hash=knowledge_service.content_hash("退款接口契约是什么？", "该契约用于开发联调。"),
        status="published",
        vectorization_status="ready",
        document_version=3,
        statement_type=statement_type,
        customer_scope=customer_scope,
        publication_approval="approved_for_internal_review",
        semantic_schema_version=1,
        approved_by=uuid.uuid4(),
        approved_at=approved_at,
        published_at=approved_at,
    )


def approved_metadata(
    statement_type: KnowledgeStatementType,
    *,
    store_id: uuid.UUID | None = None,
    document_version: int = 1,
    customer_scope: KnowledgeCustomerScope = KnowledgeCustomerScope.NONE,
) -> KnowledgeSafetyMetadata:
    """构造由知识运营人员审批的当前文档版本元数据。"""
    return KnowledgeSafetyMetadata(
        statement_type=statement_type,
        customer_scope=customer_scope,
        publication_approval=KnowledgePublicationApproval.APPROVED_FOR_INTERNAL_REVIEW,
        semantic_schema_version=1,
        approved_by=uuid.uuid4(),
        approved_at=datetime.now(UTC),
        store_id=store_id or uuid.uuid4(),
        document_version=document_version,
        approved_document_version=document_version,
    )


def evaluate_faq(
    answer: str,
    metadata: list[KnowledgeSafetyMetadata],
    *,
    store_id: uuid.UUID,
) -> object:
    """从生产 FAQ 路径调用确定性门禁。"""
    return ReplySafetyPolicy().evaluate(
        answer,
        evidence_kind=ReplyEvidenceKind.FAQ,
        claim_inventory=BusinessClaimInventory(complete=True, claims=[]),
        content_origin=ReplyContentOrigin.TRUSTED_FAQ_TEMPLATE,
        knowledge_safety_metadata=metadata,
        expected_store_id=store_id,
    )


@pytest.mark.parametrize(
    ("statement_type", "answer"),
    [
        (
            KnowledgeStatementType.TECHNICAL_ARTIFACT,
            "The reimbursement webhook contract is maintained in developer documentation.",
        ),
        (
            KnowledgeStatementType.NON_ASSERTIVE_PROPOSITION,
            "The statement that reimbursement completed remains unsupported by evidence.",
        ),
        (KnowledgeStatementType.POLICY, "签收后七天内可以申请退货。"),
    ],
)
def test_approved_non_customer_knowledge_is_reviewable_but_never_auto_authorized(
    statement_type: KnowledgeStatementType,
    answer: str,
) -> None:
    """已审批政策、技术资产和非断言命题可保留草稿，但 FAQ 不获得自动发送权。"""
    store_id = uuid.uuid4()

    result = evaluate_faq(answer, [approved_metadata(statement_type, store_id=store_id)], store_id=store_id)

    assert result.is_safe is True
    assert result.automatic_delivery_allowed is False
    assert result.reason_codes == []


@pytest.mark.parametrize(
    ("statement_type", "customer_scope", "answer"),
    [
        (
            KnowledgeStatementType.TECHNICAL_ARTIFACT,
            KnowledgeCustomerScope.NONE,
            "界面快照包含占位文案“您的订单已经签收”，仅用于校验徽标宽度。",
        ),
        (
            KnowledgeStatementType.TECHNICAL_ARTIFACT,
            KnowledgeCustomerScope.NONE,
            "回归脚本把“你的订单已经发货”作为本地化夹具，不表示真实订单状态。",
        ),
        (
            KnowledgeStatementType.TECHNICAL_ARTIFACT,
            KnowledgeCustomerScope.NONE,
            "规则文档引用“保证退款到账”作为禁止承诺的反例。",
        ),
        (
            KnowledgeStatementType.TECHNICAL_ARTIFACT,
            KnowledgeCustomerScope.NONE,
            "流程图节点名为“退款 50 元”，用于展示校验失败分支。",
        ),
        (
            KnowledgeStatementType.TECHNICAL_ARTIFACT,
            KnowledgeCustomerScope.NONE,
            "无障碍测试的 aria-label 是“订单已经送达”。",
        ),
        (
            KnowledgeStatementType.TECHNICAL_ARTIFACT,
            KnowledgeCustomerScope.NONE,
            "日志字段字典定义 delivery_status=delivered，但没有客户实例。",
        ),
        (
            KnowledgeStatementType.TECHNICAL_ARTIFACT,
            KnowledgeCustomerScope.NONE,
            "The UI fixture says ‘your order has been delivered’ to verify line wrapping.",
        ),
        (
            KnowledgeStatementType.TECHNICAL_ARTIFACT,
            KnowledgeCustomerScope.NONE,
            "The policy linter uses ‘we guarantee a refund’ as a forbidden-copy example.",
        ),
        (
            KnowledgeStatementType.TECHNICAL_ARTIFACT,
            KnowledgeCustomerScope.NONE,
            "A test badge reads ‘package has arrived’ without referencing a live shipment.",
        ),
        (
            KnowledgeStatementType.TECHNICAL_ARTIFACT,
            KnowledgeCustomerScope.NONE,
            "The schema example stores refund 25 USD as invalid sample input.",
        ),
        (
            KnowledgeStatementType.TECHNICAL_ARTIFACT,
            KnowledgeCustomerScope.NONE,
            "The callback mock returns address has been updated for parser testing only.",
        ),
        (
            KnowledgeStatementType.TECHNICAL_ARTIFACT,
            KnowledgeCustomerScope.NONE,
            "The translation glossary maps order cancelled to the status code CANCELLED.",
        ),
        (
            KnowledgeStatementType.NON_ASSERTIVE_PROPOSITION,
            KnowledgeCustomerScope.GENERIC,
            "系统尚未确认您的订单已经发货。",
        ),
        (
            KnowledgeStatementType.NON_ASSERTIVE_PROPOSITION,
            KnowledgeCustomerScope.GENERIC,
            "不能据此断定包裹已经签收。",
        ),
        (
            KnowledgeStatementType.NON_ASSERTIVE_PROPOSITION,
            KnowledgeCustomerScope.GENERIC,
            "如果退款已经到账，页面才会出现可用余额提示。",
        ),
        (
            KnowledgeStatementType.NON_ASSERTIVE_PROPOSITION,
            KnowledgeCustomerScope.GENERIC,
            "客服引用了“保证退款到账”，但明确说明该承诺无效。",
        ),
        (
            KnowledgeStatementType.NON_ASSERTIVE_PROPOSITION,
            KnowledgeCustomerScope.GENERIC,
            "尚无证据表明地址已经更新。",
        ),
        (
            KnowledgeStatementType.NON_ASSERTIVE_PROPOSITION,
            KnowledgeCustomerScope.GENERIC,
            "示例中的优惠券已发放不代表任何真实动作。",
        ),
        (
            KnowledgeStatementType.NON_ASSERTIVE_PROPOSITION,
            KnowledgeCustomerScope.GENERIC,
            "We have not confirmed that your order has shipped.",
        ),
        (
            KnowledgeStatementType.NON_ASSERTIVE_PROPOSITION,
            KnowledgeCustomerScope.GENERIC,
            "If the parcel had arrived, a carrier scan would be required.",
        ),
        (
            KnowledgeStatementType.NON_ASSERTIVE_PROPOSITION,
            KnowledgeCustomerScope.GENERIC,
            "The phrase ‘we guarantee a refund’ is quoted as prohibited wording.",
        ),
        (
            KnowledgeStatementType.NON_ASSERTIVE_PROPOSITION,
            KnowledgeCustomerScope.GENERIC,
            "No evidence establishes that the shipping address has been updated.",
        ),
        (
            KnowledgeStatementType.NON_ASSERTIVE_PROPOSITION,
            KnowledgeCustomerScope.GENERIC,
            "A coupon marked issued in a mock example is not a customer outcome.",
        ),
        (
            KnowledgeStatementType.NON_ASSERTIVE_PROPOSITION,
            KnowledgeCustomerScope.GENERIC,
            "It remains unknown whether the customer's repayment reached the account.",
        ),
    ],
)
def test_approved_non_customer_knowledge_uses_metadata_instead_of_legacy_text_rules(
    statement_type: KnowledgeStatementType,
    customer_scope: KnowledgeCustomerScope,
    answer: str,
) -> None:
    """当前店铺已审批的技术/非断言知识保留草稿，不由旧词法规则硬阻断。"""
    store_id = uuid.uuid4()
    metadata = approved_metadata(
        statement_type,
        store_id=store_id,
        customer_scope=customer_scope,
    )

    result = evaluate_faq(answer, [metadata], store_id=store_id)

    assert result.is_safe is True
    assert result.automatic_delivery_allowed is False
    assert result.reason_codes == []


def test_customer_instance_fact_requires_current_same_store_tool_evidence() -> None:
    """客户资金、订单等实例事实不能凭已发布 FAQ 获得陈述资格。"""
    store_id = uuid.uuid4()
    metadata = approved_metadata(
        KnowledgeStatementType.CUSTOMER_INSTANCE_FACT,
        store_id=store_id,
        customer_scope=KnowledgeCustomerScope.SPECIFIC_CUSTOMER,
    )

    result = evaluate_faq(
        "The customer's purchasing allowance returned after the charge was annulled.",
        [metadata],
        store_id=store_id,
    )

    assert result.is_safe is False
    assert result.automatic_delivery_allowed is False
    assert "KNOWLEDGE_CUSTOMER_FACT_REQUIRES_TOOL" in result.reason_codes


@pytest.mark.parametrize("metadata", [[], None])
def test_missing_or_untyped_knowledge_fails_closed(metadata: list[KnowledgeSafetyMetadata] | None) -> None:
    """旧 FAQ、缺失元数据和未迁移调用方都不能绕过发布审批。"""
    store_id = uuid.uuid4()

    result = ReplySafetyPolicy().evaluate(
        "退款协议词典服务于开发。",
        evidence_kind=ReplyEvidenceKind.FAQ,
        claim_inventory=BusinessClaimInventory(complete=True, claims=[]),
        content_origin=ReplyContentOrigin.TRUSTED_FAQ_TEMPLATE,
        knowledge_safety_metadata=metadata,
        expected_store_id=store_id,
    )

    assert result.is_safe is False
    assert "KNOWLEDGE_SAFETY_METADATA_MISSING" in result.reason_codes


def test_cross_store_or_stale_approval_fails_closed() -> None:
    """审批不能跨店铺使用，也不能从旧文档版本复制到新版本。"""
    expected_store_id = uuid.uuid4()
    other_store_metadata = approved_metadata(
        KnowledgeStatementType.TECHNICAL_ARTIFACT,
        store_id=uuid.uuid4(),
        document_version=1,
    )
    stale_metadata = approved_metadata(
        KnowledgeStatementType.TECHNICAL_ARTIFACT,
        store_id=expected_store_id,
        document_version=1,
    ).model_copy(update={"approved_document_version": 2})

    cross_store = evaluate_faq("技术接口契约。", [other_store_metadata], store_id=expected_store_id)
    stale = evaluate_faq("技术接口契约。", [stale_metadata], store_id=expected_store_id)

    assert "KNOWLEDGE_SAFETY_STORE_MISMATCH" in cross_store.reason_codes
    assert "KNOWLEDGE_SAFETY_VERSION_MISMATCH" in stale.reason_codes


def test_approved_metadata_requires_approver_and_time() -> None:
    """数据库/API 不能构造没有审批人或审批时间的伪批准记录。"""
    with pytest.raises(ValidationError):
        KnowledgeSafetyMetadata(
            statement_type=KnowledgeStatementType.TECHNICAL_ARTIFACT,
            customer_scope=KnowledgeCustomerScope.NONE,
            publication_approval=KnowledgePublicationApproval.APPROVED_FOR_INTERNAL_REVIEW,
            semantic_schema_version=1,
            approved_by=None,
            approved_at=None,
            store_id=uuid.uuid4(),
            document_version=1,
            approved_document_version=1,
        )


@pytest.mark.asyncio
async def test_unknown_document_cannot_publish_or_mutate_in_memory_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """审批校验失败时既不能提交，也不能把当前会话对象提前改成 published。"""
    document = document_namespace(statement_type="unknown")
    document.status = "draft"
    document.publication_approval = "draft"
    document.approved_by = None
    document.approved_at = None
    document.published_at = None
    user = SimpleNamespace(id=uuid.uuid4())
    session = MemorySession()

    async def allowed(*_: object) -> set[uuid.UUID]:
        return {document.store_id}

    async def found(*_: object) -> SimpleNamespace:
        return document

    monkeypatch.setattr(knowledge_service, "allowed_store_ids", allowed)
    monkeypatch.setattr(knowledge_service, "find_document", found)

    with pytest.raises(AppError, match="发布前"):
        await knowledge_service.set_entry_status(session, user, document.id, "published")  # type: ignore[arg-type]

    assert document.status == "draft"
    assert document.publication_approval == "draft"
    assert session.commits == 0


@pytest.mark.asyncio
async def test_semantic_change_revokes_approval_and_increments_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """语义类型或正文变化必须回到草稿，旧审批和旧向量不能继续使用。"""
    document = document_namespace()
    user = SimpleNamespace(id=uuid.uuid4())
    session = MemorySession()

    async def allowed(*_: object) -> set[uuid.UUID]:
        return {document.store_id}

    async def found(*_: object) -> SimpleNamespace:
        return document

    monkeypatch.setattr(knowledge_service, "allowed_store_ids", allowed)
    monkeypatch.setattr(knowledge_service, "find_document", found)

    result = await knowledge_service.update_entry(
        session,  # type: ignore[arg-type]
        user,  # type: ignore[arg-type]
        document.id,
        KnowledgeEntryUpdate(
            statement_type=KnowledgeStatementType.NON_ASSERTIVE_PROPOSITION,
            customer_scope=KnowledgeCustomerScope.GENERIC,
        ),
    )

    assert result.document_version == 4
    assert result.status == "draft"
    assert result.vectorization_status == "pending"
    assert result.publication_approval == KnowledgePublicationApproval.DRAFT
    assert result.approved_by is None and result.approved_at is None
    assert result.published_at is None
    assert session.commits == 1


@pytest.mark.asyncio
async def test_invalid_semantic_update_does_not_mutate_the_loaded_document(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """候选语义字段必须先校验，失败请求不能污染当前会话中的 ORM 对象。"""
    document = document_namespace()
    original_statement_type = document.statement_type
    original_customer_scope = document.customer_scope
    user = SimpleNamespace(id=uuid.uuid4())
    session = MemorySession()

    async def allowed(*_: object) -> set[uuid.UUID]:
        return {document.store_id}

    async def found(*_: object) -> SimpleNamespace:
        return document

    monkeypatch.setattr(knowledge_service, "allowed_store_ids", allowed)
    monkeypatch.setattr(knowledge_service, "find_document", found)

    with pytest.raises(AppError, match="知识语义类型与客户范围不一致"):
        await knowledge_service.update_entry(
            session,  # type: ignore[arg-type]
            user,  # type: ignore[arg-type]
            document.id,
            KnowledgeEntryUpdate(
                statement_type=KnowledgeStatementType.POLICY,
                customer_scope=KnowledgeCustomerScope.SPECIFIC_CUSTOMER,
            ),
        )

    assert document.statement_type == original_statement_type
    assert document.customer_scope == original_customer_scope
    assert session.commits == 0


def test_forged_chunk_metadata_is_downgraded_instead_of_trusted() -> None:
    """切片 JSON 即使被改成更宽松类型，也不能覆盖文档权威审批字段。"""
    store_id = uuid.uuid4()
    approver_id = uuid.uuid4()
    approved_at = datetime.now(UTC)
    authoritative: dict[str, Any] = {
        "store_id": store_id,
        "document_version": 2,
        "statement_type": "technical_artifact",
        "customer_scope": "none",
        "publication_approval": "approved_for_internal_review",
        "semantic_schema_version": 1,
        "approved_by": approver_id,
        "approved_at": approved_at,
    }
    forged = KnowledgeSafetyMetadata.model_validate(
        {
            **authoritative,
            "statement_type": "policy",
            "approved_document_version": 2,
        }
    ).model_dump(mode="json")

    result = _row_safety_metadata({**authoritative, "metadata_json": {"knowledge_safety": forged}})

    assert result.statement_type == KnowledgeStatementType.UNKNOWN
    assert result.publication_approval == KnowledgePublicationApproval.DRAFT


@pytest.mark.parametrize(
    "answer",
    [
        "退款协议词典服务于开发；收单冲销后，付款主体的账户购买力已经恢复正常。",
        "返款事件图存于模型仓库；结算逆转款已使买受方的购物额度重新生效。",
        "The refund governance model is versioned; the customer's purchasing allowance returned "
        "to its former level after a charge annulment.",
        "The compensation schema graph serves integration; the recipient's spending buffer resumed "
        "usability once the original debit was unwound.",
        "The compensation taxonomy document supports governance; the orderer's payment reserve became "
        "spendable again after the charge was rescinded.",
        "The reimbursement integration model is documentation; the customer's preloaded monetary holding "
        "regained availability after a transaction-cancellation credit.",
    ],
)
def test_report_008_customer_instance_failures_are_closed_by_structured_type(answer: str) -> None:
    """008 报告的六条漏放样本由客户实例类型稳定失败关闭，不再追加词表。"""
    store_id = uuid.uuid4()
    metadata = approved_metadata(
        KnowledgeStatementType.CUSTOMER_INSTANCE_FACT,
        store_id=store_id,
        customer_scope=KnowledgeCustomerScope.SPECIFIC_CUSTOMER,
    )

    result = evaluate_faq(answer, [metadata], store_id=store_id)

    assert result.is_safe is False
    assert "KNOWLEDGE_CUSTOMER_FACT_REQUIRES_TOOL" in result.reason_codes


@pytest.mark.parametrize(
    ("statement_type", "answer"),
    [
        (KnowledgeStatementType.TECHNICAL_ARTIFACT, "退款语义字典被用于血缘分析任务。"),
        (KnowledgeStatementType.TECHNICAL_ARTIFACT, "退费 Protobuf 描述符保存在模式中心。"),
        (KnowledgeStatementType.TECHNICAL_ARTIFACT, "赔付 OpenTelemetry 属性服务于链路观测。"),
        (KnowledgeStatementType.TECHNICAL_ARTIFACT, "补偿 CDC 流名称属于同步配置。"),
        (KnowledgeStatementType.TECHNICAL_ARTIFACT, "返款 ORM 实体映射由代码生成器维护。"),
        (KnowledgeStatementType.TECHNICAL_ARTIFACT, "退款契约基准样本用于兼容性测试。"),
        (KnowledgeStatementType.NON_ASSERTIVE_PROPOSITION, "“退款款项已经到账”这一主张仍需证据裁定。"),
        (KnowledgeStatementType.NON_ASSERTIVE_PROPOSITION, "复核备忘录没有采纳补偿余额已恢复的判断。"),
        (KnowledgeStatementType.NON_ASSERTIVE_PROPOSITION, "检查记录未就返款是否完成作出肯定结论。"),
        (KnowledgeStatementType.NON_ASSERTIVE_PROPOSITION, "将退费已入账当作现状目前缺少可验证根据。"),
        (KnowledgeStatementType.NON_ASSERTIVE_PROPOSITION, "现有材料不足以推导赔偿款已经进入账户。"),
        (KnowledgeStatementType.NON_ASSERTIVE_PROPOSITION, "退款完成属于尚未获得证成的陈述。"),
        (
            KnowledgeStatementType.TECHNICAL_ARTIFACT,
            "The refund semantic dictionary is consumed by lineage analysis.",
        ),
        (
            KnowledgeStatementType.TECHNICAL_ARTIFACT,
            "The compensation OpenTelemetry attribute supports trace observability.",
        ),
        (
            KnowledgeStatementType.TECHNICAL_ARTIFACT,
            "The refund CDC stream name belongs to synchronization settings.",
        ),
        (
            KnowledgeStatementType.TECHNICAL_ARTIFACT,
            "The reimbursement ORM entity mapping is maintained by a code generator.",
        ),
        (
            KnowledgeStatementType.TECHNICAL_ARTIFACT,
            "The compensation contract baseline sample is used for compatibility tests.",
        ),
        (
            KnowledgeStatementType.NON_ASSERTIVE_PROPOSITION,
            "The assertion that the refund posted still awaits evidentiary adjudication.",
        ),
        (
            KnowledgeStatementType.NON_ASSERTIVE_PROPOSITION,
            "The review memorandum declines to endorse that compensation restored the balance.",
        ),
        (
            KnowledgeStatementType.NON_ASSERTIVE_PROPOSITION,
            "The inspection record makes no affirmative determination on whether reimbursement completed.",
        ),
        (
            KnowledgeStatementType.NON_ASSERTIVE_PROPOSITION,
            "Describing the refund as posted currently lacks a verifiable ground.",
        ),
        (
            KnowledgeStatementType.NON_ASSERTIVE_PROPOSITION,
            "The available material is insufficient to infer that compensation entered the account.",
        ),
        (
            KnowledgeStatementType.NON_ASSERTIVE_PROPOSITION,
            "Refund completion remains an unsubstantiated proposition.",
        ),
    ],
)
def test_report_008_legal_failures_remain_reviewable_with_approved_type(
    statement_type: KnowledgeStatementType,
    answer: str,
) -> None:
    """008 报告的二十三条误杀样本由人工审批类型保留为安全人工草稿。"""
    store_id = uuid.uuid4()

    result = evaluate_faq(answer, [approved_metadata(statement_type, store_id=store_id)], store_id=store_id)

    assert result.is_safe is True
    assert result.automatic_delivery_allowed is False
    assert result.reason_codes == []
