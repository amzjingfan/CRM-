"""验证意图分类领域契约、保守动作和隐私脱敏规则。"""

import uuid

import pytest
from pydantic import ValidationError

from app.agent.providers.base import StructuredRequest
from app.agent.schemas import (
    AgentAction,
    ClassificationCommand,
    ClassificationState,
    IntentModelOutput,
    IntentName,
    MessageContext,
)
from app.agent.security import (
    TRUSTED_PROVIDER_CONTRACT_PROMPT_VERSION,
    TRUSTED_PROVIDER_CONTRACT_SYSTEM_PROMPT,
    PromptSafetyState,
    evaluate_prompt_safety,
    sanitize_prompt_text,
)
from app.agent.service import decide_phase1_action

TRUSTED_PROVIDER_CONTRACT_USER_PROMPT = '{"operation":"provider_contract_check","schema_version":"1","language":"en"}'


def test_classified_output_requires_a_supported_intent() -> None:
    """已分类结果如果没有五类意图之一，必须被结构校验拒绝。"""
    with pytest.raises(ValidationError):
        IntentModelOutput(intent=None, confidence=0.9, classification_state=ClassificationState.CLASSIFIED)


def test_abstained_output_must_not_carry_an_intent() -> None:
    """未知或混合问题不得偷偷携带一个被强行猜测的意图。"""
    with pytest.raises(ValidationError):
        IntentModelOutput(
            intent=IntentName.GENERAL,
            confidence=0.4,
            classification_state=ClassificationState.UNKNOWN,
        )


def test_classification_command_rejects_oversized_context() -> None:
    """历史上下文总量超过安全预算时必须在模型调用前失败。"""
    with pytest.raises(ValidationError):
        ClassificationCommand(
            store_id=uuid.uuid4(),
            conversation_id=uuid.uuid4(),
            trigger_message_id=uuid.uuid4(),
            message="a" * 4000,
            history=[MessageContext(role="user", content="b" * 4000) for _ in range(3)],
            language="zh-CN",
            trace_id="trace-oversized",
        )


def test_prompt_sanitizer_masks_customer_identifiers() -> None:
    """发送给外部模型前应屏蔽邮箱、手机号和长订单标识。"""
    source = "邮箱 buyer@example.com，电话 +86 138-0013-8000，订单 AB123456789。"

    sanitized = sanitize_prompt_text(source)

    assert "buyer@example.com" not in sanitized
    assert "138-0013-8000" not in sanitized
    assert "AB123456789" not in sanitized
    assert "[EMAIL]" in sanitized
    assert "[SENSITIVE_ID]" in sanitized


@pytest.mark.parametrize(
    ("source", "sentinels"),
    [
        (
            "请寄到北京市朝阳区建国路88号A座1201室，邮编100022。",
            ("北京市朝阳区建国路88号A座1201室", "100022"),
        ),
        (
            "Ship to 350 Fifth Avenue, Apt 12B, New York, NY 10118.",
            ("350 Fifth Avenue", "Apt 12B", "10118"),
        ),
        (
            "新地址为广东省深圳市南山区科技园A栋1203室，邮编518000。",
            ("广东省深圳市南山区科技园A栋1203室", "518000"),
        ),
        (
            "Deliver to 10 Downing Street, London SW1A 2AA.",
            ("10 Downing Street", "SW1A 2AA"),
        ),
        (
            "北京市朝阳区建国路甲88号A座1201室",
            ("北京市朝阳区建国路甲88号A座1201室", "甲88号", "A座1201室"),
        ),
        (
            "北京市海淀区东升园公寓12号楼3单元501室",
            ("北京市海淀区东升园公寓12号楼3单元501室", "12号楼", "3单元501室"),
        ),
        (
            "PO Box 123, Seattle, WA 98101",
            ("PO Box 123", "Seattle", "98101"),
        ),
        (
            "Baker Street 221B, London NW1 6XE",
            ("Baker Street 221B", "London", "NW1 6XE"),
        ),
    ],
)
def test_prompt_sanitizer_masks_complete_addresses(source: str, sentinels: tuple[str, ...]) -> None:
    """中英文完整地址及其楼栋、房间和邮编不得进入外部模型上下文。"""
    sanitized = sanitize_prompt_text(source)

    assert "[ADDRESS]" in sanitized
    for sentinel in sentinels:
        assert sentinel not in sanitized


def test_prompt_sanitizer_keeps_non_address_business_text() -> None:
    """地址门禁不能把普通物流描述、FAQ 路线或商品名称误判为客户住址。"""
    source = "物流路线已更新，订单号为 88；Fifth Avenue 系列商品仍可购买。"

    assert sanitize_prompt_text(source) == source


@pytest.mark.parametrize(
    "source",
    [
        "请寄到香港九龙旺角弥敦道555号九龙行12楼",
        "Please send it to One Microsoft Way, Redmond, WA 98052",
        "Please send it to Rural Route 2 Box 152, Springfield, IL 62701",
    ],
)
def test_structured_request_blocks_independent_international_address_variants(source: str) -> None:
    """最终 Provider 边界必须屏蔽香港、英文拼写门牌和乡村路线地址。"""
    request = StructuredRequest(
        system_prompt="只输出 JSON",
        user_prompt=source,
        trace_id="trace-independent-address",
        max_output_tokens=128,
    )

    assert request.user_prompt == "[ADDRESS]"


@pytest.mark.parametrize(
    "source",
    [
        "Calle de Alcalá 42, 28014 Madrid",
        "10 Rue de Rivoli, 75001 Paris",
        "Unter den Linden 77, 10117 Berlin",
        "Flat A, 12/F, Tower 3, Harbour City, Tsim Sha Tsui, Kowloon",
        "東京都新宿区西新宿2丁目8-1",
        "Via Roma 18, 00184 Roma",
    ],
)
def test_structured_request_blocks_unlabeled_multilingual_addresses(source: str) -> None:
    """客户只发送地址正文时，最终 Provider 边界也必须失败关闭。"""
    request = StructuredRequest(
        system_prompt="只输出 JSON",
        user_prompt=source,
        trace_id="trace-unlabeled-address",
        max_output_tokens=128,
    )

    assert request.user_prompt == "[ADDRESS]"


@pytest.mark.parametrize(
    "source",
    [
        "Avenida Paulista, 1578 - Bela Vista, São Paulo - SP, 01310-200",
        "Flat 12B, Lotus Residency, MG Road, Bengaluru 560001",
        "Blk 123, #08-45, Orchard Road, Singapore 238888",
        "Av. Paseo de la Reforma 222, Juárez, 06600 Ciudad de México",
        "서울특별시 강남구 테헤란로 152, 12층",
        "大阪府大阪市北区梅田3-1-1",
        "1600 Amphitheatre Parkway Mountain View CA 94043",
        "221B Baker Street London NW1 6XE",
        "Karl-Marx-Allee 93 10243 Berlin",
        "12 Jalan Ampang, Kuala Lumpur 50450",
    ],
)
def test_provider_boundary_fails_closed_for_phase4_report_005_addresses(source: str) -> None:
    """005 独立样例中的完整地址必须被标记为不可外发。"""
    request = StructuredRequest(
        system_prompt="只输出 JSON",
        user_prompt=source,
        trace_id="00000000-0000-4000-8000-000000000005",
        max_output_tokens=128,
    )

    assert request.prompt_safety_state == PromptSafetyState.BLOCKED
    assert request.user_prompt == "[ADDRESS]"


@pytest.mark.parametrize(
    ("source", "expected_state"),
    [
        ("Avenida Paulista 1578 is the product collection code, not a delivery address.", PromptSafetyState.UNCERTAIN),
        ("Compare build 1578 with release 01310 in the incident report.", PromptSafetyState.UNCERTAIN),
        (
            "Flat 12B and Tower 3 are warehouse shelf labels, not customer addresses.",
            PromptSafetyState.UNCERTAIN,
        ),
        ("The Singapore 238888 campaign code should be escalated to Level 2 support.", PromptSafetyState.UNCERTAIN),
        ("订单12345和工单67890都需要人工复核。", PromptSafetyState.UNCERTAIN),
        ("大阪府活动第3期与版本1-1需要客服确认。", PromptSafetyState.UNCERTAIN),
        ("Please send order 1600 to queue 94043 for manual review.", PromptSafetyState.UNCERTAIN),
        ("Block 123 and unit 08-45 are SKU names in this catalog.", PromptSafetyState.UNCERTAIN),
    ],
)
def test_phase4_report_005_business_text_has_explicit_safety_state(
    source: str,
    expected_state: PromptSafetyState,
) -> None:
    """合法业务正文应保留；存在地点歧义时显式转人工而非静默误脱敏。"""
    decision = evaluate_prompt_safety(source)

    assert decision.state == expected_state
    assert decision.sanitized_text == source
    assert decision.reason_code in {"ADDRESS_CONTEXT_AMBIGUOUS", "UNTRUSTED_FREE_TEXT_REQUIRES_DLP"}


@pytest.mark.parametrize(
    "source",
    [
        "Keizersgracht 123, Amsterdam",
        "Mannerheimintie 10, Helsinki",
        "İstiklal Caddesi 15, İstanbul",
        "Bulevar Kralja Aleksandra 73, Beograd",
        "Rue de Rivoli, Paris",
        "Jalan Tun Razak, Kuala Lumpur",
        "Paseo de Gracia 25, Barcelona",
        "Prinsengracht 263, Amsterdam",
        "Via Garibaldi, Genova",
        "Тверская улица Москва",
        "ถนนสุขุมวิท กรุงเทพมหานคร",
        '{"profile":{"ship_to":"Keizersgracht 123, Amsterdam"}}',
        '{"contact":{"delivery_location":"Rue de Rivoli, Paris"}}',
    ],
)
def test_phase4_report_006_open_address_set_never_defaults_to_allowed(source: str) -> None:
    """开放地址、未知字段别名和未知文字系统都不得以未命中词表为由外发。"""
    assert evaluate_prompt_safety(source).state != PromptSafetyState.ALLOWED


@pytest.mark.parametrize(
    "source",
    [
        "Tower 7 and Suite 2 are inventory labels for the weekly report.",
        "Block 5 and Unit 9 identify fulfillment bins.",
        "Apartment 3 and Building 4 are internal taxonomy labels.",
        "Flat 6 and Tower 8 are routing labels for operations.",
    ],
)
def test_phase4_report_006_internal_labels_are_preserved_for_local_handoff(source: str) -> None:
    """住宅词形与内部标签冲突时保留正文并转人工，不能错误整段脱敏。"""
    decision = evaluate_prompt_safety(source)

    assert decision.state == PromptSafetyState.UNCERTAIN
    assert decision.sanitized_text == source
    assert decision.reason_code == "UNTRUSTED_FREE_TEXT_REQUIRES_DLP"


@pytest.mark.parametrize(
    "source",
    [
        "Revenue, cost, and margin are shown in the report.",
        "Hello, thanks, please escalate this issue.",
        "你好，请帮我查询订单，谢谢。",
        "退款页面、帮助中心、术语表都已更新。",
    ],
)
def test_free_text_without_local_dlp_uses_explicit_fail_closed_reason(source: str) -> None:
    """普通自由文本按数据来源失败关闭，不能再用逗号数量伪装成位置判断。"""
    decision = evaluate_prompt_safety(source)

    assert decision.state == PromptSafetyState.UNCERTAIN
    assert decision.sanitized_text == source
    assert decision.reason_code == "UNTRUSTED_FREE_TEXT_REQUIRES_DLP"


def test_positive_control_payload_is_the_only_local_allowed_protocol() -> None:
    """仅固定控制字段及固定枚举值可由本地正向协议证明不含客户自由文本。"""
    source = '{"operation":"provider_contract_check","schema_version":"1","language":"en"}'

    decision = evaluate_prompt_safety(source)

    assert decision.state == PromptSafetyState.ALLOWED
    assert decision.sanitized_text == source
    assert decision.reason_code == "TRUSTED_CONTROL_PAYLOAD_ALLOWED"


@pytest.mark.parametrize(
    "source",
    [
        '{"operation":"Laugavegur 28, Reykjavik","operation":"provider_contract_check",'
        '"schema_version":"1","language":"en"}',
        '{"operation":"provider_contract_check","schema_version":"Rua Augusta 150, Lisboa",'
        '"schema_version":"1","language":"en"}',
        '{"operation":"provider_contract_check","schema_version":"1","language":"en",'
        '"metadata":{"label":"first","label":"second"}}',
    ],
)
def test_duplicate_json_keys_fail_closed_without_retaining_raw_payload(source: str) -> None:
    """任意层级重复键都属于解析歧义，不能折叠后进入正向协议。"""
    decision = evaluate_prompt_safety(source)

    assert decision.state == PromptSafetyState.UNCERTAIN
    assert decision.sanitized_text == "[UNTRUSTED_JSON]"
    assert decision.reason_code == "JSON_DUPLICATE_KEY_REJECTED"
    assert "Laugavegur" not in decision.sanitized_text
    assert "Rua Augusta" not in decision.sanitized_text


def test_positive_control_payload_is_canonicalized_before_external_use() -> None:
    """合法控制 DTO 必须重新序列化，不能沿用空白、顺序或 Unicode 变形原文。"""
    source = '{  "language" : "en", "schema\u005fversion" : "1", "operation" : "provider\u005fcontract\u005fcheck" }'

    decision = evaluate_prompt_safety(source)

    assert decision.state == PromptSafetyState.ALLOWED
    assert decision.sanitized_text == TRUSTED_PROVIDER_CONTRACT_USER_PROMPT
    assert decision.reason_code == "TRUSTED_CONTROL_PAYLOAD_ALLOWED"


def test_structured_request_evaluates_the_complete_prompt_envelope() -> None:
    """系统 Prompt 与用户 Prompt 都必须通过共同外发门禁。"""
    request = StructuredRequest(
        system_prompt="Ship to 123 Main Street, Seattle, WA 98101 before checking the provider contract.",
        user_prompt=TRUSTED_PROVIDER_CONTRACT_USER_PROMPT,
        trace_id="trace-system-prompt-address",
        max_output_tokens=128,
    )

    assert request.prompt_safety_state == PromptSafetyState.BLOCKED
    assert request.prompt_safety_reason_code == "SYSTEM_PROMPT_SENSITIVE_DATA_DETECTED"
    assert request.system_prompt == "[SYSTEM_PROMPT_BLOCKED]"
    assert "Main Street" not in request.system_prompt


def test_unregistered_system_prompt_defaults_to_uncertain() -> None:
    """未注册系统指令即使未命中地址规则也不能触达外部模型。"""
    request = StructuredRequest(
        system_prompt="classify safely",
        user_prompt=TRUSTED_PROVIDER_CONTRACT_USER_PROMPT,
        trace_id="trace-unregistered-system-prompt",
        max_output_tokens=128,
    )

    assert request.prompt_safety_state == PromptSafetyState.UNCERTAIN
    assert request.prompt_safety_reason_code == "UNTRUSTED_SYSTEM_PROMPT_REQUIRES_REGISTRY"
    assert request.system_prompt == "[SYSTEM_PROMPT_BLOCKED]"


def test_registered_system_prompt_and_control_payload_are_allowed() -> None:
    """仅不可变系统指令与规范控制 DTO 的组合可以通过工程契约检查。"""
    request = StructuredRequest(
        system_prompt=TRUSTED_PROVIDER_CONTRACT_SYSTEM_PROMPT,
        user_prompt=TRUSTED_PROVIDER_CONTRACT_USER_PROMPT,
        trace_id="trace-trusted-provider-contract",
        max_output_tokens=128,
    )

    assert request.prompt_safety_state == PromptSafetyState.ALLOWED
    assert request.prompt_safety_reason_code == "TRUSTED_PROMPT_ENVELOPE_ALLOWED"
    assert request.system_prompt == TRUSTED_PROVIDER_CONTRACT_SYSTEM_PROMPT
    assert request.user_prompt == TRUSTED_PROVIDER_CONTRACT_USER_PROMPT
    assert TRUSTED_PROVIDER_CONTRACT_PROMPT_VERSION == "provider-contract-v1.1.0"
    # DeepSeek 的 JSON Output 契约要求 system 或 user Prompt 显式包含 json。
    # 该条件必须由不可变工程 Prompt 满足，不能让调用方注入动态自由文本补齐。
    assert "json" in request.system_prompt.lower()


def test_unknown_structured_field_defaults_to_uncertain() -> None:
    """未知 JSON 字段即使当前值不像地址，也不能越过任务级字段允许列表。"""
    source = '{"message":"where is my package"}'

    decision = evaluate_prompt_safety(source)

    assert decision.state == PromptSafetyState.UNCERTAIN
    assert decision.sanitized_text == source
    assert decision.reason_code == "UNTRUSTED_STRUCTURED_DATA_REQUIRES_DLP"


@pytest.mark.parametrize(
    "source",
    [
        "Тверская улица, 12, Москва, 125009",
        "شارع الشيخ زايد، مبنى 12، دبي",
        "北京市朝阳区建国路",
        "Main Bazaar, Jaipur, Rajasthan",
        '以下 JSON 是待处理数据：\n{"message":"Тверская улица, 12, Москва, 125009"}',
    ],
)
def test_unrecognized_or_low_confidence_location_text_never_defaults_to_allowed(source: str) -> None:
    """未知文字系统、无门牌地址和结构化嵌套文本必须失败关闭或转人工。"""
    assert evaluate_prompt_safety(source).state != PromptSafetyState.ALLOWED


def test_structured_business_payload_without_local_dlp_remains_uncertain() -> None:
    """JSON 包装不构成隐私证明，客户自由文本仍应失败关闭。"""
    source = '以下 JSON 是待分类数据：\n{"message":"Please send order 1600 to queue 94043 for manual review."}'

    assert evaluate_prompt_safety(source).state == PromptSafetyState.UNCERTAIN


def test_redacted_address_marker_preserves_blocked_state_at_final_boundary() -> None:
    """上游已替换地址时最终边界仍须转人工，不能因原文消失而丢失阻断状态。"""
    request = StructuredRequest(
        system_prompt="只输出 JSON",
        user_prompt='以下 JSON 是待分类数据：\n{"message":"[ADDRESS]"}',
        trace_id="00000000-0000-4000-8000-000000000005",
        max_output_tokens=128,
    )

    assert request.prompt_safety_state == PromptSafetyState.BLOCKED
    assert request.user_prompt == "[ADDRESS]"


@pytest.mark.parametrize(
    "source",
    [
        "上海市第1号消费券怎么领取？",
        "这款公寓模型有1号和2号规格吗？",
        "订单到达北京市中转站12号分拨中心了吗？",
        "Fifth Avenue系列商品多少钱？",
        "请寄到客服中心处理，不需要修改收货地址。",
        "Please send it to customer service for review.",
        "Please send it to Level 2 support for review.",
        "Please send it to order 12345 for manual review.",
        "请将问题发往2号客服队列处理。",
        "请寄到3号售后工单继续处理。",
        "Please escalate version 2.1 to Level 3 support.",
        "第12号商品规格需要人工复核。",
    ],
)
def test_prompt_sanitizer_preserves_address_like_business_messages(source: str) -> None:
    """地址规则不得误删优惠券、商品规格、物流节点和商品系列语义。"""
    assert sanitize_prompt_text(source) == source


def test_structured_request_enforces_address_sanitization_at_provider_boundary() -> None:
    """调用方遗漏脱敏时，统一模型请求对象仍必须在 Provider 前失败关闭。"""
    request = StructuredRequest(
        system_prompt="只输出 JSON",
        user_prompt="客户地址：北京市朝阳区建国路88号A座1201室",
        trace_id="trace-address-boundary",
        max_output_tokens=128,
    )

    assert "北京市朝阳区建国路88号A座1201室" not in request.user_prompt
    assert "[ADDRESS]" in request.user_prompt


@pytest.mark.parametrize(
    "address",
    [
        "北京市朝阳区建国路甲88号A座1201室",
        "北京市海淀区东升园公寓12号楼3单元501室",
        "PO Box 123, Seattle, WA 98101",
        "Baker Street 221B, London NW1 6XE",
    ],
)
def test_structured_request_fails_closed_for_address_shape_variants(address: str) -> None:
    """最终 Provider 请求边界必须覆盖常见地址顺序和组成形式。"""
    request = StructuredRequest(
        system_prompt="只输出 JSON",
        user_prompt=f"客户提供的文本：{address}",
        trace_id="trace-address-variant",
        max_output_tokens=128,
    )

    assert address not in request.user_prompt
    assert "[ADDRESS]" in request.user_prompt


def test_structured_request_fails_closed_for_split_address_json() -> None:
    """绕过工具层直接进入统一请求的拆分地址 JSON 也不得外发。"""
    source = (
        '{"shipping_address":{"district":"Chaoyang","street_name":"Jianguo Road",'
        '"house_number":"88","building":"Tower A","room":"1201"}}'
    )

    request = StructuredRequest(
        system_prompt="只输出 JSON",
        user_prompt=source,
        trace_id="trace-address-json",
        max_output_tokens=128,
    )

    assert request.user_prompt == "[ADDRESS]"


@pytest.mark.parametrize(
    ("output", "expected"),
    [
        (
            IntentModelOutput(
                intent=IntentName.LOGISTICS_QUERY,
                confidence=0.95,
                classification_state=ClassificationState.CLASSIFIED,
            ),
            AgentAction.HUMAN_REVIEW,
        ),
        (
            IntentModelOutput(
                intent=IntentName.LOGISTICS_QUERY,
                confidence=0.59,
                classification_state=ClassificationState.CLASSIFIED,
            ),
            AgentAction.TRANSFER_HUMAN,
        ),
        (
            IntentModelOutput(intent=None, confidence=0.8, classification_state=ClassificationState.MIXED),
            AgentAction.TRANSFER_HUMAN,
        ),
    ],
)
def test_phase1_never_returns_auto_reply(output: IntentModelOutput, expected: AgentAction) -> None:
    """Phase 1 没有 RAG 和回复安全链路，任何分类结果都不得自动发送。"""
    assert decide_phase1_action(output) == expected
