"""识别没有可信工具依据的退款、退费、赔偿和补偿业务事实。"""

import re
import unicodedata

SEMANTIC_SPLIT_PATTERN = re.compile(
    r"[。！？!?；;\n\r]+|(?:，|,)?\s*(?:但(?:是)?|不过|然而|可是|却|另外|同时|反而)\s*|"
    r"(?:并且|而且|而)\s*(?=(?:本订单|本次|当前|这笔|您的|你的|平台|系统|商家|卖家|我们|我方))|"
    r"(?:,?\s*\b(?:but|however|whereas)\b\s*)|"
    r"(?:,\s*\b(?:yet|while)\b\s*)|"
    r"(?:,?\s*\band\b\s+)(?=(?:this|current|your|the\s+(?:platform|seller|merchant|system))\b)",
    re.IGNORECASE,
)
CONCESSIVE_PREFIX_PATTERN = re.compile(r"^(?:(?:although|though|despite)\b|尽管|虽然)", re.IGNORECASE)
CONCESSIVE_CONTINUATION_PATTERN = re.compile(r"\b(?:still|yet)\b|仍(?:然)?", re.IGNORECASE)
# 保留换行作为强语义边界，只折叠行内空白。
WHITESPACE_PATTERN = re.compile(r"[^\S\r\n]+")

# 金额类通用词只有与资金返回动作共同出现才属于退款主题，避免普通付款说明
# 被这条高风险规则误判。
CHINESE_REFUND_TOPIC_PATTERN = re.compile(
    r"(?:退款(?:申请|款项|结果|审批|审核|状态|单|请求|金额|金|资格|时间|政策|流程)?|"
    r"退费(?:申请)?|退钱|赔偿(?:申请|款|方案)?|补偿(?:申请|款|方案)?|赔付(?:申请|款)?|"
    r"退赔(?:申请|款)?|返款(?:申请)?|(?:退回|退还|返还)(?:全部|全额|部分|原路)?(?:的)?款项|"
    r"原路(?:退(?:回|还|了)?|返回)|"
    r"(?:钱|款项|货款|金额).{0,10}(?:退回|退还|返还|退至|返回|汇回|打入|打到|打回|到账|入账))"
)
CHINESE_DIRECT_RECIPIENT_ACTION_PATTERN = re.compile(
    r"(?:我|我们|这边|平台|系统|商家|卖家)?(?:已经|已|正在|现在|这就|马上|立即)?"
    r"(?:给您|为您|给你|为你)(?:安排|办理|发起|执行|处理|批准|完成)?"
    r"(?:(?:原路|全额|部分)?(?:退款|退费|退钱|赔偿|补偿|赔付|返款|原路退)|"
    r"(?:退回|退还|返还)(?:全部|全额|部分|原路)?(?:的)?(?:款项|货款|金额))"
)
CHINESE_NON_ASSERTIVE_PATTERNS = (
    re.compile(
        r"(?:平台|系统|商家|卖家|支付机构).{0,8}(?:尚未|未曾|从未|并未|没有|不得|不能|不会|拒绝).{0,20}"
        r"(?:退款|退费|赔偿|补偿|批准|处理|完成|确认)"
    ),
    re.compile(r"(?:无法|不能|未能).{0,10}(?:确认|证实)"),
    re.compile(r"(?:无法|不能|未能).{0,16}(?:证明|说明|断定).{0,20}(?:已经|已|退款|退费|退还|返还|到账)"),
    re.compile(r"(?:没有|无|尚无).{0,8}(?:证据|依据|确认|定论)"),
    re.compile(r"(?:不|并不|并非).{0,6}(?:表示|代表|意味着)"),
    re.compile(r"(?:请勿|不要|勿|别).{0,20}(?:相信|采信|当作|视为)"),
    re.compile(r"(?:请勿|不要|勿|别).{0,24}(?:理解成|理解为)"),
    re.compile(r"(?:既)?(?:尚未|未).{0,10}(?:确认|承诺).{0,20}(?:也)?(?:尚未|未).{0,10}(?:确认|承诺)"),
    re.compile(r"(?:信息|资料|材料).{0,8}(?:不足|不充分).{0,12}(?:确定|判断)"),
    re.compile(r"(?:未必|不一定).{0,10}(?:获批|批准|通过|到账|完成)"),
    re.compile(r"(?:无法|不能|不会|无权).{0,18}(?:退款|退费|退钱|赔偿|补偿|承诺)"),
    re.compile(r"(?:退款|退费|赔偿|补偿|返款).{0,10}(?:不会自动生效|尚无定论|尚未确认)"),
    re.compile(r"(?:不|并不|并非).{0,8}(?:等于|保证).{0,12}(?:通过|批准|获批|完成|到账)"),
    re.compile(r"(?:若|如果|只有|除非).{0,48}(?:才|方|可能)"),
    re.compile(r"(?:可能|也许|或许).{0,24}(?:也可能|或|或者|拒绝|不予)"),
    re.compile(r"(?:不能|无法).{0,10}(?:说明|断定).{0,16}(?:通过|批准|获批|完成|成立)"),
    re.compile(r"(?:退款|退费|赔偿|补偿)(?:申请|结果|审批|审核)?.{0,8}仍待.{0,12}(?:确认|判定|审核)"),
    re.compile(r"(?:退款|退费|赔偿|补偿).{0,8}(?:到账)?时间.{0,8}(?:没有|无).{0,8}(?:统一|固定)标准"),
    re.compile(
        r"(?:记录|资料|材料|截图|证据|依据).{0,12}(?:不能|无法|不足以|不够).{0,8}"
        r"(?:支持|证明|认定|表明|显示)"
    ),
    re.compile(
        r"(?:没有|无).{0,6}(?:足够|充分)?(?:资料|材料|证据|依据).{0,8}"
        r"(?:可|足以)?(?:支持|证明|认定|表明|显示)"
    ),
    re.compile(
        r"(?:当前|现有|这张|该|从现有)?(?:记录|信息|资料|材料|截图|证据|页面提示).{0,10}"
        r"(?:推不出|支撑不了|无法判断|不能推出|尚不能推出|不足以支撑|不足以说|不能由.{0,8}推导出)"
    ),
    re.compile(r"(?:一旦|假如|倘若|要是|待).{0,48}(?:才|方可|会|后)"),
    re.compile(r"(?:说法|结论|结果).{0,8}(?:仍)?(?:未经核实|未获证实|没有得到证实)"),
    # “是否/能否”引导的是待核验问题，不是当前已经成立的业务事实；后续
    # 独立句仍会单独扫描，因此该规则不能遮蔽真正的完成声明。
    re.compile(r"^(?:是否|能否)[^。！？!?；;\n\r]{0,64}$"),
)
# 这些模式描述整个命题的证据、疑问或条件状态，可以控制位于它们之前
# 的结果候选。它们与普通前置否定分开，避免安全前句遮蔽后续独立事实。
CHINESE_PROPOSITION_NON_ASSERTIVE_PATTERNS = (
    # 后置证据否定控制前面的命题；“已经结清”只是被否定的判断，不能
    # 因为完成词出现在否定词之前就被当成当前客户事实。
    re.compile(
        r"(?:判断|说法|结论|命题|断言).{0,12}(?:没有|无).{0,10}"
        r"(?:事实根据|事实基础|证明力|证据支持|证明依据)"
    ),
    re.compile(
        r"(?:记录|证据|材料|信息).{0,16}(?:对|关于).{0,32}(?:没有|无).{0,10}"
        r"(?:证明力|证明作用|证据效力|支持力)"
    ),
    re.compile(
        r"(?:退款|退费|赔偿|补偿|赔付|返款|到账|入账).{0,24}是否(?:属实|成立|发生|完成)?"
        r".{0,24}(?:未知|未定|无法确定|尚无结论)"
    ),
    re.compile(r"唯有.{0,48}才(?:可能|可以|可|会)"),
    re.compile(
        r"(?:文字|说法|主张|声明|判断|结论).{0,32}"
        r"(?:无法|不能|尚未|未曾|没有).{0,24}(?:证据|材料|事实|依据)?.{0,12}"
        r"(?:支持|证实|核验|确认)"
    ),
    re.compile(r"(?:不能|不得|不应).{0,12}(?:视作|当作|认定为).{0,10}(?:既成)?(?:事实|结论|结果)"),
    re.compile(r"(?:仅是|只是|仅为).{0,12}(?:未经|未获|尚未).{0,12}(?:核验|证实|确认).{0,8}(?:推测|说法|主张)"),
    re.compile(r"(?:文字|说法|主张|声明|陈述|判断|结论).{0,24}(?:仍)?(?:处于|保持)?(?:待证|待核验|未证)状态"),
    # 叙述、主张和假说描述的是“某句话能否成立”，审计、确认、判断或
    # 验证状态控制整个命题；其中出现完成词不代表当前客户资金结果成立。
    re.compile(
        r"(?:叙述|说法|主张|声明|陈述|判断|结论|假说).{0,56}"
        r"(?:仍待|尚待|等待|待)(?:外部|独立|人工|平台)?(?:审计|核验|复核|确认|验证)"
    ),
    re.compile(r"(?:没有|无).{0,8}(?:核验人|复核人|审核人|审计人|审计员|核验员|复核员).{0,12}(?:确认|证实|认定|判断)"),
    re.compile(r"(?:现有|当前|已有).{0,6}(?:材料|资料|证据|信息).{0,12}(?:没有|未).{0,8}(?:作出|形成)(?:判断|结论)"),
    re.compile(
        r"(?:所谓|声称|号称).{0,56}(?:只是|仅是|不过是).{0,16}(?:尚未|未经|未获)?(?:验证|核验)?(?:的)?(?:假说|推测|猜测)"
    ),
    re.compile(
        r"(?:即便|即使|纵使).{0,56}(?:也)?(?:不能|不得|不应).{0,24}"
        r"(?:描述|认定|视为|当作|写成)(?:当前|既成)?(?:状态|事实|结论|结果)?"
    ),
    re.compile(
        r"(?:除非|除经).{0,32}(?:外|否则)?.{0,12}(?:不能|不得|不应).{0,24}(?:视为|当作|写成|认定为)(?:既成)?事实"
    ),
    # 认识态控制描述的是“命题是否成立”，不是退款本身已经完成。这里按
    # 控制关系识别，不枚举被讨论的每一种技术资产或资金同义词。
    re.compile(
        r"(?:将|把).{0,56}(?:作为|当作|视为|认定为)(?:既成)?(?:事实|结论|结果).{0,24}"
        r"(?:仍)?(?:缺少|缺乏|没有|无).{0,16}(?:授权|事实|证据)?(?:依据|基础|支持)"
    ),
    re.compile(
        r"(?:现阶段|目前|当前)?(?:不能|无法|不足以).{0,24}(?:从|由).{0,32}"
        r"(?:材料|资料|证据|记录|信息).{0,24}(?:推出|推导出|推断出|得出)"
    ),
    re.compile(
        r"(?:审计|核验|验证|复核|事实核查)(?:意见|结论|结果)?.{0,32}"
        r"(?:未置可否|不置可否|没有结论|未作判断|不支持|无法确认)"
    ),
    re.compile(
        r"(?:说法|叙述|主张|声明|命题|假说|观点|结论).{0,40}"
        r"(?:尚待|仍待|等待|需要|有待).{0,16}(?:事实)?(?:核查|验证|核验|审计|复核|确认)"
    ),
    re.compile(
        r"(?:只是|仅是|不过是).{0,20}(?:需要|有待|尚待|仍待)?(?:验证|核验|待决|待证).{0,12}(?:命题|假说|推测|主张)"
    ),
)
CHINESE_POLICY_PATTERNS = (
    re.compile(
        r"(?:退款|退费|赔偿|补偿|赔付|退赔|返款)(?:申请|方案)?.{0,10}"
        r"(?:须|需|需要|应当).{0,24}(?:提出|申请|提交|材料|审核|评估)"
    ),
    re.compile(r"(?:退款|退费|赔偿|补偿|赔付|退赔|返款).{0,8}(?:仅|只)适用于"),
    re.compile(r"(?:退款|退费|赔偿|补偿|赔付|退赔|返款).{0,10}由.{0,16}(?:负责|承担)"),
    re.compile(r"(?:退款|退费|赔偿|补偿).{0,8}资格.{0,16}(?:为依据|取决于)"),
    re.compile(r"(?:退款|退费|赔偿|补偿|赔付|退赔|返款)(?:申请)?.{0,12}(?:会|将)?由.{0,16}(?:审核|评估)"),
    re.compile(r"(?:退款|退费|赔偿|补偿|赔付|退赔|返款)(?:申请)?.{0,12}会进入.{0,12}(?:审核|审批)流程"),
    re.compile(r"(?:退款|退费|赔偿|补偿|赔付|退赔|返款).{0,16}(?:取决于|通常会|一般会)"),
    re.compile(r"(?:退款|退费|赔偿|补偿).{0,12}(?:政策|申请条件|申请步骤)"),
    re.compile(r"(?:如何|怎么).{0,20}(?:退款|退费|赔偿|补偿|返款|赔付)"),
    re.compile(r"(?:可以|可在).{0,24}(?:查询|查看).{0,24}(?:退款|退费|赔偿|补偿|返款|赔付)"),
    re.compile(r"(?:退款|退费|赔偿|补偿|返款|赔付).{0,24}(?:可以|可在).{0,16}(?:查询|查看)"),
    re.compile(r"(?:退款|退费|赔偿|补偿).{0,16}是否.{0,16}(?:查询|查看|通知为准|为准)"),
    re.compile(r"(?:说明|告诉|指导).{0,18}(?:退款|退费|赔偿|补偿).{0,10}(?:政策|流程|条件|步骤)"),
    re.compile(r"(?:协助|指导).{0,8}(?:提交|申请).{0,8}(?:退款|退费|赔偿|补偿)"),
    re.compile(r"(?:联系|致电).{0,24}(?:客服|人工|处理).{0,12}(?:退款|退费|赔偿|补偿)"),
    re.compile(
        r"(?:若|如果|如|发生|满足|符合).{0,24}(?:可|可以|才能|方可).{0,16}"
        r"(?:提出|提交|申请).{0,10}(?:退款|退费|赔偿|补偿|返款|赔付)"
    ),
    re.compile(r"(?:是否可|能否|是否能够).{0,8}(?:退款|退费|赔偿|补偿).{0,20}(?:规则|条件).{0,8}为准"),
    re.compile(
        r"(?:退款|退费|赔偿|补偿).{0,10}是否.{0,12}(?:成立|可用|适用).{0,20}"
        r"(?:等待|须|需|应).{0,12}(?:人工|平台).{0,8}(?:核验|判断|审核)"
    ),
    re.compile(
        r"(?:提交|提供).{0,10}(?:材料|资料).{0,24}(?:平台|人工).{0,8}"
        r"(?:判断|核验|审核).{0,10}(?:是否)?(?:退款|退费|赔偿|补偿)"
    ),
    re.compile(r"只有.{0,24}(?:条件|审核).{0,12}(?:后)?.{0,12}才会.{0,8}(?:办理|发起)(?:退款|退费|赔偿|补偿)"),
    re.compile(r"是否(?:退款|退费|赔偿|补偿).{0,4}由.{0,24}(?:判定|决定|审核)"),
    re.compile(r"(?:平台|商家|卖家).{0,8}有权拒绝.{0,20}(?:退款|退费|赔偿|补偿)(?:申请|请求)?"),
)
CHINESE_CONTEXTUAL_FACT_PATTERN = re.compile(
    r"(?:审核|审批)(?:结果)?.{0,8}(?:已|已经).{0,6}(?:通过|批准|获批)|"
    r"(?:您的|你的)?(?:申请|款项|补偿款|赔偿款).{0,10}(?:已|已经).{0,8}"
    r"(?:获批|批准|完成|到账|入账|打款)|"
    r"(?:平台|系统|商家|卖家).{0,12}(?:已|已经).{0,8}(?:批准|完成|确认).{0,8}(?:退款|退费|成功)|"
    r"(?:款项|补偿款|赔偿款).{0,10}(?:已|已经).{0,6}(?:到账|入账|退回|返还)"
)

ENGLISH_REFUND_TOPIC_PATTERN = re.compile(
    r"\b(?:refund(?:s|ed|ing)?|reimburse(?:ment|ments|d|ing)?|compensat(?:ion|ed|ing)|money back)\b|"
    r"\b(?:money|funds?)\b.{0,36}\b(?:return(?:ed|ing)?|credit(?:ed|ing)?|reach(?:es|ed|ing)?)\b"
)
ENGLISH_REFERENTIAL_FACT_PATTERN = re.compile(
    r"\b(?:platform|seller|merchant|system|we|they)\b.{0,24}"
    r"\b(?:approved|completed|issued|credited|refunded|reimbursed|processed)\b.{0,12}\b(?:it|this|that)\b|"
    r"\b(?:it|this|that)\b.{0,16}\b(?:was|is|has been)\b.{0,8}"
    r"\b(?:approved|completed|issued|credited|refunded|processed)\b|"
    r"\b(?:review|approval)\s+result\b.{0,12}\b(?:is|was|has been)\b.{0,8}\b(?:approved|complete)\b|"
    r"\byours\b.{0,12}\b(?:is|was|has been)\b.{0,8}\b(?:approved|complete|credited)\b|"
    r"\b(?:current|this|the|your)\s+(?:request|application)\b.{0,8}"
    r"\b(?:is|was|has been)\b.{0,8}\b(?:approved|complete|credited|processed)\b"
)
ENGLISH_NON_ASSERTIVE_PATTERNS = (
    re.compile(r"\b(?:has|have|had|is|are|was|were|did|does|do)\s+not\b"),
    re.compile(r"\bno\s+(?:platform|seller|merchant|provider|system|party)\b"),
    re.compile(r"\b(?:if|unless)\b.{0,64}\b(?:may|might|can|could|will|would)\b"),
    re.compile(r"\b(?:may|might|could)\b.{0,32}\b(?:or|reject|decline|deny)\b"),
    re.compile(r"\b(?:cannot|can't|could not|unable to)\b.{0,32}\b(?:confirm|verify|prove)\b"),
    re.compile(r"\b(?:no|without)\s+(?:confirmation|evidence|proof)\b"),
    re.compile(r"\b(?:does not|doesn't|do not|don't)\b.{0,20}\b(?:prove|mean|represent|trust|treat)\b"),
    re.compile(r"\b(?:will not|won't|cannot|can't)\b.{0,24}\b(?:refund|reimburse|compensate|promise)\w*\b"),
    re.compile(r"\b(?:refunds?|reimbursements?|compensation)\b.{0,24}\b(?:not guaranteed|not confirmed)\b"),
    re.compile(r"\bnot\s+(?:a\s+)?confirmation\s+of\b"),
    re.compile(r"\b(?:should|must|can)\s+not\b.{0,20}\btreated as\b.{0,12}\bproof\b"),
    re.compile(r"\bno\s+decision\s+has\s+been\s+made\b"),
    re.compile(r"\bdoes\s+not\s+guarantee\b.{0,16}\b(?:approval|completion|payment)\b"),
    re.compile(r"\b(?:approval|decision|determination)\b.{0,12}\b(?:remains?\s+)?undecided\b"),
    re.compile(r"\bno\s+determination\s+exists\b"),
    re.compile(
        r"\b(?:evidence|record|information|materials?|screenshot)\b.{0,20}"
        r"\b(?:is|are)?\s*(?:insufficient|unable)\b.{0,16}\b(?:show|prove|establish|support)\b"
    ),
    re.compile(
        r"\b(?:this|the)\s+(?:record|screenshot)\s+cannot\s+"
        r"(?:show|prove|establish|support)\b"
    ),
    re.compile(r"\b(?:no|without)\s+(?:sufficient\s+)?(?:basis|grounds?|evidence)\b.{0,16}\bconclude\b"),
    re.compile(r"\bnothing\b.{0,24}\b(?:proves?|shows?|establishes?|supports?)\b"),
    re.compile(r"\bno\s+(?:refund|reimbursement|compensation)\s+decision\s+was\s+made\b"),
    re.compile(r"\b(?:record|evidence|information)\b.{0,20}\b(?:does not warrant|falls short of)\b"),
    re.compile(r"\b(?:remains?\s+)?unproven\s+that\b"),
    re.compile(r"\b(?:provided|assuming)\b.{0,48}\b(?:will|would|may|might|can|could|appears?)\b"),
    re.compile(r"\b(?:no|neither)\s+[^,.;!?]{0,24}\b(?:answer|determine|say|tell)\s+whether\b"),
)
ENGLISH_PROPOSITION_NON_ASSERTIVE_PATTERNS = (
    # 证据否定既可能位于声明之前，也可能作为后置评价出现；两者都只
    # 描述命题的证据状态，不断言退款事实成立。
    re.compile(
        r"\b(?:proposition|claim|assertion|finding|statement)\b.{0,80}"
        r"\b(?:lacks?|has no|without)\b.{0,24}"
        r"\b(?:evidentiary support|factual foundation|evidence|support|proof)\b"
    ),
    re.compile(
        r"\b(?:record|evidence|material|information)\b.{0,24}"
        r"\b(?:gives?|carries?|has)\s+no\s+(?:evidentiary\s+)?(?:weight|support|proof)\b"
    ),
    re.compile(r"\bwhether\b.{0,72}\b(?:remains?|is|stays?)\s+(?:unresolved|unknown|undetermined)\b"),
    re.compile(r"\bonly\b.{0,56}\b(?:could|would|may|might)\b.{0,40}\b(?:establish|prove|confirm)\b"),
    re.compile(r"\bin\s+the\s+event\s+of\b.{0,48}\b(?:would|could|may|might)\b"),
    re.compile(
        r"\b(?:wording|statement|claim|assertion)\b.{0,96}"
        r"\b(?:remains?\s+)?(?:unsupported|unverified|unproven)\b"
    ),
    re.compile(r"\bcannot\s+be\s+treated\s+as\b.{0,20}\b(?:settled|complete|completed|fact|result)\b"),
    re.compile(r"\bsubject\s+to\b.{0,48}\b(?:would|could|may|might)\b"),
    # 审计、核验和证据沉默描述的是命题状态，不是资金状态。限定命题载体
    # 与控制谓词同时出现，避免单个 audit/evidence 词成为整句通行证。
    re.compile(
        r"\b(?:narrative|claim|statement|assertion|allegation|hypothesis)\b.{0,96}"
        r"\b(?:awaits?|is\s+awaiting|remains?\s+pending)\b.{0,24}"
        r"\b(?:independent\s+|external\s+)?(?:audit|review|verification|confirmation)\b"
    ),
    re.compile(
        r"\bno\s+(?:reviewer|verifier|auditor|examiner)\b.{0,48}"
        r"\b(?:confirm|verify|establish|determine|certify)\b"
    ),
    re.compile(
        r"\b(?:available|current|existing)\s+(?:evidence|record|materials?|information)\b.{0,24}"
        r"\b(?:is|are|remains?)\s+silent\s+on\s+whether\b"
    ),
    # 以命题载体和认识态谓词建立方向关系，避免继续枚举 ontology、Avro、
    # metric 等开放技术对象，同时不让前句免责声明遮蔽后句资金事实。
    re.compile(
        r"\b(?:narrative|claim|statement|assertion|proposition|opinion|finding|allegation)\b.{0,96}"
        r"\b(?:remains?\s+)?(?:subject\s+to|awaits?|is\s+awaiting|requires?)\b.{0,32}"
        r"\b(?:fact[- ]?checking|validation|verification|audit|review|confirmation)\b"
    ),
    re.compile(
        r"\b(?:audit|verification|review|fact[- ]?checking)\s+(?:opinion|finding|result|conclusion)\b.{0,64}"
        r"\b(?:takes?\s+no\s+position|does\s+not\s+support|is\s+inconclusive|reaches?\s+no\s+conclusion)\b"
    ),
    re.compile(
        r"\b(?:treating|describing|presenting|regarding)\b.{0,72}\b(?:as|to\s+be)\b.{0,40}"
        r"\b(?:still\s+)?(?:lacks?|has\s+no|is\s+without)\b.{0,24}"
        r"\b(?:authorized|factual|evidentiary)?\s*(?:basis|authorization|evidence|support)\b"
    ),
    re.compile(
        r"\b(?:evidence|records?|materials?|information)\b.{0,64}"
        r"\b(?:does\s+not\s+entail|cannot\s+establish|cannot\s+support|is\s+silent\s+(?:on|about))\b"
    ),
)
ENGLISH_POLICY_PATTERNS = (
    re.compile(
        r"\b(?:refunds?|reimbursements?|compensation)\b.{0,20}"
        r"\b(?:must|should|need to|needs to|requires?)\b.{0,24}"
        r"\b(?:request(?:ed)?|submit(?:ted)?|manual review|approval|documents?)\b"
    ),
    re.compile(r"\b(?:refunds?|reimbursements?|compensation)\b.{0,20}\b(?:is|are) governed by\b"),
    re.compile(r"\b(?:refunds?|reimbursements?|compensation)\b.{0,20}\b(?:is|are) available only\b"),
    re.compile(r"\b(?:refunds?|reimbursements?|compensation|funds?)\b.{0,28}\bonly after\b"),
    re.compile(r"\b(?:refunds?|reimbursements?|compensation)\b.{0,24}\bsubject to\b"),
    re.compile(r"\b(?:refunds?|reimbursements?|compensation)\b.{0,24}\bdepends? on\b"),
    re.compile(
        r"\b(?:explain|show|find)\b.{0,24}\b(?:refunds?|reimbursements?|compensation)\b.{0,16}\b(?:policy|steps?|process|conditions?)\b"
    ),
    re.compile(
        r"\b(?:can|could)\b.{0,20}\b(?:check|review|find)\b.{0,24}\b(?:refunds?|reimbursements?|compensation)\b"
    ),
    re.compile(
        r"\b(?:can|could)\b.{0,12}\b(?:request|apply for)\b.{0,12}\b(?:refunds?|reimbursements?|compensation)\b"
    ),
    re.compile(r"\b(?:refunds?|reimbursements?|compensation)\b.{0,24}\bunder\b.{0,16}\b(?:policy|rules?)\b"),
    re.compile(r"\b(?:refunds?|reimbursements?|compensation)\b.{0,16}\bmay be requested\b"),
    re.compile(r"\b(?:qualify|qualifies|eligible)\b.{0,12}\bfor\b.{0,8}\b(?:refunds?|reimbursements?|compensation)\b"),
    re.compile(
        r"\b(?:must|should|need to|needs to)\b.{0,24}\b(?:submit|provide)\b.{0,10}\b(?:documents?|evidence)\b"
        r".{0,24}\b(?:apply(?:ing)? for|request(?:ing)?)\b.{0,10}\b(?:refunds?|reimbursements?|compensation)\b"
    ),
    re.compile(r"\b(?:refunds?|reimbursements?|compensation)\b.{0,20}\bonly if\b"),
    re.compile(r"\bdetermines? whether\b.{0,20}\b(?:refunds?|reimbursements?|compensation)\b"),
    re.compile(r"\b(?:refund|reimbursement|compensation)\s+timing\b.{0,16}\bvar(?:y|ies)\b"),
    re.compile(
        r"\b(?:seller|merchant|platform)\b.{0,12}\bmay reject\b.{0,16}\b(?:refund|reimbursement|compensation)\b"
    ),
    re.compile(
        r"\b(?:approval|review|verification)\b.{0,24}\b(?:is|would be|remains?)\b.{0,12}"
        r"\b(?:a\s+)?prerequisite\b.{0,24}\bbefore\b.{0,24}"
        r"\b(?:refund|reimbursement|compensation)\b"
    ),
)

# 角色模式不依赖固定的“退款已到账”短语，而是要求同一命题同时具有客户
# 金融目标、资金返还来源和余额结果变化。这样卡片、账面、额度等新表述可
# 失败关闭，同时不会仅因技术文档出现 refund 一词就触发。
_CHINESE_FINANCIAL_TARGET = (
    r"(?:顾客|买家|消费者|用户|收货人|持卡人|原持卡人|客户|买方|收件人|购买者|付款人|收款人|"
    r"订购人|订货人|购方|会员|买受人|收款方|购货人|购物者|账户持有人|卡主)(?:的)?"
    r"[^，,。！？!?；;\n\r]{0,12}"
    r"(?:预付卡|储值卡|支付卡|银行卡|原卡|卡面|钱包|预付账户|资金账户|账户|余额|额度|净值|结余|"
    r"账面|可用|可支配|权益|支付准备金|预付金|账户结存|可花额度|电子余额|账户总额|消费能力)"
)
_CHINESE_RETURN_SOURCE = (
    r"(?:退来|退回|退还|退转|返还|返来|回补|回送|冲销|返付|回款|补回|回填|回拨|返拨|汇回|划回|"
    r"撤回|原交易冲正|逆向清算|贷记|撤销支付|逆向入账|回冲|撤单|作废|逆向结算|撤销扣款)"
)
_CHINESE_FINANCIAL_STATE = (
    r"(?:涵盖|包含|上升|升高|增加|增长|变高|计入|记入|现存|反映|构成|补回|回填|新增|多出|出现|"
    r"留有|呈现|抬高|补足|恢复|纳入|叠加|充足|回到原水平|吸收|抬升)"
)
CHINESE_FINANCIAL_STATE_ASSERTION_PATTERN = re.compile(
    rf"(?:{_CHINESE_FINANCIAL_TARGET}"
    rf"(?=[^，,。！？!?；;\n\r]{{0,140}}{_CHINESE_RETURN_SOURCE})"
    rf"(?=[^，,。！？!?；;\n\r]{{0,140}}{_CHINESE_FINANCIAL_STATE})|"
    rf"{_CHINESE_RETURN_SOURCE}"
    rf"(?=[^，,。！？!?；;\n\r]{{0,140}}{_CHINESE_FINANCIAL_TARGET})"
    rf"(?=[^，,。！？!?；;\n\r]{{0,140}}{_CHINESE_FINANCIAL_STATE}))"
    r"[^，,。！？!?；;\n\r]{0,160}"
)
_ENGLISH_FINANCIAL_TARGET = (
    r"(?:(?:[a-z][a-z'-]{1,24}'s|buyer|customer|shopper|recipient|cardholder|purchaser|payee)"
    r"[^,.;!?\n\r]{0,28}(?:card|wallet|account|balance|credit|limit|total|statement|ledger|equity|"
    r"reserve|purse|register|book|power)|"
    r"(?:spendable|available|account|wallet|card|ledger|statement|payment|prepaid|deposit|stored-funds)"
    r"[^,.;!?\n\r]{0,28}"
    r"(?:buyer|customer|shopper|recipient|cardholder|purchaser|payee))"
)
_ENGLISH_RETURN_SOURCE = (
    r"(?:route\w*\s+back|refund\w*|reimburs\w*|repay\w*|revers\w*|return\w*|remit\w*|sent\s+back|"
    r"cancel\w*(?:\s+the)?\s+(?:debit|charge|payment)|void\w*(?:\s+the)?\s+(?:debit|charge|payment)|"
    r"restor\w*|(?:order|sale|purchase|settlement|transaction)\s+(?:price|value|proceeds|amount|funds?)|"
    r"principal|charge)"
)
_ENGLISH_FINANCIAL_STATE = (
    r"(?:augment\w*|enrich\w*|expand\w*|increas\w*|grow\w*|grew|grown|ris\w*|rose|factor\w*\s+in|"
    r"rebound\w*|recover\w*|restor\w*|show\w*|higher|lift\w*|top\w*\s+up|part\s+of|contribut\w*|"
    r"list\w*|carr\w*|contain\w*|reflect\w*)"
)
ENGLISH_FINANCIAL_STATE_ASSERTION_PATTERN = re.compile(
    rf"(?:{_ENGLISH_FINANCIAL_TARGET}"
    rf"(?=[^,.;!?\n\r]{{0,200}}\b{_ENGLISH_RETURN_SOURCE}\b)"
    rf"(?=[^,.;!?\n\r]{{0,200}}\b{_ENGLISH_FINANCIAL_STATE}\b)|"
    rf"\b{_ENGLISH_RETURN_SOURCE}\b"
    rf"(?=[^,.;!?\n\r]{{0,200}}{_ENGLISH_FINANCIAL_TARGET})"
    rf"(?=[^,.;!?\n\r]{{0,200}}\b{_ENGLISH_FINANCIAL_STATE}\b))"
    r"[^,.;!?\n\r]{0,220}",
    re.IGNORECASE,
)

# 旧角色模式需要预先知道每一种“钱包/准备金/额度”和“回冲/贷记”词形，
# 开放集只要替换同义词就会漏放。这个补充模式只依赖稳定语义骨架：某个
# 实例所有者的金融对象发生可用性/数值变化，且变化由资金回退来源引起。
# 技术文档即使出现 account，也不会同时满足结果和资金来源两个约束。
ENGLISH_CAUSAL_FINANCIAL_CHANGE_PATTERN = re.compile(
    r"\b(?:the\s+)?[a-z][a-z'-]*(?:'s|’s)\s+"
    r"(?=[^,.;!?\n\r]{0,80}\b(?:account|balance|cash|funds?|credit|payment|purchase|purchasing|"
    r"spending|wallet|reserve|deposit|prepaid|stored|card|ledger|equity|value|position|capacity|"
    r"headroom|float|cushion|power|assets?)\b)"
    r"(?=[^,.;!?\n\r]{0,120}\b(?:reviv\w*|recover\w*|restor\w*|rebound\w*|normaliz\w*|"
    r"increas\w*|ris(?:e|es|en)|rose|grew|grow\w*|expand\w*|augment\w*|enrich\w*|"
    r"became\s+(?:usable|available)|become\s+(?:usable|available)|returned\s+to)\b)"
    r"(?=[^,.;!?\n\r]{0,160}\b(?:after|following|when|once|because\s+of|due\s+to)\b"
    r"[^,.;!?\n\r]{0,72}\b(?:credit|write-back|reversal|rollback|unwind|correction|refund|"
    r"repayment|return|void\w*|cancel\w*|revers\w*|chargeback|settlement|clearing|acquirer|gateway)\b)"
    r"[^,.;!?\n\r]{1,180}",
    re.IGNORECASE,
)

# 高风险事实必须绑定退款审批、执行或资金论元。这里枚举的是稳定的业务角色，
# 不是开放的结果动词；动作可以变化，但“页面已加载”不会因为出现 refund
# 就被当成资金或审批事实。
CHINESE_BUSINESS_OUTCOME_ASSERTION_PATTERNS = (
    CHINESE_FINANCIAL_STATE_ASSERTION_PATTERN,
    # “客户金融容器 + 结果状态 + 资金对象”是完整的资金结果命题。它覆盖
    # 主动、被动和资金来源后置语序，不要求退款动词或业务主体先出现。
    re.compile(
        r"[\u4e00-\u9fff]{1,8}(?:的)?(?:原卡|支付卡|银行卡|储值卡|电子钱包|钱包|电子账户|账户|余额)"
        r"(?:里|上|内|中)?[^，,。！？!?；;\n\r]{0,12}"
        r"(?:多出(?:了)?|出现(?:了)?|显示|呈现|看到(?:了)?|看见(?:了)?|记有|留有|包含|收到(?:了)?|"
        r"反映|恢复正常)[^，,。！？!?；;\n\r]{0,28}"
        r"(?:钱|款项|款额|钱款|资金|现金|货款|金额|差额|价值|回款|补偿金|赔偿款)"
    ),
    re.compile(
        r"[\u4e00-\u9fff]{1,8}(?:的)?(?:原卡|支付卡|银行卡|储值卡|电子钱包|钱包|电子账户|账户|余额)"
        r"(?:里|上|内|中)?[^，,。！？!?；;\n\r]{0,28}"
        r"(?:钱|款项|款额|钱款|资金|现金|货款|金额|差额|价值|回款|补偿金|赔偿款)"
        r"[^，,。！？!?；;\n\r]{0,12}(?:多出(?:了)?|出现(?:了)?|显示|呈现|记有|留有|包含|收到(?:了)?|"
        r"反映|恢复正常)"
    ),
    re.compile(
        r"(?:钱|款项|款额|钱款|资金|现金|货款|金额|差额|价值|回款|补偿金|赔偿款)"
        r"[^，,。！？!?；;\n\r]{0,16}(?:现在|当前|刚)?"
        r"(?:显示|呈现|出现|进入|留在|记入|回到|躺在|存于|落入)"
        r"[^，,。！？!?；;\n\r]{0,16}(?:原卡|支付卡|银行卡|储值卡|电子钱包|钱包|电子账户|账户|余额)"
    ),
    # 资金完成语法本身足以构成候选，不依赖系统是否认识主语名称。通过
    # “把价值移入目标”或“向收款方补钱”的完成体识别未知商户和结算方。
    re.compile(
        r"把(?:该|这笔|您的|你的)?(?:钱|款项|资金|现金|货款|差额|价值|补偿金|赔偿款)"
        r"(?=[^，,。！？!?；;\n\r]{0,20}了)[^，,。！？!?；;\n\r]{1,20}"
        r"(?:原卡|支付卡|银行卡|钱包|账户|余额)"
    ),
    re.compile(
        r"(?:给|向)(?:买家|客户|用户|消费者|您|你)"
        r"(?=[^，,。！？!?；;\n\r]{0,16}了)[^，,。！？!?；;\n\r]{0,16}"
        r"(?:一笔|部分|全部|全额)?(?:钱|款项|资金|现金|货款|差额|价值)"
    ),
    # 兼容旧自由文本调用：可信业务主体对资金或钱包作出的自然过去完成
    # 陈述一律视为高风险。这里不枚举具体结果动词，避免同义词再次漏放。
    re.compile(
        r"(?:平台|系统|商家|卖家|店铺|店家|商户|店面|门店|支付机构|结算方|渠道方|"
        r"服务商|提供方|处理方|财务方|我们|我方)"
        r"[^，,。！？!?；;\n\r]{0,12}(?:把(?:该|这笔|您的|你的)?(?:钱|款项|资金|现金|货款|差额|价值|补偿金|赔偿款)"
        r"[^，,。！？!?；;\n\r]{1,14}了(?:原卡|支付卡|银行卡|钱包|账户|余额)?|"
        r"[\u4e00-\u9fff]{1,8}了(?:款项|钱款|资金|现金|货款|补偿金|赔偿款|钱包|账户|余额))"
    ),
    re.compile(
        r"(?:平台|系统|商家|卖家|店铺|店家|商户|店面|门店|支付机构|结算方|渠道方|"
        r"服务商|提供方|处理方|财务方|我们|我方)"
        r"[^，,。！？!?；;\n\r]{0,8}(?:给|向)(?:买家|客户|用户|消费者|您|你)"
        r"[^，,。！？!?；;\n\r]{0,12}了(?:一笔|部分|全部|全额)?(?:钱|款项|资金|现金|货款|差额|价值)"
    ),
    re.compile(
        r"(?:平台|系统|商家|卖家|支付机构|服务商|提供方|我们|我方)"
        r"(?:(?:最终|随后|接着|当前|目前|现在|这边)\s*){0,2}"
        r"(?:现已|已经|已|正在)(?!经)(?:"
        r"(?:批准|核准|同意|通过|获批|完成|成功|结清|受理)(?:了)?|"
        r"[^，,。！？!?；;\n\r]{0,18}(?:"
        r"(?:赔偿款|补偿款)(?:到账|入账)|"
        r"退款(?:申请|审批|结果|决定|款项|金额|状态|时间|流程(?!图)|单)?(?![\u4e00-\u9fff])|"
        r"退费(?:申请|结果|款项|时间)?(?![\u4e00-\u9fff])|"
        r"赔偿(?:申请|结果|款|金|金额|时间)?(?![\u4e00-\u9fff])|"
        r"补偿(?:申请|结果|款|金|金额|时间)?(?![\u4e00-\u9fff])|"
        r"申请(?![\u4e00-\u9fff])|原账户|账户|银行卡|支付卡|原卡|支付方式|"
        r"款项|钱|钱款|资金|金额|货款|余额))"
    ),
    re.compile(
        r"(?:您的|你的)?(?:退款(?=(?:现已|已经|已|正在))|退款(?:申请|审批|结果|决定|款项|金额|状态|时间|流程(?!图)|单)|"
        r"退费(?:申请|结果|款项|时间)?|赔偿(?:申请|结果|款|金额|时间)?|补偿(?:申请|结果|款|金额|时间)?|"
        r"退赔款|赔付款|返款|款项|钱款|资金|金额|货款|余额)"
        r"(?:(?:当前|目前|现在|通常)\s*)?(?:现已|已经|已|正在)(?!经)"
        r"[^，,。！？!?；;\n\r]{1,24}"
    ),
    re.compile(
        r"(?:现已|已经|已|正在)(?!经)[^，,。！？!?；;\n\r]{0,18}"
        r"(?:原账户|账户|银行卡|支付卡|原卡|支付方式|款项|钱款|资金|金额|货款|余额)"
    ),
    re.compile(r"(?:决定|结果|结论)\s*(?:是|为|显示)(?!未|不|尚|没有)[^，,。！？!?；;\n\r]{1,16}"),
    re.compile(
        r"(?:退款(?:申请|审批|结果|决定|状态|时间)|退费(?:申请|结果)?|赔偿(?:申请|结果)?|补偿(?:申请|结果)?)"
        r"[^。！？!?；;\n\r]{0,32}[，,]\s*(?:现已|已经|已)(?!经)[^，,。！？!?；;\n\r]{1,16}"
    ),
    re.compile(
        r"(?:平台|系统|商家|卖家|支付机构|服务商|提供方|我们|我方)"
        r"(?:(?:最终|随后|接着|当前|目前|现在|又)\s*)?"
        r"(?:确认|批准|核准|同意|完成|办理|处理|退回|退还|返还|打款)"
        r"[^，,。！？!?；;\n\r]{0,8}(?:退款|退费|赔偿|补偿|款项|钱款|资金|金额|成功|到账|入账)"
    ),
    re.compile(
        r"(?:平台|系统|商家|卖家|支付机构|服务商|提供方|我们|我方)"
        r"(?:(?:最终|随后|接着|当前|目前|现在|这边)\s*){0,2}"
        r"(?:现已|已经|已|正在)(?!经)把(?:该|这笔|您的|你的)?"
        r"(?:退款(?:申请|款项|金额)?|退费(?:申请|款项)?|赔偿(?:款|金|金额)?|"
        r"补偿(?:款|金|金额)?|款项|钱款|资金|金额|货款)"
        r"[^，,。！？!?；;\n\r]{1,12}"
    ),
)
ENGLISH_BUSINESS_OUTCOME_ASSERTION_PATTERNS = (
    ENGLISH_FINANCIAL_STATE_ASSERTION_PATTERN,
    ENGLISH_CAUSAL_FINANCIAL_CHANGE_PATTERN,
    # 英文资金结果同样按语义角色识别：金融目标、资金对象、结果状态和
    # 可选来源可以采用主动、被动或存在状态语序，不依赖商户名称词表。
    re.compile(
        r"\b(?:cash|credit|money|value|funds?|amount)\b.{0,36}"
        r"\b(?:appears?|shows?|sits?|rests?|remains?|is\s+(?:now\s+)?sitting|is\s+visible|"
        r"was\s+posted|was\s+credited)\b"
        r".{0,28}\b(?:wallet|account|balance|card)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:(?:the|a|an)\s+)?(?:[a-z][a-z'-]*'s\s+)?(?:wallet|account|balance|card)\b"
        r".{0,20}\b(?:appears?|includes?|shows?|reflects?|contains?|displays?|holds?|carries?|records?)\b"
        r".{0,28}\b(?:cash|credit|money|value|funds?|amount)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:buyer|customer|shopper|purchaser|recipient|cardholder|user)\b.{0,16}"
        r"\b(?:was|were|has been|have been)\s+made\s+whole\b",
        re.IGNORECASE,
    ),
    # 英文同样按“局部主语 + 已完成资金动作 + 收款目标”发现候选。主语
    # 使用受限词形而不是商户词表，避免 retailer/clearing house 等新名称漏放。
    re.compile(
        r"\b(?![^,.;!?]{0,32}\b(?:cannot|can't|could not|unable to)\b"
        r"[^,.;!?]{0,16}\b(?:confirm|verify|prove)\b)"
        r"(?!(?:that|if|unless|provided|assuming|cannot|unable|confirm|verify|prove|answer|determine)\b)"
        r"(?:the\s+)?(?:[a-z][a-z'-]*\s+){1,3}"
        r"(?:credited|posted|restored|funded|settled|issued|refunded|reimbursed|compensated|"
        r"repaid|paid|returned|transferred|wired|remitted|put)\b.{0,28}"
        r"\b(?:me|us|him|her|buyer|customer|shopper|cash|credit|money|value|funds?|wallet|account|"
        r"balance|card|[a-z][a-z'-]*'s\s+(?:wallet|account|balance|card))\b",
        re.IGNORECASE,
    ),
    # 业务主体 + 资金动作 + 收款方即为具体结果事实，不要求 refund 主题
    # 在前句重复出现；动词仍限定为资金动作，避免把“通知买家”等普通
    # 客服行为误判为资金完成。
    re.compile(
        r"\b(?:platform|seller|merchant|shop|store|vendor|storefront|marketplace|system|provider|processor|"
        r"service provider|payment handler|commerce platform|finance|we|they)\b"
        r".{0,16}\b(?:credited|posted|restored|funded|settled|issued|refunded|reimbursed|compensated|"
        r"repaid|paid|returned|transferred|wired|remitted|put)\b.{0,24}"
        r"\b(?:me|us|him|her|buyer|customer|cash|credit|money|value|funds?|wallet|account|balance|card)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:platform|seller|merchant|shop|store|vendor|storefront|marketplace|system|provider|processor|"
        r"service provider|payment handler|commerce platform|finance|we|they)\b"
        r".{0,16}\bmade\b.{0,16}\b(?:buyer|customer|account|balance|card)\b.{0,8}\bwhole\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:platform|seller|merchant|system|provider|processor|service provider|we|they)\b"
        r".{0,16}\bsent\b.{0,10}\b(?:cash|money|funds?|amount)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:platform|seller|merchant|system|provider|processor|we|they)\b.{0,12}"
        r"\b(?:has|have|had)\s+(?!not\b|never\b)(?:(?:already|just)\s+)?(?:been\s+)?"
        r"(?:[a-z]+(?:-[a-z]+)?(?:ed|en)|[a-z]+-[a-z]+|sent|paid|repaid|made|done)\b.{0,20}"
        r"\b(?:(?:it|this|that|yours)(?:\s+back)?|(?:the|your)\s+(?:money|funds?|amount|balance|"
        r"account|card|request|(?:refund|reimbursement|compensation)"
        r"(?:\s+(?:request|application|payment))?)\b(?!\s+[a-z]))"
    ),
    re.compile(
        r"\b(?:platform|seller|merchant|system|provider|processor|we|they)\b\s+"
        r"(?:[a-z]+(?:-[a-z]+)?ed|[a-z]+-[a-z]+|sent|paid|repaid|made)\s+"
        r"(?:(?:it|this|that|yours)(?:\s+back)?|(?:the|your)\s+(?:money|funds?|amount|balance|"
        r"account|card|request|(?:refund|reimbursement|compensation)"
        r"(?:\s+(?:request|application|payment))?)\b(?!\s+[a-z]))"
    ),
    re.compile(
        r"\b(?:your\s+)?(?:(?:refund|reimbursement|compensation)"
        r"(?=\s+(?:(?:usually|already|just)\s+)?(?:has|have|is|was|are|were)\b)|"
        r"refund\s+(?:request|application|approval|decision|outcome|result|status|payment|process)|"
        r"reimbursement\s+(?:request|application|approval|decision|outcome|result|status|payment|process)|"
        r"compensation\s+(?:request|application|approval|decision|outcome|result|status|payment|process)|"
        r"money|funds?|amount|balance)\b.{0,12}\b(?:has|have|is|was|are|were)\b\s+"
        r"(?!not\b|never\b).{0,12}\b(?:[a-z]+(?:-[a-z]+)?(?:ed|en)|complete|successful|pending)\b"
    ),
    re.compile(
        r"\b(?:outcome|decision|result|conclusion)\b.{0,10}\b(?:is|was|has been)\b\s+"
        r"(?!not\b|never\b).{0,8}\b(?:[a-z]+(?:-[a-z]+)?(?:ed|en)|complete|successful)\b"
    ),
)
CHINESE_NON_BUSINESS_REFUND_PATTERN = re.compile(
    r"(?:退款|退费|赔偿|补偿)(?!(?:申请|审批|结果|决定|款项|金额|状态|单|成功|到账))"
    r"(?:[a-z]+|[\u4e00-\u9fff]{1,12})(?:现已|已经|已|正在)"
)
CHINESE_ACTOR_NON_BUSINESS_REFUND_PATTERN = re.compile(
    r"(?:平台|系统|商家|卖家|支付机构|服务商|提供方|我们|我方)"
    r"(?:(?:最终|随后|接着|当前|目前|现在|这边)\s*){0,2}(?:现已|已经|已|正在)(?!经)"
    r"[^，,。！？!?；;\n\r]{1,18}(?:退款|退费|赔偿|补偿)"
    r"(?!(?:申请|审批|结果|决定|款项|款|金|金额|状态|时间|流程(?!图)|单|成功|到账))"
    r"(?:[a-z]+|[\u4e00-\u9fff]{1,12})"
)
ENGLISH_NON_BUSINESS_REFUND_PATTERN = re.compile(
    r"\b(?:refund|reimbursement|compensation)\s+"
    r"(?!(?:request|application|approval|decision|outcome|result|status|payment|process|money|funds?|amount)\b)"
    r"[a-z][a-z-]*\s+(?:has|have|had|is|are|was|were)\b"
)
ENGLISH_ACTOR_NON_BUSINESS_REFUND_PATTERN = re.compile(
    r"\b(?:platform|seller|merchant|system|provider|processor|we|they)\b.{0,12}"
    r"\b(?:has|have|had|is|are|was|were)\b.{0,16}"
    r"\b(?:the\s+|your\s+)?(?:refund|reimbursement|compensation)\s+"
    r"(?!(?:request|application|approval|decision|outcome|result|status|payment|process|money|funds?|amount)\b)"
    r"[a-z][a-z-]*\b"
)
# 页面、表单、字段、模板和说明文档的技术状态不是退款审批或资金事实。
# 该兼容判断按对象类型收口，不把“已加载/已保存”等结果词本身当授权依据。
CHINESE_NON_BUSINESS_ARTIFACT_PATTERN = re.compile(
    r"(?:退款|退费|赔偿|补偿|赔付|退赔|返款)(?:申请|审批|状态|金额|结果|流程)?"
    r"(?:faq(?:术语表)?|[a-zA-Z\u4e00-\u9fff]{1,12})"
    r"[^，,。！？!?；;\n\r]{0,8}(?:现已|已|已经|正在|刚(?:刚)?|完成(?:了)?|通过(?:了)?)?"
    r"(?:下载|上线|刷新|校验|保存|发布|导出|加载|更新|升级|生成|翻译|归档|审校|校对|校订|改版|"
    r"复核|同步|查阅|启用|禁用|隐藏|渲染|部署)(?:完成|完毕|通过)?"
)
CHINESE_TYPED_REFUND_ARTIFACT_PATTERN = re.compile(
    r"(?:退款|退费|赔偿|补偿|赔付|退赔|返款)(?:审批|申请|支付)?"
    r"(?:\s*[a-z0-9-]+)?\s*"
    r"(?:[a-z0-9_-]+\s*定义|(?:审计|接口|数据|展示)?字段(?:映射表|目录)?|接口契约|openapi\s*描述(?:文件)?|"
    r"事件说明书|graphql\s*类型|grpc\s*服务描述|kafka\s*消费者组名|"
    r"消息(?:队列)?(?:主题|路由键)|监控(?:指标|度量)|sdk\s*(?:调用)?片段|"
    r"json\s*样例|数据库(?:物化)?视图|状态机图|"
    r"术语索引|知识图谱|状态枚举|数据字典|规则索引|查询表|分类法|模式定义|事件模式|接口模式|"
    r"元数据|测试夹具|测试数据|测试值|本地化标记|标签)"
)
ENGLISH_NON_BUSINESS_ARTIFACT_PATTERN = re.compile(
    r"\b(?:refund|reimbursement|compensation)(?:\s+(?:request|approval|payment|status|process|decision|amount))?\s+"
    r"(?:[a-z][a-z-]*\s+){0,3}[a-z][a-z-]*\b.{0,16}"
    r"(?:\b(?:has|have|had|is|are|was|were)(?:\s+been)?\s+"
    r"(?:loaded|changed|revised|rendered|exported|saved|validated|loading|updated|published|archived|online|"
    r"translated|reviewed|deployed|versioned|synchronized)\b|\bwent\s+live\b|\bpassed\s+editorial\s+review\b|"
    r"\bcompleted\s+translation\s+review\b|\bwas\s+archived\s+after\s+review\b)",
    re.IGNORECASE,
)
ENGLISH_TYPED_REFUND_ARTIFACT_PATTERN = re.compile(
    r"\b(?:refund|reimbursement|compensation)(?:-[a-z]+)?\s+"
    r"(?:(?:protobuf|avro|json|api|event|payload)\s+definition|field\s+catalog|openapi\s+description|"
    r"event\s+(?:descriptor|specification|topic)|graphql\s+type|webhook\s+contract|"
    r"(?:message\s+)?queue\s+routing\s+key|"
    r"monitoring\s+metric|sdk\s+(?:call\s+)?snippet|(?:database\s+)?materialized\s+view|"
    r"database\s+view|state-machine\s+diagram|"
    r"rule\s+index|lookup\s+table|api\s+contract|taxonomy|data\s+dictionary|knowledge\s+graph|"
    r"(?:event|api|payload|response)?\s*schema|metadata|test\s+fixture|test\s+data|ui\s+test\s+value|"
    r"localization\s+test\s+token|label|badge)\b",
    re.IGNORECASE,
)
# 技术资产是“对象 + 技术用途/治理关系”，而不是若干固定产品名。开放集
# 可以把 OpenAPI 换成 Avro、把路由键换成分区键；只要对象明确服务于
# 注册、配置、治理、监控、代码生成或报表任务，就不构成客户退款事实。
CHINESE_TECHNICAL_RELATION_PATTERN = re.compile(
    r"(?:退款|退费|赔偿|补偿|返款|赔付)[^，,。！？!?；;\n\r]{0,32}"
    r"(?:本体|记录|指标|键|类型|声明|图|视图|描述|协议|模式|字段|事件|接口|端点|工件|资产)"
    r"[^，,。！？!?；;\n\r]{0,32}"
    r"(?:目录|注册|仓库|文档|治理|配置|面板|告警|监控|客户端|代码|测试|集成|报表|任务|消息|开发|运维)"
)
ENGLISH_TECHNICAL_RELATION_PATTERN = re.compile(
    r"\b(?:refund|reimbursement|compensation)\b[^,.;!?\n\r]{0,72}"
    r"\b(?:ontology|record|metric|gauge|key|declaration|graph|descriptor|schema|catalog|type|view|"
    r"specification|contract|field|event|model|diagram|fixture|token|badge|page|guide|documentation)\b"
    r"[^,.;!?\n\r]{0,96}"
    r"\b(?:governance|catalog|registry|schema|documentation|dashboard|configuration|client-code|"
    r"reporting|jobs?|integration|developer|monitoring|repository|code\s+generation|alerting|messaging)\b",
    re.IGNORECASE,
)
# 引用、示例和占位文案描述的是文本资产，不是当前客户的退款事实。必须
# 同时出现元文本对象与示例/占位关系；单纯给危险事实加引号不能获得放行。
CHINESE_META_TEXT_PATTERN = re.compile(
    r"[‘'\"“][^，,。！？!?；;\n\r]{0,48}[’'\"”]"
    r"[^，,。！？!?；;\n\r]{0,16}(?:(?:只是|仅是|仅为|属于)"
    r"[^，,。！？!?；;\n\r]{0,12}(?:示例|样例|占位|字段|标签|文案|术语)|"
    r"(?:是|属于)(?:回归|单元|集成|ui)?测试(?:夹具|数据|值|文本))"
)
ENGLISH_META_TEXT_PATTERN = re.compile(
    r"(?:\b(?:phrase|wording|text)\b.{0,40}\b(?:is|was)\b.{0,12}\b(?:sample|example|placeholder)\b|"
    r"[\"'][^\"']{0,40}[\"']\s+(?:label|field|text|copy)\b.{0,16}"
    r"\b(?:sample|example|placeholder)\b|"
    r"[\"'][^\"']{0,72}[\"']\s+is\s+(?:a\s+)?"
    r"(?:regression[- ]fixture|test[- ]fixture|synthetic\s+test|acceptance[- ]corpus)\s+text\b)",
    re.IGNORECASE,
)
CHINESE_HISTORICAL_EXAMPLE_PATTERN = re.compile(
    r"(?:历史|过往|以往|此前)(?:案例|示例|记录|工单|订单)?[^，,。！？!?；;\n\r]{0,20}(?:曾|曾经|一度|过去)"
)
ENGLISH_HISTORICAL_EXAMPLE_PATTERN = re.compile(
    r"\b(?:a\s+)?(?:previous|historical|past|earlier)\s+(?:case|example|record|ticket|order)\b",
    re.IGNORECASE,
)
CHINESE_CURRENT_INSTANCE_PATTERN = re.compile(
    r"(?:本订单|本次(?:申请|退款|请求)?|当前(?:订单|申请|退款|请求)|这笔(?:订单|申请|退款|款项)?|"
    r"您的(?:订单|申请|退款|款项)|你的(?:订单|申请|退款|款项)|"
    r"(?:并且|而且|而)(?:平台|系统|商家|卖家|我们|我方))"
)
ENGLISH_CURRENT_INSTANCE_PATTERN = re.compile(
    r"\b(?:this|current|your)\s+(?:order|request|application|refund|reimbursement|compensation|payment|funds?)\b|"
    r"\band\s+(?:the\s+)?(?:platform|seller|merchant|system|we)\b",
    re.IGNORECASE,
)
STRONG_BOUNDARY_PATTERN = re.compile(r"[。！？!?；;\n\r]")


class RefundFactPolicy:
    """按命题结构区分无依据退款事实与合法政策或否定语境。

    当前没有能证明退款执行、审批或到账状态的白名单工具，因此具体客户
    事实失败关闭。安全放行规则必须同时约束业务对象和语义关系，单独出现
    “查询、申请、通常、时间”等词不会成为整段通行证。
    """

    def contains_unsupported_fact(self, answer: str) -> bool:
        """判断回答是否包含没有可信来源的退款执行或状态事实。

        Args:
            answer: 已完成结构化解析、尚未发送的客服回复草稿。

        Returns:
            True 表示存在具体退款事实，必须转人工；False 表示本规则未命中。
        """
        normalized = self._normalize(answer)
        has_refund_context = bool(
            CHINESE_REFUND_TOPIC_PATTERN.search(normalized) or ENGLISH_REFUND_TOPIC_PATTERN.search(normalized)
        )
        # 明确的资金审批、执行或到账候选本身已经构成退款/赔偿语境，不能
        # 要求前句再次出现 refund 主题，否则“merchant credited buyer”会
        # 因省略重复宾语而漏过确定性门禁。
        if self._contains_asserted_outcome(normalized):
            return True
        return any(
            self._contains_unsupported_clause(clause, has_refund_context=has_refund_context)
            for clause in self._clauses(normalized)
        )

    def _contains_asserted_outcome(self, answer: str) -> bool:
        """统一扫描结果候选，并对每个候选执行局部语义作用域检查。

        旧实现把少量“硬结果词”直接判为事实，其余结果再检查否定作用域，
        造成同义词漏放和合法否定误杀同时存在。现在所有候选只走这一条
        路径；动作词可以变化，否定、条件和警示的控制关系不能被跳过。
        """
        for pattern in CHINESE_BUSINESS_OUTCOME_ASSERTION_PATTERNS:
            for match in pattern.finditer(answer):
                if self._is_candidate_non_business_artifact(answer, match):
                    continue
                if not self._is_chinese_scoped_nonassertion(answer, match):
                    return True
        for pattern in ENGLISH_BUSINESS_OUTCOME_ASSERTION_PATTERNS:
            for match in pattern.finditer(answer):
                if self._is_candidate_non_business_artifact(answer, match):
                    continue
                if not self._is_english_scoped_nonassertion(answer, match):
                    return True
        return False

    def _contains_only_scoped_outcomes(self, clause: str) -> bool:
        """判断命题中的全部已识别结果是否都受否定、条件或引用控制。

        旧实现先正确识别了局部否定，随后又让宽松的 clause fallback 对同一
        命题重新判定，形成双重且互相矛盾的决策路径。这里把两条路径收口。
        """
        found_outcome = False
        for pattern in CHINESE_BUSINESS_OUTCOME_ASSERTION_PATTERNS:
            for match in pattern.finditer(clause):
                if self._is_candidate_non_business_artifact(clause, match):
                    continue
                found_outcome = True
                if not self._is_chinese_scoped_nonassertion(clause, match):
                    return False
        for pattern in ENGLISH_BUSINESS_OUTCOME_ASSERTION_PATTERNS:
            for match in pattern.finditer(clause):
                if self._is_candidate_non_business_artifact(clause, match):
                    continue
                found_outcome = True
                if not self._is_english_scoped_nonassertion(clause, match):
                    return False
        return found_outcome

    @staticmethod
    def _is_non_business_artifact(proposition: str) -> bool:
        """识别退款主题下的技术资产状态以及明确的示例或占位文本。"""
        return bool(
            CHINESE_NON_BUSINESS_ARTIFACT_PATTERN.search(proposition)
            or CHINESE_TYPED_REFUND_ARTIFACT_PATTERN.search(proposition)
            or CHINESE_TECHNICAL_RELATION_PATTERN.search(proposition)
            or ENGLISH_NON_BUSINESS_ARTIFACT_PATTERN.search(proposition)
            or ENGLISH_TYPED_REFUND_ARTIFACT_PATTERN.search(proposition)
            or ENGLISH_TECHNICAL_RELATION_PATTERN.search(proposition)
            or CHINESE_META_TEXT_PATTERN.search(proposition)
            or ENGLISH_META_TEXT_PATTERN.search(proposition)
        )

    @classmethod
    def _is_candidate_non_business_artifact(cls, answer: str, assertion: re.Match[str]) -> bool:
        """仅当技术资产或引用范围与当前结果候选重叠时才放行。

        未知连接词不能作为安全边界。与其枚举所有“况且/moreover”，这里
        直接比较候选和技术资产的字符区间：前句文档状态与后句资金结果不
        重叠，因此后者仍会失败关闭；同一引用或示例中的候选则可以放行。
        """
        start, end = cls._proposition_bounds(answer, assertion.start(), assertion.end())
        proposition = answer[start:end]
        candidate_start = assertion.start() - start
        candidate_end = assertion.end() - start
        # 技术资产模式已限定为“对象 + 明确编辑/页面状态”，可按区间重叠
        # 关联候选；它不会跨过未知连接词吞掉后句资金事实。
        return any(
            artifact.start() < candidate_end and candidate_start < artifact.end()
            for pattern in (
                CHINESE_NON_BUSINESS_ARTIFACT_PATTERN,
                CHINESE_TYPED_REFUND_ARTIFACT_PATTERN,
                CHINESE_TECHNICAL_RELATION_PATTERN,
                ENGLISH_NON_BUSINESS_ARTIFACT_PATTERN,
                ENGLISH_TYPED_REFUND_ARTIFACT_PATTERN,
                ENGLISH_TECHNICAL_RELATION_PATTERN,
                CHINESE_META_TEXT_PATTERN,
                ENGLISH_META_TEXT_PATTERN,
            )
            for artifact in pattern.finditer(proposition)
        )

    def _is_chinese_scoped_nonassertion(self, answer: str, assertion: re.Match[str]) -> bool:
        """只允许方向明确、与候选紧邻的中文否定或引述控制。

        不能再用“同一字符串出现过无法确认”作为通行证；控制词到业务
        候选之间只允许退款对象、可信业务主体等语法性成分，出现“况且”
        一类新话语关系时自然无法通过，而无需枚举全部连接词。
        """
        prefix, candidate, suffix, proposition = self._assertion_context(answer, assertion)
        full_suffix = answer[assertion.end() :]
        if self._matches_any(proposition, CHINESE_PROPOSITION_NON_ASSERTIVE_PATTERNS):
            return True
        if re.match(
            r"^[^。！？!?；;\n\r]{0,4}[，,]\s*(?:只是|仅是|不过是).{0,16}"
            r"(?:尚未|未经|未获)?(?:验证|核验)?(?:的)?(?:假说|推测|猜测)",
            full_suffix,
        ):
            # 中文后置评价常用逗号把“所谓完成事实”与“只是待验证假说”分开。
            # 逗号仍是普通候选的局部边界，只对这个紧邻控制结构向后查看，
            # 避免后续独立资金事实借前句获得放行。
            return True
        if re.match(r"^(?:是否|能否)", proposition):
            # 疑问命题只询问事实是否成立；即使控制答复位于逗号后的相邻
            # 分句，当前候选本身也不是肯定的完成声明。
            return True
        historical_context = CHINESE_HISTORICAL_EXAMPLE_PATTERN.search(prefix)
        if historical_context and len(prefix[historical_context.end() :].strip()) <= 3:
            return True
        if re.search(
            r"(?:平台|系统|商家|卖家|支付机构)?(?:尚未|未|没有)"
            r"(?:确认|认定|判定)(?:任何)?(?:(?:该|这笔|您的|你的)?)\s*$",
            prefix,
        ):
            return True
        if re.search(
            r"(?:不要|请勿|勿|别)(?:把|将)[^，,。！？!?；;\n\r]{0,40}"
            r"(?:退款|退费|赔偿|补偿)[^，,。！？!?；;\n\r]{0,24}"
            r"(?:当作|视为|理解成|理解为)(?:事实|证明|依据)?",
            proposition,
        ):
            return True
        if re.search(r"(?:请勿|不要|勿|别).{0,16}(?:相信|采信)", prefix) and re.search(
            r"(?:的)?(?:提示|消息|通知|说法)\s*$", suffix or proposition
        ):
            return True
        controlled_prefix = re.compile(
            r"(?:(?:无法|不能|未能)(?:直接)?(?:确认|证实|证明|说明|断定)"
            r"(?:(?:该|这笔|您的|你的)?(?:退款|退费|赔偿|补偿|款项)?"
            r"(?:平台|系统|商家|卖家|支付机构|服务商|提供方|我们|我方)?(?:的)?)?|"
            r"(?:不能|尚不能|尚不足以|不足以|不宜|没有理由)(?:据此|由.{0,8})?"
            r"(?:认定|断言|推断|推出|推导出)|"
            r"(?:现有|这份|该)?(?:信息|资料|材料|记录|截图|证据)(?:尚)?"
            r"(?:不能|无法|不足以|不够|推不出)(?:支持|支撑|证明|表明|显示|认定|判断|推出|说)?|"
            r"(?:没有|无)(?:任何|足够|充分)?(?:信息|资料|材料|记录|证据|依据)"
            r"(?:可|足以)?(?:支持|证明|表明|显示|认定)|"
            r"(?:没有|无)(?:任何|足够|充分)?(?:依据|理由)(?:可|足以)?(?:断定|认定|推断))"
            r"(?:该|这笔|您的|你的|平台|系统|商家|卖家|店铺|店家|商户|支付机构|结算方|渠道方)?\s*$"
        )
        evidence_prefix = re.compile(
            r"(?:没有|尚无|无)(?:任何|足够|相关)?(?:证据|依据|确认|定论)"
            r"(?:能够|可以)?(?:表明|证明|说明)?\s*$"
        )
        denial_prefix = re.compile(r"(?:不|并不|并非).{0,8}(?:表示|代表|意味着|等于|保证)\s*$")
        if any(pattern.search(prefix) for pattern in (controlled_prefix, evidence_prefix, denial_prefix)):
            return True
        if re.search(
            r"(?:不要|请勿|勿|别|切勿)(?:把|将)[^，,。！？!?；;\n\r]{0,24}"
            r"(?:当作|视为|理解成|理解为|解读为)\s*$",
            prefix,
        ):
            return True
        if re.search(r"(?:不要|请勿|勿|别|切勿)(?:把|将)[^，,。！？!?；;\n\r]{0,8}[‘'“\"]?\s*$", prefix) and re.match(
            r"[’'”\"]?(?:当作|视为|理解成|理解为|解读为)(?:事实|证明|依据|官方结论)?", suffix
        ):
            return True
        if re.search(r"(?:若|如果|只有|除非|一旦|假如|倘若|要是)\s*$", prefix) and re.search(
            r"^[^。！？!?；;\n\r]{0,4}[，,]?[^。！？!?；;\n\r]{0,12}(?:才|方|可能|会)",
            answer[assertion.end() :],
        ):
            return True
        if re.search(r"待\s*$", prefix) and re.match(r"后", suffix):
            return True
        if re.match(r"^(?:的)?(?:说法|结论|结果).{0,8}(?:仍)?(?:未经核实|未获证实|没有得到证实)", suffix):
            return True
        return bool(re.search(r"(?:未必|不一定|可能|也许|或许)\s*$", prefix) and candidate)

    def _is_english_scoped_nonassertion(self, answer: str, assertion: re.Match[str]) -> bool:
        """只允许直接补语、条件或明确引用警示控制英文结果候选。"""
        prefix, _, suffix, proposition = self._assertion_context(answer, assertion)
        if self._matches_any(proposition, ENGLISH_PROPOSITION_NON_ASSERTIVE_PATTERNS):
            return True
        historical_context = ENGLISH_HISTORICAL_EXAMPLE_PATTERN.search(prefix)
        if historical_context and len(prefix[historical_context.end() :].strip()) <= 12:
            return True
        warning = re.search(
            r"\b(?:do not|don't|should not|must not)\s+(?:trust|believe)\s+"
            r"(?:(?:a|the)\s+)?(?:notice|message|claim)s?\s+(?:saying|claiming|that)\s+"
            r"(?:(?:the|your)\s+)?$",
            prefix,
        )
        if warning:
            return True
        controller = re.search(
            r"\b(?:cannot|can't|could not|unable to)\s+(?:confirm|verify|prove)\s+"
            r"(?:that\s+)?(?:(?:the|your)\s+)?$|"
            r"\b(?:cannot|can't|could not|unable to)\s+(?:determine|tell|conclude)\s+whether\s+"
            r"(?:(?:the|your)\s+)?$|"
            r"\b(?:there is|there's|we have|there are)?\s*no\s+"
            r"(?:confirmation|evidence|proof)\s+(?:that\s+)?(?:(?:the|your)\s+)?$|"
            r"\b(?:the\s+)?(?:message|notice|page|content)\s+(?:does|do|did)\s+not\s+"
            r"(?:prove|mean|represent|guarantee)\s+(?:that\s+)?(?:(?:the|your)\s+)?$|"
            r"\bno\s+$|"
            r"\b(?:we\s+)?lack\s+grounds\s+to\s+conclude\s+that\s+(?:(?:the|your)\s+)?$|"
            r"\bit\s+would\s+be\s+wrong\s+to\s+infer\s+that\s+(?:(?:the|your)\s+)?$|"
            r"\b(?:the\s+)?record\s+is\s+insufficient\s+to\s+establish\s+that\s+"
            r"(?:(?:the|your)\s+)?$|"
            r"\bnothing\s+here\s+demonstrates\s+that\s+(?:(?:the|your)\s+)?$|"
            r"\b(?:the\s+)?notice\s+cannot\s+substantiate\s+that\s+(?:(?:the|your)\s+)?$|"
            r"\b(?:the\s+)?(?:available\s+)?(?:evidence|record|information|materials?|screenshot)\s+"
            r"(?:is\s+)?(?:insufficient|unable)\s+to\s+(?:show|prove|establish|support)\s+that\s+"
            r"(?:(?:the|your)\s+)?$|"
            r"\b(?:this|the)\s+(?:record|screenshot)\s+cannot\s+(?:show|prove|establish|support)\s+that\s+"
            r"(?:(?:the|your)\s+)?(?:(?:refund|reimbursement|compensation)\s+"
            r"(?:payment|request|application|decision|amount)\s+)?$|"
            r"\b(?:we\s+have\s+)?no\s+(?:basis|grounds?|evidence)\s+to\s+conclude\s+"
            r"(?:(?:that\s+)?(?:the|your)\s+)?$|"
            r"\bnothing\s+(?:in|from)\s+(?:the\s+)?(?:record|screenshot|evidence)\s+"
            r"(?:proves?|shows?|establishes?|supports?)\s+that\s+(?:(?:the|your)\s+)?$|"
            r"\b(?:the\s+)?(?:record|evidence|information)\s+"
            r"(?:does\s+not\s+warrant\s+concluding|falls\s+short\s+of\s+establishing)\s+that\s+"
            r"(?:(?:the|your)\s+)?$|"
            r"\bit\s+remains\s+unproven\s+that\s+(?:(?:the|your)\s+)?$|"
            r"\bno\s+[^,.;!?]{0,24}\b(?:can\s+)?(?:answer|determine|say|tell)\s+whether\s+"
            r"(?:(?:the|your)\s+)?$|"
            r"\bno\s+(?:(?:refund|reimbursement|compensation)\s+)?$",
            prefix,
        )
        if controller:
            return True
        full_suffix = answer[assertion.end() :]
        if re.search(r"\b(?:the\s+)?phrase\s+['\"]?\s*$", prefix) and re.match(
            r"['\"]?\s+is\s+an\s+example,?\s+not\s+(?:a\s+)?status\s+confirmation",
            full_suffix,
        ):
            return True
        if re.search(r"\b(?:if|unless|provided|assuming)\s+(?:(?:a|an|the|your)\s+)?$", prefix):
            return True
        return bool(re.search(r"\bonly (?:if|after)\b", suffix or proposition))

    @classmethod
    def _assertion_context(cls, answer: str, assertion: re.Match[str]) -> tuple[str, str, str, str]:
        """返回候选所在标点命题及候选前后片段，保留作用域方向。"""
        start, end = cls._proposition_bounds(answer, assertion.start(), assertion.end())
        return (
            answer[start : assertion.start()],
            assertion.group(0),
            answer[assertion.end() : end],
            answer[start:end],
        )

    @staticmethod
    def _proposition_bounds(answer: str, assertion_start: int, assertion_end: int) -> tuple[int, int]:
        """逗号和强标点限定局部命题；安全判断不再依赖连接词词表。"""
        start = 0
        for prior_boundary in STRONG_BOUNDARY_PATTERN.finditer(answer, 0, assertion_start):
            start = prior_boundary.end()
        comma_start = max(answer.rfind(",", start, assertion_start), answer.rfind("，", start, assertion_start))
        if comma_start >= 0:
            start = comma_start + 1
        next_boundary = STRONG_BOUNDARY_PATTERN.search(answer, assertion_end)
        end = next_boundary.start() if next_boundary else len(answer)
        comma_positions = [
            position
            for position in (
                answer.find(",", assertion_end, end),
                answer.find("，", assertion_end, end),
            )
            if position >= 0
        ]
        if comma_positions:
            end = min(comma_positions)
        return start, end

    @staticmethod
    def _normalize(answer: str) -> str:
        """统一全半角、英文大小写和空白，降低表面字符差异的影响。"""
        normalized = unicodedata.normalize("NFKC", answer).lower()
        return WHITESPACE_PATTERN.sub(" ", normalized).strip()

    @staticmethod
    def _clauses(answer: str) -> list[str]:
        """按句末、转折和前置让步划分独立命题。"""
        clauses: list[str] = []
        for segment in SEMANTIC_SPLIT_PATTERN.split(answer):
            segment = segment.strip()
            if not segment:
                continue
            if CONCESSIVE_PREFIX_PATTERN.match(segment) and ("," in segment or "，" in segment):
                boundary = min(position for position in (segment.find(","), segment.find("，")) if position >= 0)
                clauses.extend(part.strip() for part in (segment[:boundary], segment[boundary + 1 :]) if part.strip())
            elif CONCESSIVE_PREFIX_PATTERN.match(segment) and (
                continuation := CONCESSIVE_CONTINUATION_PATTERN.search(segment)
            ):
                # “虽然无法确认退款仍已到账”没有标点，但让步前后是相互独立的
                # 命题；继续合并会让前置否定成为整句安全通行证。
                clauses.extend(
                    part.strip()
                    for part in (segment[: continuation.start()], segment[continuation.end() :])
                    if part.strip()
                )
            else:
                clauses.append(segment)
        return clauses

    @staticmethod
    def _matches_any(clause: str, patterns: tuple[re.Pattern[str], ...]) -> bool:
        """判断单个命题是否匹配任一结构化安全语境。"""
        return any(pattern.search(clause) for pattern in patterns)

    def _contains_unsupported_clause(self, clause: str, *, has_refund_context: bool) -> bool:
        """仅放行与退款主题存在明确结构关系的非事实命题。"""
        if self._is_non_business_artifact(clause):
            return False
        # 明确标记为历史案例的命题不描述当前客户状态；后续当前命题仍按
        # 独立分句继续检查，不能借历史前句掩盖当下事实。
        chinese_history_only = CHINESE_HISTORICAL_EXAMPLE_PATTERN.search(
            clause
        ) and not CHINESE_CURRENT_INSTANCE_PATTERN.search(clause)
        english_history_only = ENGLISH_HISTORICAL_EXAMPLE_PATTERN.search(
            clause
        ) and not ENGLISH_CURRENT_INSTANCE_PATTERN.search(clause)
        if chinese_history_only or english_history_only:
            return False
        if self._contains_only_scoped_outcomes(clause):
            return False
        if ENGLISH_REFUND_TOPIC_PATTERN.search(clause):
            if ENGLISH_NON_BUSINESS_REFUND_PATTERN.search(clause) or ENGLISH_ACTOR_NON_BUSINESS_REFUND_PATTERN.search(
                clause
            ):
                return False
            if self._matches_any(clause, ENGLISH_NON_ASSERTIVE_PATTERNS) or self._matches_any(
                clause, ENGLISH_PROPOSITION_NON_ASSERTIVE_PATTERNS
            ):
                return False
            if has_refund_context and ENGLISH_REFERENTIAL_FACT_PATTERN.search(clause):
                return True
            return not self._matches_any(clause, ENGLISH_POLICY_PATTERNS)
        if has_refund_context and ENGLISH_REFERENTIAL_FACT_PATTERN.search(clause):
            return True

        if CHINESE_REFUND_TOPIC_PATTERN.search(clause) is None:
            return bool(has_refund_context and CHINESE_CONTEXTUAL_FACT_PATTERN.search(clause))
        if CHINESE_NON_BUSINESS_REFUND_PATTERN.search(clause) or CHINESE_ACTOR_NON_BUSINESS_REFUND_PATTERN.search(
            clause
        ):
            return False
        if self._matches_any(clause, CHINESE_NON_ASSERTIVE_PATTERNS) or self._matches_any(
            clause, CHINESE_PROPOSITION_NON_ASSERTIVE_PATTERNS
        ):
            return False

        # 政策、责任或申请语境后仍可能追加“审核已通过、补偿款已到账”等
        # 客户事实；事实优先于政策放行，避免安全前缀掩盖实际承诺。
        if CHINESE_CONTEXTUAL_FACT_PATTERN.search(clause):
            return True

        # “可以为您退款”不是一般能力说明，而是面向当前客户的执行承诺，
        # 必须先于政策模式阻断。
        if CHINESE_DIRECT_RECIPIENT_ACTION_PATTERN.search(clause):
            return True
        return not self._matches_any(clause, CHINESE_POLICY_PATTERNS)
