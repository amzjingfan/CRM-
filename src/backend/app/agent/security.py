"""在模型边界执行最小化脱敏，减少客户标识发送到外部供应商。"""

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from enum import StrEnum

from app.agent.prompt_registry import BusinessPromptId, get_business_prompt


class PromptSafetyState(StrEnum):
    """自由文本进入外部模型前的三态安全结论。"""

    ALLOWED = "allowed"
    BLOCKED = "blocked"
    UNCERTAIN = "uncertain"


@dataclass(frozen=True, slots=True)
class PromptSafetyDecision:
    """保存低敏安全结论，不保留或记录客户原文副本。"""

    state: PromptSafetyState
    sanitized_text: str
    reason_code: str


@dataclass(frozen=True, slots=True)
class RealModelEvaluationSafetyContext:
    """独立评测专用的最小授权上下文。

    该对象只由已经校验数据集摘要和清单的评测加载器创建。普通业务请求不会
    获得该上下文，因此生产自由文本仍按原有三态 DLP 规则失败关闭。
    """

    dataset_version: str
    dataset_sha256: str
    manifest_sha256: str
    allowed_payload_hashes: frozenset[str]

    def __post_init__(self) -> None:
        """拒绝空授权和非 SHA-256 摘要，避免畸形上下文扩大允许范围。"""
        digest_pattern = re.compile(r"^[a-f0-9]{64}$")
        if not self.dataset_version or not digest_pattern.fullmatch(self.dataset_sha256):
            raise ValueError("真实模型评测安全上下文无效")
        if not digest_pattern.fullmatch(self.manifest_sha256) or not self.allowed_payload_hashes:
            raise ValueError("真实模型评测清单授权无效")
        if any(not digest_pattern.fullmatch(value) for value in self.allowed_payload_hashes):
            raise ValueError("真实模型评测载荷摘要无效")


PROMPT_DLP_POLICY_VERSION = "prompt-dlp-v1.3.0"
TRUSTED_PROVIDER_CONTRACT_PROMPT_VERSION = "provider-contract-v1.1.0"
TRUSTED_PROVIDER_CONTRACT_SYSTEM_PROMPT = (
    "You are a provider contract checker. Return only a valid json object matching the requested structured output. "
    'Example json format: {"result":"ok"}.'
)
SYNTHETIC_DEMO_PROMPT_VERSION = "synthetic-crm-demo-v1.0.1"
SYNTHETIC_DEMO_SYSTEM_PROMPT = (
    "你是 CRM 智能客服的合成数据演示助手。所有订单、客户和政策均为虚构测试数据。"
    "只能依据输入中的 synthetic_evidence 回答；证据不足或涉及退款到账、赔偿承诺时必须要求人工复核。"
    "请只返回一个有效 json 对象，不要输出 Markdown，也不要增加字段。"
    "json 必须包含以下字段："
    '{"content":"给客服使用的中文回复草稿",'
    '"intent":"logistics_query|return_policy|size_guide|price_inquiry|general",'
    '"confidence":0.0,'
    '"requires_human":false,'
    '"reason_code":"faq_grounded|tool_grounded|insufficient_evidence|high_risk_review"}。'
    "intent 必须与 expected_intent 完全一致。物流工具证据使用 tool_grounded；普通 FAQ 使用 faq_grounded；"
    "证据不足使用 insufficient_evidence；高风险承诺使用 high_risk_review 且 requires_human 必须为 true。"
)
REAL_MODEL_EVALUATION_PROMPT_VERSION = "real-model-eval-v1.2.5"
REAL_MODEL_EVALUATION_REASON_CODES = (
    "grounded_draft",
    "policy_grounded",
    "translation_completed",
    "marketing_review_required",
    "insufficient_evidence",
    "tool_failed",
    "high_risk_review",
)
REAL_MODEL_EVALUATION_SYSTEM_PROMPT = (
    "你是 CRM 智能客服 REAL-AI-05 合成评测节点。输入中的客户、订单、政策和证据全部是冻结的虚构测试数据，"
    "只能依据 synthetic_evidence 回答，不得使用外部事实，不得执行工具或平台动作。"
    "reply 任务生成目标语言的内部回复候选；translation 任务只忠实翻译且固定 human_review；"
    "marketing 任务只生成待人工审核草稿且固定 human_review。"
    "FAQ、否定、条件、引用和营销内容最高 human_review；真实查询证据充分的订单或物流可以 auto_reply；"
    "证据缺失、RAG 无结果、工具失败、敏感复述要求、退款到账、优惠发放或送达承诺必须 transfer_human 且 content=null。"
    "business_claims 必须覆盖正文中的业务命题；没有业务命题时返回空数组。每条声明字段固定为 "
    "subject_type、subject_id、action、tense、polarity、condition、evidence_type、evidence_id、confidence。"
    "本评测常用 subject_type 仅为 refund_policy、order、logistics、non_business_artifact；"
    "对应 action 仅为 explain_policy、report_status、display；tense 使用 present 或 timeless；"
    "polarity 使用 affirmed、negated 或 uncertain；condition 使用 actual、conditional、quoted 或 example；"
    "evidence_type 必须与输入一致，faq_chunk/tool_call 必须逐字复制 evidence_id，其他类型 evidence_id=null。"
    "reason_code 只能逐字使用 grounded_draft、policy_grounded、translation_completed、"
    "marketing_review_required、insufficient_evidence、tool_failed、high_risk_review 之一，禁止创造近义原因码。"
    "决策映射固定为：tool_failed 依赖使用 transfer_human+tool_failed；rag_miss 或退款/优惠缺少证据使用 "
    "transfer_human+insufficient_evidence；敏感信息复述和无依据送达承诺使用 transfer_human+high_risk_review；"
    "translation 使用 human_review+translation_completed；marketing 使用 human_review+marketing_review_required；"
    "FAQ 政策说明使用 human_review+policy_grounded；订单或物流 tool_call 证据充分时使用 "
    "auto_reply+grounded_draft。transfer_human 的 content 必须为 null，其他决策的 content 必须是非空字符串。"
    "否定说明或引用的禁止反例不是客户实例事实：只要 faq_chunk 证据与输入一致，必须使用 "
    "human_review+policy_grounded，不能因出现退款、到账或保证等被引用词而转人工。否定说明和引用反例的声明 "
    "subject_type 使用 non_business_artifact、action 使用 display、tense 使用 timeless；引用反例的 condition "
    "使用 quoted 且 polarity 使用 negated，否定说明使用 condition=actual、polarity=negated。"
    "当前售后政策和多语言政策的批准都取决于审核，均使用 "
    "refund_policy+explain_policy+timeless+affirmed+conditional；"
    "售后政策说明即使交给人工复核，也必须输出一条有证据的 refund_policy 结构化声明；"
    "证据不足时改为 transfer_human 且 business_claims 为空数组。"
    "条件政策使用 refund_policy+explain_policy+timeless+affirmed+conditional。"
    "禁止用语即使出现在引用反例中，也不要在 content 中逐字复述；应概述其风险，不能写出确定性承诺。"
    "否定说明必须区分页面展示与真实结果：页面未显示不能推断退款完成或失败；只描述已有证据所显示的事实。"
    "条件政策只描述审核规则：平台批准是处理的前置条件，不声称具体申请已经获批；不得承诺退款结果。"
    "英文条件说明使用 only if the platform approves 表达前置条件，不使用表示已经获批的完成式，即使是否定句。"
    "英语否定状态标签只解释标签含义，使用一般现在时正向句式 The status is unconfirmed 或 "
    "The status is not confirmed 明确状态未确认；不得从标签推断退款成功、失败或实际处理进度。"
    "英语条件政策只解释通用规则，使用一般现在时正向句式 Processing begins only if the platform "
    "approves a request，并依据证据调整动作与主体；不得追加具体申请的审批现状或完成时个案说明。"
    "非订单主体的 subject_id 必须为 null；所有业务声明 confidence 必须不低于 0.5。"
    "无证据的退款、补偿款及其同义表达统一使用 insufficient_evidence，不使用 high_risk_review。"
    "transfer_human 时 business_claims 必须为空数组；订单或物流 tool_call 只输出一个与 subject_ref 匹配的声明。"
    "翻译必须忠实保留状态和否定，不增加业务事实；处理中统一使用 being processed，准备中使用 "
    "in preparation 或 being prepared，尚未发货使用 has not shipped。"
    "任何结果 send_performed 必须为 false。只返回一个有效 JSON 对象，字段固定为 decision、content、language、"
    "reason_code、business_claims、send_performed，不得输出 Markdown 或增加字段。"
    "无声明示例："
    '{"decision":"human_review","content":"内部草稿","language":"zh-CN",'
    '"reason_code":"policy_grounded","business_claims":[],"send_performed":false}。'
    "声明示例："
    '{"subject_type":"order","subject_id":"[SYNTHETIC_ORDER]","action":"report_status",'
    '"tense":"present","polarity":"affirmed","condition":"actual","evidence_type":"tool_call",'
    '"evidence_id":"10000000-0000-4000-8000-000000000001","confidence":0.9}。'
)
# 每个摘要对应 ``src/tests/ai/datasets/real-model-v1.0.0.jsonl`` 中一个规范化外发载荷。
# 只登记摘要而不在安全模块复制正文；数据集任意字符变化都会回到默认失败关闭。
TRUSTED_REAL_MODEL_EVALUATION_PAYLOAD_HASHES = frozenset(
    {
        "f932f3297e0fa8c6a9cfb8e22dad3817712b7c07edbeb60856d1d470ccde33f6",
        "a1e6b45a7bfce383aedb4f4d41b6c9195406100ea96b85f4392f17b7915daad6",
        "76de428074530f213e2d51f133e4e1d80170b98d51ee7f8578053a48ffc3a950",
        "c5f868ebd18efc6c6ae4920b2b89869e650df1b91bafad21690649a68aa29050",
        "2172a91b59b558ff0a258a15c965e76dbc7a1add09218147d072abb96895dc32",
        "7aaa439d5b38dc9c143836090d165fed1e1bf23afe2e5aab5cae37abbaa5985b",
        "71d398264526d73e86419078f83fedc74ae790b144303260afe953e9c15a974b",
        "42539399a837578c9a49e5374173a566c274869e3259eef33a062ba040cdc280",
        "9b91a50b68a9f48974eb1aae8648f9ae7d3ffd0aef9c3c39696f8c8b064cfb62",
        "61754d0f0f25ac835ed4b1506c9284c686147ba8eb92f6ba96d55ef878ecb247",
        "5b5ef7dc246643c586c74e493e3f776a686e246b59cc3d1124fd036ffef4ce4d",
        "2131cc0bdae8996134052e5dd7f01bc237184e944797386f2bf1944bcb3c4803",
        "070c6b5092c0f5b23b29340edcc17b02095702ee5fa9fbc50f0d7ddbca2221af",
        "5b7a7efec571c43f6a8b08c8aa5bf8160e45a82a90c9100249f20cffbfbe9bab",
        "ba1aea657d4e7456963d30aeed4a6e0c5699612b09fa728c13862b1b67b9400d",
        "e56374209e2bfd5b1c0e4449b90d6141b622bcae7b7c9d09442b910bca96ef58",
        "b15ff7531688969c9843334eae6d32d5963885cc6e310e37e0683f977bacb77b",
        "b4e29e5a026060c46c115dc8401afd63651f30f84fec1d94a77d3e0d0cdb4de2",
    }
)
REAL_MODEL_EVALUATION_PAYLOAD_KEYS = frozenset(
    {
        "operation",
        "schema_version",
        "dataset_version",
        "sample_id",
        "task",
        "input_language",
        "target_language",
        "customer_message",
        "synthetic_evidence",
        "evidence_type",
        "evidence_id",
        "subject_ref",
        "dependency_state",
    }
)
SYNTHETIC_SUBJECT_PATTERN = re.compile(r"^\[SYNTHETIC_[A-Z_]{2,40}\]$")
EVALUATION_SECRET_PATTERN = re.compile(
    r"(?:\bBearer\s+[A-Za-z0-9._~+/=-]{8,}|\b(?:api[_ -]?key|access[_ -]?token|refresh[_ -]?token)\b\s*[:=])",
    re.IGNORECASE,
)
# 演示场景全部由服务端固定，浏览器只能通过已经落库的场景 ID 选择。
# 这里保存完整允许值，确保任何新增字段、篡改文本或真实客户内容都会回到默认失败关闭逻辑。
SYNTHETIC_DEMO_SCENARIOS: dict[str, dict[str, str]] = {
    "logistics": {
        "customer_message": "我的演示订单 DEMO-1001 现在到哪里了？",
        "synthetic_evidence": "演示物流工具结果：订单 DEMO-1001 已发货，当前位于广州转运中心，预计两天内送达。",
        "expected_intent": "logistics_query",
    },
    "return-policy": {
        "customer_message": "演示商品不合适，应该怎样申请退货？",
        "synthetic_evidence": "演示退货政策：签收后七天内可申请退货；商品需保持未使用状态，质量问题由商家承担运费。",
        "expected_intent": "return_policy",
    },
    "size-guide": {
        "customer_message": "演示款运动上衣的 M 码适合什么身材？",
        "synthetic_evidence": "演示尺码 FAQ：M 码建议胸围 92 至 98 厘米；介于两个尺码之间时建议选择较大尺码。",
        "expected_intent": "size_guide",
    },
    "price": {
        "customer_message": "演示款运动上衣现在多少钱？",
        "synthetic_evidence": "演示价格 FAQ：运动上衣标价 49.90 美元；实际结算价格以演示页面为准。",
        "expected_intent": "price_inquiry",
    },
    "general": {
        "customer_message": "你们演示客服的服务时间是什么时候？",
        "synthetic_evidence": "演示服务 FAQ：人工客服服务时间为北京时间每天 09:00 至 18:00。",
        "expected_intent": "general",
    },
    "high-risk": {
        "customer_message": "你能保证演示退款明天到账并赔偿 100 元吗？",
        "synthetic_evidence": "演示安全规则：没有退款工具结果，不得承诺到账时间、退款完成或赔偿金额，应建议人工复核。",
        "expected_intent": "return_policy",
    },
}
SYSTEM_PROMPT_BLOCKED_MARKER = "[SYSTEM_PROMPT_BLOCKED]"
UNTRUSTED_JSON_MARKER = "[UNTRUSTED_JSON]"
ADDRESS_REDACTION_MARKER_PATTERN = re.compile(r"\[ADDRESS\]")
EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_PATTERN = re.compile(r"(?<!\w)(?:\+?\d[\d\s-]{7,}\d)(?!\w)")
ALPHANUMERIC_ID_PATTERN = re.compile(r"\b(?=[A-Z0-9-]{8,}\b)(?=[A-Z0-9-]*\d)[A-Z0-9-]+\b", re.IGNORECASE)
LABELED_ADDRESS_PATTERN = re.compile(
    r"(?i)(?:(?:shipping\s+address|delivery\s+address|mailing\s+address|address|"
    r"收货地址|配送地址|送货地址|邮寄地址|新地址|地址)\s*(?:[:：=]|是|为)\s*|"
    r"(?:请)?(?:寄到|寄往|送到|配送到|发往)\s*"
    r"(?=[^,，;；\r\n]{0,80}(?:(?:大道|公路|路|街|道|巷|弄|胡同|号楼|栋|单元|室)|"
    r"PO\s+BOX|RURAL\s+ROUTE))|"
    r"(?:ship|deliver|send)(?:\s+(?:it|this|the\s+(?:order|package|parcel)))?\s+to\s+"
    r"(?=[^,，;；\r\n]{0,80}(?:PO\s+BOX|RURAL\s+ROUTE|\b(?:STREET|ST\.?|ROAD|RD\.?|"
    r"AVENUE|AVE\.?|LANE|LN\.?|DRIVE|DR\.?|BOULEVARD|BLVD\.?|COURT|CT\.?|WAY|"
    r"PARKWAY|PKWY\.?|HIGHWAY|HWY\.?)\b)))[^,，;；\r\n]{4,160}"
)
CHINESE_ADDRESS_PATTERN = re.compile(
    r"(?:(?:中国)?(?:[\u4e00-\u9fff]{2,8}(?:省|自治区|特别行政区))?)"
    r"(?:[\u4e00-\u9fff]{2,8}(?:市|自治州|州|盟))?"
    r"(?:[\u4e00-\u9fff]{1,12}(?:区|县|旗|镇|乡|街道))?"
    r"[\u4e00-\u9fffA-Za-z0-9]{1,30}(?:大道|公路|路|街|道|巷|弄|胡同)"
    r"\s*[甲乙丙丁戊己庚辛壬癸A-Za-z]?\d{1,6}(?:号|號)[\u4e00-\u9fffA-Za-z0-9#-]{0,30}"
)
ENGLISH_ADDRESS_PATTERN = re.compile(
    r"(?i)\b\d{1,6}[A-Z]?(?:\s+|,\s*)"
    r"(?:[A-Z0-9][A-Z0-9.'-]*\s+){0,8}"
    r"(?:street|st\.?|road|rd\.?|avenue|ave\.?|lane|ln\.?|drive|dr\.?|boulevard|blvd\.?|"
    r"court|ct\.?|way|parkway|pkwy\.?|highway|hwy\.?)\b"
    r"(?:\s*,?\s*(?:apt|apartment|suite|unit|#)\s*[A-Z0-9-]+)?"
    r"(?:\s*,\s*[A-Z][A-Z .'-]{1,30})?"
    r"(?:\s*,\s*[A-Z]{2})?"
    r"(?:\s+\d{5}(?:-\d{4})?)?"
)
PO_BOX_ADDRESS_PATTERN = re.compile(r"(?i)\b(?:P(?:OST)?\.?\s*O(?:FFICE)?\.?\s*BOX|PO\s+BOX)\s+[A-Z0-9-]+")
ENGLISH_STREET_FIRST_ADDRESS_PATTERN = re.compile(
    r"(?i)\b(?:[A-Z0-9][A-Z0-9.'-]*\s+){1,8}"
    r"(?:street|st\.?|road|rd\.?|avenue|ave\.?|lane|ln\.?|drive|dr\.?|boulevard|blvd\.?|"
    r"court|ct\.?|way|parkway|pkwy\.?|highway|hwy\.?)\s+\d{1,6}[A-Z]?\b"
)
CHINESE_RESIDENTIAL_ADDRESS_PATTERN = re.compile(
    r"[\u4e00-\u9fffA-Za-z0-9]{0,50}(?:社区|小区|公寓|村|花园|大厦|广场|园区)"
    r"[^,，;；\r\n]{0,30}?[甲乙丙丁戊己庚辛壬癸A-Za-z]?\d{1,6}"
    r"(?:号楼|號樓|栋|棟|座|单元|單元|室|楼|樓|层|層|"
    r"(?:号|號)[^,，;；\r\n]{0,20}(?:楼|樓|栋|棟|单元|單元|室))"
    r"[^,，;；\r\n]{0,40}"
)
RURAL_ROUTE_ADDRESS_PATTERN = re.compile(
    r"(?i)\b(?:rural\s+route|rr)\s+\d{1,4}\s+(?:box\s+)?[A-Z0-9-]+"
    r"(?:\s*,\s*[A-Z][A-Z .'-]{1,30})?(?:\s*,\s*[A-Z]{2})?(?:\s+\d{5}(?:-\d{4})?)?"
)
ENGLISH_SPELLED_NUMBER_ADDRESS_PATTERN = re.compile(
    r"(?i)\b(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|"
    r"fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|"
    r"ninety|hundred)\s+(?:[A-Z0-9][A-Z0-9.'-]*\s+){1,8}"
    r"(?:street|st\.?|road|rd\.?|avenue|ave\.?|lane|ln\.?|drive|dr\.?|boulevard|blvd\.?|"
    r"court|ct\.?|way|parkway|pkwy\.?|highway|hwy\.?)\b"
    r"(?:\s*,\s*[A-Z][A-Z .'-]{1,30})?(?:\s*,\s*[A-Z]{2})?(?:\s+\d{5}(?:-\d{4})?)?"
)
# 裸地址没有“address/地址”标签时，不按城市或街道名称枚举，而要求多个独立组成证据。
# 第一类是“第一段存在门牌数字 + 逗号后存在 4～6 位邮编和地点名称”；这可覆盖常见欧洲
# 地址顺序，同时不会把单个订单号、客服层级或版本号当成地址。
BARE_POSTAL_ADDRESS_PATTERN = re.compile(
    r"(?i)^(?=.{8,180}$)(?=[^,\r\n]{1,100}\d{1,6}[A-Z]?[^,\r\n]*,)"
    r"[^,\r\n]{2,100},\s*[A-Z0-9 -]{0,12}\b\d{4,6}\b\s+[^\W\d_][^,\r\n]{1,40}$"
)
# 第二类要求住宅单元、楼层/楼座和数字同时出现。单独的 “Level 2 support” 或商品规格
# 不具备这些相互独立的地址组成，因此不会触发整段失败关闭。
BARE_BUILDING_ADDRESS_PATTERN = re.compile(
    r"(?i)^(?=.{8,180}$)(?=.*\b(?:flat|apartment|apt\.?|unit|suite)\b)"
    r"(?=.*\b(?:tower|building|block)\b)(?=.*\d)[^;；\r\n]+$"
)
# 日本地址通常同时包含都道府县/行政区、丁目和连续门牌。要求完整组成链，避免仅凭日文数字误判。
JAPANESE_ADDRESS_PATTERN = re.compile(
    r"^(?=.{8,160}$)[^\r\n]{0,30}(?:都|道|府|県)[^\r\n]{0,40}(?:市|区|郡)"
    r"[^\r\n]{0,40}\d{1,4}丁目\d{1,4}(?:-\d{1,4}){1,2}[^\r\n]{0,30}$"
)
# 地址是开放集合，不能把已知格式正则当作“安全允许证明”。下面的信号只用于
# 识别地址风险或不确定性：生产外发仍由三态结果失败关闭，而不是因为未命中某条
# 国家格式正则就默认安全。词表只保存公共地址类别词，不包含客户数据或真实地址。
MULTILINGUAL_LOCATION_TERM_PATTERN = re.compile(
    r"(?i)(?:\b(?:avenida|av\.?|calle|rue|via|jalan|allee|strasse|straße|road|rd\.?|street|st\.?|"
    r"avenue|ave\.?|parkway|pkwy\.?|flat|apartment|apt\.?|unit|suite|tower|block|blk|"
    r"residency|building|floor)\b|(?:路|街|道|巷|弄|号|號|栋|棟|单元|單元|室|层|層)|"
    r"(?:특별시|광역시|도|시|군|구|로|길|층)|(?:都|道|府|県|市|区|町|村|丁目))"
)
ADDRESS_SEPARATOR_PATTERN = re.compile(r"[,，،#]|\s-\s")
ADDRESS_NUMBER_PATTERN = re.compile(r"(?<!\w)\d{1,6}[A-Z]?(?!\w)|(?<=\D)\d{1,4}(?:-\d{1,4})+")
POSTAL_SHAPE_PATTERN = re.compile(r"(?i)(?:\b\d{5,6}(?:-\d{3,4})?\b|\b[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}\b)")
HYPHENATED_LOCATION_NUMBER_PATTERN = re.compile(r"\d{1,4}(?:-\d{1,4}){2,}")
BUSINESS_NON_ADDRESS_CONTEXT_PATTERN = re.compile(
    r"(?i)(?:warehouse|shelf|sku|catalog|product|collection\s+code|campaign\s+code|"
    r"incident\s+report|release|version|queue|support|manual\s+review|not\s+(?:a\s+)?(?:delivery\s+)?address|"
    r"仓库|货架|库位|商品|规格|型号|活动|版本|队列|客服|工单|人工复核|不是(?:客户)?地址|不(?:是|需要)修改收货地址)"
)
UNSUPPORTED_SCRIPT_PATTERN = re.compile(r"[\u0600-\u06ff\u0750-\u077f\u0900-\u097f\u0e00-\u0e7f]")
POSTAL_CODE_PATTERN = re.compile(
    r"(?i)(?:(?:邮(?:政)?编码|邮编|zip(?:\s*code)?|postal(?:\s*code)?)\s*[:：=]?\s*[A-Z0-9][A-Z0-9 -]{2,11}"
    r"|\b[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}\b)"
)
ADDRESS_FIELD_NAMES = frozenset(
    {
        "address",
        "shippingaddress",
        "deliveryaddress",
        "mailingaddress",
        "street",
        "addressline1",
        "addressline2",
        "city",
        "province",
        "state",
        "zipcode",
        "postalcode",
        "postcode",
        "country",
        "收货地址",
        "配送地址",
        "送货地址",
        "邮寄地址",
        "地址",
    }
)
HIGH_RISK_ADDRESS_PATTERNS = (
    LABELED_ADDRESS_PATTERN,
    CHINESE_RESIDENTIAL_ADDRESS_PATTERN,
    ENGLISH_ADDRESS_PATTERN,
    ENGLISH_STREET_FIRST_ADDRESS_PATTERN,
    PO_BOX_ADDRESS_PATTERN,
    RURAL_ROUTE_ADDRESS_PATTERN,
    ENGLISH_SPELLED_NUMBER_ADDRESS_PATTERN,
    BARE_POSTAL_ADDRESS_PATTERN,
    BARE_BUILDING_ADDRESS_PATTERN,
    JAPANESE_ADDRESS_PATTERN,
)
STRUCTURED_ADDRESS_CONTAINER_PATTERN = re.compile(r"(?i)[\"']?(?:shipping|delivery|mailing)[_\s-]*address[\"']?\s*[:=]")
STRUCTURED_ADDRESS_COMPONENT_PATTERN = re.compile(
    r"(?i)[\"']?(?:district|street[_-]?name|house[_-]?number|building|room|postal[_-]?code|postcode)"
    r"[\"']?\s*[:=]"
)

# 该正向协议只用于验证 Provider 工程契约，不承载客户、订单、知识或营销正文。
# 业务请求中出现任意其他字段都意味着存在自由文本或未来未知数据，必须进入本地
# DLP/人工接管，而不能因为地址黑名单暂时未命中就默认允许出境。
TRUSTED_CONTROL_PAYLOAD_KEYS = frozenset({"operation", "schema_version", "language"})
TRUSTED_CONTROL_OPERATIONS = frozenset({"provider_contract_check"})
TRUSTED_CONTROL_LANGUAGES = frozenset({"en", "zh-CN"})
TRUSTED_SYNTHETIC_DEMO_PAYLOAD_KEYS = frozenset(
    {"operation", "schema_version", "scenario_id", "customer_message", "synthetic_evidence"}
)
DUPLICATE_JSON_PAYLOAD = object()


class DuplicateJsonKeyError(ValueError):
    """表示输入 JSON 在任意对象层级包含重复键。"""


def is_sensitive_address_field(field_name: object) -> bool:
    """判断结构化模型上下文中的字段是否属于完整地址组成部分。"""
    normalized = re.sub(r"[^a-z0-9\u4e00-\u9fff]", "", str(field_name).lower())
    return normalized in ADDRESS_FIELD_NAMES


def _contains_high_risk_address(text: str) -> bool:
    """识别应整段失败关闭的自由文本或结构化地址上下文。"""
    if any(pattern.search(text) for pattern in HIGH_RISK_ADDRESS_PATTERNS):
        return True
    if STRUCTURED_ADDRESS_CONTAINER_PATTERN.search(text):
        return True
    # 两个及以上地址组成字段已经足以在模型端拼接客户位置，不能继续逐值猜测。
    return len(STRUCTURED_ADDRESS_COMPONENT_PATTERN.findall(text)) >= 2


def _contains_open_address_signature(text: str) -> bool:
    """按组成证据识别完整地址，不把具体国家格式作为允许列表。

    地址至少同时具备地点类别和定位数字；出现第二组数字、邮编形态或地址分隔符时，
    已足以让外部模型重新定位客户，应整段阻断。未知文字系统则进入不确定状态，
    由调用链转人工，不能因本地规则不认识该语言而默认外发。
    """
    location_term_count = len(MULTILINGUAL_LOCATION_TERM_PATTERN.findall(text))
    if location_term_count == 0:
        return False
    if location_term_count >= 3 and not BUSINESS_NON_ADDRESS_CONTEXT_PATTERN.search(text):
        return True
    number_count = len(ADDRESS_NUMBER_PATTERN.findall(text))
    return (
        HYPHENATED_LOCATION_NUMBER_PATTERN.search(text) is not None
        or number_count >= 2
        or (
            number_count >= 1
            and (POSTAL_SHAPE_PATTERN.search(text) is not None or ADDRESS_SEPARATOR_PATTERN.search(text) is not None)
        )
    )


def _contains_ambiguous_address_context(text: str) -> bool:
    """识别住宅词与仓位、SKU、版本等业务语义冲突的文本。"""
    return bool(
        BUSINESS_NON_ADDRESS_CONTEXT_PATTERN.search(text)
        and (MULTILINGUAL_LOCATION_TERM_PATTERN.search(text) or _contains_high_risk_address(text))
        and ADDRESS_NUMBER_PATTERN.search(text)
    )


def _contains_unknown_script_letters(text: str) -> bool:
    """判断文本是否超出当前本地策略明确支持的中英日韩文字集合。"""
    supported_name_prefixes = ("LATIN", "CJK", "HIRAGANA", "KATAKANA", "HANGUL")
    return any(
        character.isalpha() and not unicodedata.name(character, "UNKNOWN").startswith(supported_name_prefixes)
        for character in text
    )


def _contains_low_confidence_location_shape(text: str) -> bool:
    """识别无法可靠证明为安全业务文本的开放地址形态。"""
    if BUSINESS_NON_ADDRESS_CONTEXT_PATTERN.search(text):
        return False
    separator_count = len(ADDRESS_SEPARATOR_PATTERN.findall(text))
    number_count = len(ADDRESS_NUMBER_PATTERN.findall(text))
    location_term_count = len(MULTILINGUAL_LOCATION_TERM_PATTERN.findall(text))
    alphabetic_count = sum(character.isalpha() for character in text)
    if location_term_count >= 2:
        return True
    if _contains_unknown_script_letters(text) and (number_count >= 1 or separator_count >= 1):
        return True
    if separator_count >= 2 and alphabetic_count >= 8:
        return True
    return number_count >= 2 and separator_count >= 1 and alphabetic_count >= 5


def _reject_duplicate_json_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """在 JSON 解码阶段拒绝重复键，避免后值覆盖隐藏原始敏感数据。"""
    payload: dict[str, object] = {}
    for key, value in pairs:
        if key in payload:
            raise DuplicateJsonKeyError(key)
        payload[key] = value
    return payload


def _extract_json_payload(text: str) -> object | None:
    """提取 Prompt 尾部 JSON，并显式标记任意层级的重复键。"""
    json_start = text.find("{")
    if json_start < 0:
        return None
    try:
        parsed_payload: object = json.loads(text[json_start:], object_pairs_hook=_reject_duplicate_json_keys)
        return parsed_payload
    except DuplicateJsonKeyError:
        return DUPLICATE_JSON_PAYLOAD
    except (json.JSONDecodeError, TypeError, ValueError):
        return None


def _is_trusted_control_payload(text: str, payload: object) -> bool:
    """验证不含客户自由文本的最小 Provider 控制协议。

    只有纯 JSON、固定字段和固定枚举值同时满足时才能成为 ``allowed``。
    前缀、嵌套对象、未知字段或自由文本值均失败关闭，避免调用方把任意客户数据
    伪装成“已结构化”后绕过最终 Provider 边界。
    """
    if not text.lstrip().startswith("{") or not isinstance(payload, dict):
        return False
    if set(payload) != TRUSTED_CONTROL_PAYLOAD_KEYS:
        return False
    return (
        payload.get("operation") in TRUSTED_CONTROL_OPERATIONS
        and payload.get("schema_version") == "1"
        and payload.get("language") in TRUSTED_CONTROL_LANGUAGES
    )


def _canonicalize_trusted_control_payload(payload: dict[str, object]) -> str:
    """只从已验证字段重建控制 DTO，确保原始变形和隐藏值不会继续外发。"""
    canonical_payload = {
        "operation": str(payload["operation"]),
        "schema_version": str(payload["schema_version"]),
        "language": str(payload["language"]),
    }
    return json.dumps(canonical_payload, ensure_ascii=True, separators=(",", ":"))


def build_synthetic_demo_payload(scenario_id: str) -> str:
    """从固定合成场景生成可外发的规范 JSON，不接受浏览器提供正文。"""
    scenario = SYNTHETIC_DEMO_SCENARIOS.get(scenario_id)
    if scenario is None:
        raise ValueError("未知的 AI 合成演示场景")
    payload = {
        "operation": "synthetic_crm_suggestion",
        "schema_version": "1",
        "scenario_id": scenario_id,
        "customer_message": scenario["customer_message"],
        "synthetic_evidence": scenario["synthetic_evidence"],
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _is_trusted_synthetic_demo_payload(payload: object) -> bool:
    """仅允许与服务端固定场景逐字段一致的合成数据进入外部模型。"""
    if not isinstance(payload, dict) or set(payload) != TRUSTED_SYNTHETIC_DEMO_PAYLOAD_KEYS:
        return False
    scenario_id = payload.get("scenario_id")
    if not isinstance(scenario_id, str):
        return False
    scenario = SYNTHETIC_DEMO_SCENARIOS.get(scenario_id)
    return bool(
        scenario
        and payload.get("operation") == "synthetic_crm_suggestion"
        and payload.get("schema_version") == "1"
        and payload.get("customer_message") == scenario["customer_message"]
        and payload.get("synthetic_evidence") == scenario["synthetic_evidence"]
    )


def _is_trusted_real_model_evaluation_payload(text: str, payload: object) -> bool:
    """仅允许冻结 REAL-AI-05 合成数据集中的逐字规范载荷外发。"""
    if not text.lstrip().startswith("{") or not isinstance(payload, dict):
        return False
    if payload.get("operation") != "real_model_evaluation" or payload.get("schema_version") != "1":
        return False
    return hashlib.sha256(text.encode("utf-8")).hexdigest() in TRUSTED_REAL_MODEL_EVALUATION_PAYLOAD_HASHES


def _evaluate_authorized_real_model_payload(
    text: str,
    payload: object,
    context: RealModelEvaluationSafetyContext,
) -> PromptSafetyDecision:
    """校验独立评测清单授权，并对合成正文再次执行本地 PII/DLP 检查。"""
    payload_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if payload_hash not in context.allowed_payload_hashes:
        return PromptSafetyDecision(
            state=PromptSafetyState.UNCERTAIN,
            sanitized_text=UNTRUSTED_JSON_MARKER,
            reason_code="EVALUATION_PAYLOAD_HASH_NOT_IN_MANIFEST",
        )
    if not isinstance(payload, dict) or set(payload) != REAL_MODEL_EVALUATION_PAYLOAD_KEYS:
        return PromptSafetyDecision(
            state=PromptSafetyState.UNCERTAIN,
            sanitized_text=UNTRUSTED_JSON_MARKER,
            reason_code="EVALUATION_PAYLOAD_SCHEMA_INVALID",
        )
    if (
        payload.get("operation") != "real_model_evaluation"
        or payload.get("schema_version") != "1"
        or payload.get("dataset_version") != context.dataset_version
    ):
        return PromptSafetyDecision(
            state=PromptSafetyState.UNCERTAIN,
            sanitized_text=UNTRUSTED_JSON_MARKER,
            reason_code="EVALUATION_PAYLOAD_CONTEXT_MISMATCH",
        )
    subject_ref = payload.get("subject_ref")
    if subject_ref is not None and (
        not isinstance(subject_ref, str) or SYNTHETIC_SUBJECT_PATTERN.fullmatch(subject_ref) is None
    ):
        return PromptSafetyDecision(
            state=PromptSafetyState.UNCERTAIN,
            sanitized_text=UNTRUSTED_JSON_MARKER,
            reason_code="EVALUATION_SUBJECT_NOT_SYNTHETIC",
        )
    for field_name in ("customer_message", "synthetic_evidence"):
        value = payload.get(field_name)
        if value is None:
            continue
        if not isinstance(value, str):
            return PromptSafetyDecision(
                state=PromptSafetyState.UNCERTAIN,
                sanitized_text=UNTRUSTED_JSON_MARKER,
                reason_code="EVALUATION_PAYLOAD_SCHEMA_INVALID",
            )
        # 安全测试允许字面占位符；先移除占位符再检测，避免把已脱敏标记
        # 误当成真实地址，同时仍拒绝实际邮箱、电话、地址、Token 和长标识。
        scan_value = ADDRESS_REDACTION_MARKER_PATTERN.sub("", value)
        scan_value = scan_value.replace("[EMAIL]", "").replace("[PHONE]", "")
        if (
            EMAIL_PATTERN.search(scan_value)
            or PHONE_PATTERN.search(scan_value)
            or ALPHANUMERIC_ID_PATTERN.search(scan_value)
            or EVALUATION_SECRET_PATTERN.search(scan_value)
        ):
            return PromptSafetyDecision(
                state=PromptSafetyState.BLOCKED,
                sanitized_text=UNTRUSTED_JSON_MARKER,
                reason_code="EVALUATION_PAYLOAD_PII_DETECTED",
            )
        location_risk = _structured_location_risk(scan_value)
        if location_risk is not None:
            state, reason_code = location_risk
            return PromptSafetyDecision(
                state=state,
                sanitized_text=UNTRUSTED_JSON_MARKER,
                reason_code=f"EVALUATION_{reason_code}",
            )
    return PromptSafetyDecision(
        state=PromptSafetyState.ALLOWED,
        sanitized_text=text,
        reason_code="VERIFIED_REAL_MODEL_EVALUATION_PAYLOAD_ALLOWED",
    )


def _is_unlabeled_building_reference(text: str) -> bool:
    """识别无法区分住宅地址与内部标签的无分隔符楼座组合。"""
    return BARE_BUILDING_ADDRESS_PATTERN.search(text) is not None and ADDRESS_SEPARATOR_PATTERN.search(text) is None


def _structured_location_risk(value: object) -> tuple[PromptSafetyState, str] | None:
    """递归检查结构化允许列表中的字符串值和地址字段名。"""
    if isinstance(value, dict):
        pending_uncertain: tuple[PromptSafetyState, str] | None = None
        for key, item in value.items():
            if is_sensitive_address_field(key):
                return PromptSafetyState.BLOCKED, "STRUCTURED_ADDRESS_FIELD_BLOCKED"
            child_risk = _structured_location_risk(item)
            if child_risk is not None and child_risk[0] == PromptSafetyState.BLOCKED:
                return child_risk
            if child_risk is not None:
                pending_uncertain = child_risk
        return pending_uncertain
    if isinstance(value, list):
        pending_uncertain = None
        for item in value:
            child_risk = _structured_location_risk(item)
            if child_risk is not None and child_risk[0] == PromptSafetyState.BLOCKED:
                return child_risk
            if child_risk is not None:
                pending_uncertain = child_risk
        return pending_uncertain
    if not isinstance(value, str):
        return None
    if _contains_ambiguous_address_context(value):
        return PromptSafetyState.UNCERTAIN, "ADDRESS_CONTEXT_AMBIGUOUS"
    if _contains_high_risk_address(value) or _contains_open_address_signature(value):
        return PromptSafetyState.BLOCKED, "COMPLETE_ADDRESS_DETECTED"
    if _contains_low_confidence_location_shape(value):
        return PromptSafetyState.UNCERTAIN, "LOCATION_TEXT_LOW_CONFIDENCE"
    return None


def _redact_non_address_identifiers(text: str) -> str:
    """即使地址判断不确定，也必须先移除确定可识别的邮箱、电话和长标识。"""
    sanitized = EMAIL_PATTERN.sub("[EMAIL]", text)
    sanitized = PHONE_PATTERN.sub("[SENSITIVE_ID]", sanitized)
    return ALPHANUMERIC_ID_PATTERN.sub("[SENSITIVE_ID]", sanitized)


def _business_payload_contains_unapproved_identifier(value: object, field_name: str | None = None) -> bool:
    """识别业务 JSON 中未位于技术引用字段的原始长标识。

    FAQ chunk、工具调用和声明证据使用的 UUID 是内部关联键，可在指定字段中
    保留；客户消息、知识正文、候选文案和其他字段中的订单号等长标识必须已由
    各场景构造器替换为低敏占位符，否则最终边界拒绝外发。
    """
    technical_reference_fields = {
        "chunk_id",
        "citation_chunk_ids",
        "tool_call_id",
        "tool_call_ids",
        "evidence_id",
    }
    if isinstance(value, dict):
        return any(_business_payload_contains_unapproved_identifier(item, str(key)) for key, item in value.items())
    if isinstance(value, list):
        return any(_business_payload_contains_unapproved_identifier(item, field_name) for item in value)
    if not isinstance(value, str):
        return False
    if field_name in technical_reference_fields:
        # 技术引用字段只接受 UUID 或明确的脱敏占位符，不能借字段名夹带正文。
        normalized = value.strip()
        return not bool(
            re.fullmatch(
                r"(?:[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}"
                r"|\[[A-Z_]{2,40}\])",
                normalized,
            )
        )
    return bool(
        EMAIL_PATTERN.search(value)
        or PHONE_PATTERN.search(value)
        or ALPHANUMERIC_ID_PATTERN.search(value)
        or EVALUATION_SECRET_PATTERN.search(value)
    )


def _evaluate_registered_business_payload(text: str, prompt_id: BusinessPromptId) -> PromptSafetyDecision:
    """按注册场景验证业务 JSON，并在通过后保留必要的内部引用。"""
    registration = get_business_prompt(prompt_id)
    if not any(text.startswith(prefix) for prefix in registration.user_prompt_prefixes):
        return PromptSafetyDecision(
            state=PromptSafetyState.UNCERTAIN,
            sanitized_text=UNTRUSTED_JSON_MARKER,
            reason_code="BUSINESS_PROMPT_PREFIX_MISMATCH",
        )
    payload = _extract_json_payload(text)
    if payload is DUPLICATE_JSON_PAYLOAD:
        return PromptSafetyDecision(
            state=PromptSafetyState.UNCERTAIN,
            sanitized_text=UNTRUSTED_JSON_MARKER,
            reason_code="JSON_DUPLICATE_KEY_REJECTED",
        )
    if not isinstance(payload, dict) or set(payload) != registration.payload_keys:
        return PromptSafetyDecision(
            state=PromptSafetyState.UNCERTAIN,
            sanitized_text=UNTRUSTED_JSON_MARKER,
            reason_code="BUSINESS_PROMPT_PAYLOAD_SCHEMA_MISMATCH",
        )
    location_risk = _structured_location_risk(payload)
    if location_risk is not None:
        state, reason_code = location_risk
        return PromptSafetyDecision(
            state=state,
            sanitized_text=UNTRUSTED_JSON_MARKER,
            reason_code=f"BUSINESS_PROMPT_{reason_code}",
        )
    if _business_payload_contains_unapproved_identifier(payload):
        return PromptSafetyDecision(
            state=PromptSafetyState.BLOCKED,
            sanitized_text=UNTRUSTED_JSON_MARKER,
            reason_code="BUSINESS_PROMPT_SENSITIVE_DATA_DETECTED",
        )
    return PromptSafetyDecision(
        state=PromptSafetyState.ALLOWED,
        sanitized_text=text,
        reason_code="REGISTERED_BUSINESS_PAYLOAD_ALLOWED",
    )


def evaluate_prompt_safety(
    text: str,
    *,
    real_model_evaluation_context: RealModelEvaluationSafetyContext | None = None,
    business_prompt_id: BusinessPromptId | None = None,
) -> PromptSafetyDecision:
    """对自由文本给出可审计的三态结论并完成低敏标识脱敏。

    业务规则：
    1. 明确完整地址整段替换并标记 ``blocked``；
    2. 仅固定控制字段及固定枚举值能够由正向协议证明为 ``allowed``；
    3. 客户自由文本、带前缀 JSON、未知字段和未知嵌套结构统一标记 ``uncertain``；
    4. ``uncertain`` 保留低敏正文供本地转人工，但任何 Provider 都不得调用 SDK；
    5. 地址正则仅作为纵深阻断，不再承担“未命中即安全”的放行职责。
    """
    # REAL-AI-05 的逐字冻结载荷可能故意包含敏感占位符或地址风险语句。
    # 只有摘要完全命中的合成样本可以先行放行；任意字符变化都会继续接受
    # 下方完整的地址、标识和结构化数据检查，不能成为通用 DLP 旁路。
    initial_payload = _extract_json_payload(text)
    if real_model_evaluation_context is not None and business_prompt_id is not None:
        return PromptSafetyDecision(
            state=PromptSafetyState.UNCERTAIN,
            sanitized_text=UNTRUSTED_JSON_MARKER,
            reason_code="PROMPT_SAFETY_CONTEXT_CONFLICT",
        )
    if real_model_evaluation_context is not None:
        # 显式评测上下文不允许回退到其他正向协议。摘要、Schema 或 DLP 任一
        # 不匹配都直接失败关闭，避免错误清单意外命中普通控制载荷。
        return _evaluate_authorized_real_model_payload(text, initial_payload, real_model_evaluation_context)
    if business_prompt_id is not None:
        return _evaluate_registered_business_payload(text, business_prompt_id)
    if _is_trusted_real_model_evaluation_payload(text, initial_payload):
        return PromptSafetyDecision(
            state=PromptSafetyState.ALLOWED,
            sanitized_text=text,
            reason_code="TRUSTED_REAL_MODEL_EVALUATION_PAYLOAD_ALLOWED",
        )
    if ADDRESS_REDACTION_MARKER_PATTERN.search(text):
        return PromptSafetyDecision(
            state=PromptSafetyState.BLOCKED,
            sanitized_text="[ADDRESS]",
            reason_code="ADDRESS_REDACTION_MARKER_PRESENT",
        )
    if _is_unlabeled_building_reference(text):
        return PromptSafetyDecision(
            state=PromptSafetyState.UNCERTAIN,
            sanitized_text=_redact_non_address_identifiers(text),
            reason_code="UNTRUSTED_FREE_TEXT_REQUIRES_DLP",
        )
    if _contains_ambiguous_address_context(text):
        return PromptSafetyDecision(
            state=PromptSafetyState.UNCERTAIN,
            sanitized_text=_redact_non_address_identifiers(text),
            reason_code="ADDRESS_CONTEXT_AMBIGUOUS",
        )
    if _contains_high_risk_address(text) or _contains_open_address_signature(text):
        return PromptSafetyDecision(
            state=PromptSafetyState.BLOCKED,
            sanitized_text="[ADDRESS]",
            reason_code="COMPLETE_ADDRESS_DETECTED",
        )
    structured_payload = _extract_json_payload(text)
    if structured_payload is DUPLICATE_JSON_PAYLOAD:
        return PromptSafetyDecision(
            state=PromptSafetyState.UNCERTAIN,
            sanitized_text=UNTRUSTED_JSON_MARKER,
            reason_code="JSON_DUPLICATE_KEY_REJECTED",
        )
    if structured_payload is not None:
        # 固定演示载荷必须逐字段完全匹配服务端常量。先完成精确匹配可避免
        # 合成物流地点被开放地址启发式误判；任意篡改仍会进入下面的通用门禁。
        if _is_trusted_synthetic_demo_payload(structured_payload):
            if not isinstance(structured_payload, dict):
                raise TypeError("可信合成演示载荷必须包含场景 ID")
            scenario_id = structured_payload.get("scenario_id")
            if not isinstance(scenario_id, str):
                raise TypeError("可信合成演示载荷必须包含场景 ID")
            return PromptSafetyDecision(
                state=PromptSafetyState.ALLOWED,
                sanitized_text=build_synthetic_demo_payload(scenario_id),
                reason_code="TRUSTED_SYNTHETIC_DEMO_PAYLOAD_ALLOWED",
            )
        structured_risk = _structured_location_risk(structured_payload)
        if structured_risk is not None:
            state, reason_code = structured_risk
            return PromptSafetyDecision(
                state=state,
                sanitized_text=(
                    "[ADDRESS]" if state == PromptSafetyState.BLOCKED else _redact_non_address_identifiers(text)
                ),
                reason_code=reason_code,
            )
        if _is_trusted_control_payload(text, structured_payload):
            trusted_payload = structured_payload
            if not isinstance(trusted_payload, dict):
                raise TypeError("可信控制载荷必须是 JSON 对象")
            return PromptSafetyDecision(
                state=PromptSafetyState.ALLOWED,
                sanitized_text=_canonicalize_trusted_control_payload(trusted_payload),
                reason_code="TRUSTED_CONTROL_PAYLOAD_ALLOWED",
            )
        return PromptSafetyDecision(
            state=PromptSafetyState.UNCERTAIN,
            sanitized_text=_redact_non_address_identifiers(text),
            reason_code="UNTRUSTED_STRUCTURED_DATA_REQUIRES_DLP",
        )

    return PromptSafetyDecision(
        state=PromptSafetyState.UNCERTAIN,
        sanitized_text=_redact_non_address_identifiers(text),
        reason_code="UNTRUSTED_FREE_TEXT_REQUIRES_DLP",
    )


def evaluate_system_prompt_safety(
    text: str,
    *,
    business_prompt_id: BusinessPromptId | None = None,
) -> PromptSafetyDecision:
    """仅允许不可变工程控制系统提示，其他系统层文本全部失败关闭。

    系统 Prompt 会被所有 Provider 直接发送，因此不能把动态字符串、店铺配置
    或未来新增模板默认为可信。业务 Prompt 后续必须通过架构评审建立版本化注册表。
    """
    if business_prompt_id is not None:
        registration = get_business_prompt(business_prompt_id)
        if hashlib.sha256(text.encode("utf-8")).hexdigest() == registration.content_sha256:
            return PromptSafetyDecision(
                state=PromptSafetyState.ALLOWED,
                sanitized_text=text,
                reason_code="REGISTERED_BUSINESS_SYSTEM_PROMPT_ALLOWED",
            )
        decision = evaluate_prompt_safety(text)
        return PromptSafetyDecision(
            state=(
                PromptSafetyState.BLOCKED
                if decision.state == PromptSafetyState.BLOCKED
                else PromptSafetyState.UNCERTAIN
            ),
            sanitized_text=SYSTEM_PROMPT_BLOCKED_MARKER,
            reason_code=(
                "SYSTEM_PROMPT_SENSITIVE_DATA_DETECTED"
                if decision.state == PromptSafetyState.BLOCKED
                else "BUSINESS_SYSTEM_PROMPT_REGISTRY_MISMATCH"
            ),
        )
    if text == TRUSTED_PROVIDER_CONTRACT_SYSTEM_PROMPT:
        return PromptSafetyDecision(
            state=PromptSafetyState.ALLOWED,
            sanitized_text=TRUSTED_PROVIDER_CONTRACT_SYSTEM_PROMPT,
            reason_code="TRUSTED_SYSTEM_PROMPT_ALLOWED",
        )
    if text == SYNTHETIC_DEMO_SYSTEM_PROMPT:
        return PromptSafetyDecision(
            state=PromptSafetyState.ALLOWED,
            sanitized_text=SYNTHETIC_DEMO_SYSTEM_PROMPT,
            reason_code="TRUSTED_SYNTHETIC_DEMO_SYSTEM_PROMPT_ALLOWED",
        )
    if text == REAL_MODEL_EVALUATION_SYSTEM_PROMPT:
        return PromptSafetyDecision(
            state=PromptSafetyState.ALLOWED,
            sanitized_text=REAL_MODEL_EVALUATION_SYSTEM_PROMPT,
            reason_code="TRUSTED_REAL_MODEL_EVALUATION_SYSTEM_PROMPT_ALLOWED",
        )
    decision = evaluate_prompt_safety(text)
    if decision.state == PromptSafetyState.BLOCKED:
        return PromptSafetyDecision(
            state=PromptSafetyState.BLOCKED,
            sanitized_text=SYSTEM_PROMPT_BLOCKED_MARKER,
            reason_code="SYSTEM_PROMPT_SENSITIVE_DATA_DETECTED",
        )
    return PromptSafetyDecision(
        state=PromptSafetyState.UNCERTAIN,
        sanitized_text=SYSTEM_PROMPT_BLOCKED_MARKER,
        reason_code="UNTRUSTED_SYSTEM_PROMPT_REQUIRES_REGISTRY",
    )


def sanitize_prompt_text(text: str) -> str:
    """屏蔽模型任务不需要的地址、邮箱、电话和长标识。

    Args:
        text: 客户当前消息或历史消息。

    Returns:
        保留业务语义但去除明显客户标识的文本。
    """
    return evaluate_prompt_safety(text).sanitized_text
