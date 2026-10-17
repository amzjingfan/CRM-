# AI、RAG 与工具契约

## Provider 与输入边界

应用通过 Provider 抽象接入模型。DeepSeek Provider 只接收版本化系统指令、固定业务字段、经过 DLP 的用户输入、已审批知识摘要和符合 `TOOL_OUTPUT_SCHEMAS` 的工具结果。未知字段、地址细节、凭证、跨店铺标识和任意 Prompt 配置一律丢弃或拒绝。

FAQ 回答 Prompt 中的知识来源标签也使用现有 DLP 脱敏函数。来源标签只帮助模型区分证据，不能携带未脱敏的业务标识；答案正文仍按现有位置文本、敏感信息与注册业务载荷规则检查。G5 的隔离 FAQ 版本 3 仅调整合成测试答案的句子分隔，不改变 DLP 策略、知识审批或公开发送边界。

模型返回结构化信封；DeepSeek FAQ 草稿使用 Responses JSON Schema，其余现有场景使用 Chat Completions JSON Output。两条路径的枚举、长度、引用和安全状态都必须经本地 Pydantic 与业务安全校验才可进入应用。错误、超时、协议漂移或 DLP 不确定时失败关闭并转人工，不透传第三方响应正文。

完整 Agent 工作流遇到 `LLM_OUTPUT_INVALID` 时，运行记录沿用现有 `output_summary`，仅追加固定模型节点（分类、FAQ/工具草稿、安全复核或翻译）及 Provider 已分类的 `unfinished`、`empty`、`invalid_structure`、`invalid_json`、`invalid_schema`。仅在 `invalid_schema` 时，Provider 已映射的 Schema 字段路径与 Pydantic 错误类型可写入最多八组；记录端口再次按固定白名单校验、去重和截断。其他失败类别不写 Schema 明细。缺失或不在白名单的诊断字段不写入；Prompt、模型正文、字段值、原始异常和请求 ID 不持久化。诊断只用于定位失败，公开错误码、失败关闭、DLP、评分、调用次数及发送开关不因此改变。

G5 R53 的受控单会话在 FAQ 草稿处记录 `business_claims:model_type` 与 `unknown:missing`，没有保存模型正文，后者不能倒推出具体字段。FAQ 生成 Prompt `faq-answer-v1.6.1` 明列 `FaqAnswerModelOutput` 的全部必需顶层字段，以及 `business_claims={complete:true, claims:[...]}` 的对象结构；无业务命题时 `claims=[]`，有业务命题时仍须完整列出。低敏 Schema 路径白名单仅新增 `answer`、`citation_chunk_ids`、`grounding_confidence`、`answer_language`、`needs_human`，不记录模型字段值。注册摘要同步更新；严格 Schema、DLP、评分、调用次数及 TikTok 发送边界未改变。确定性测试不能证明新 Prompt 的真实模型输出或 G5 单会话通过。

G5 R56 的受控单会话通过 FAQ 草稿，但安全复核返回 `invalid_schema / unknown:missing`，低敏证据不能还原具体缺失字段。`faq-grounding-review-v1.5.1` 明列 `GroundingReviewOutput` 的五个顶层字段及布尔、数字、字符串数组类型；运行失败摘要只允许记录新增白名单路径 `is_safe`、`is_grounded`、`business_claims_consistent`、`confidence`、`reason_codes` 和既有固定错误类型。注册正文哈希已同步，工作流版本为 `faq-agent-workflow-v1.7.1`。这只改输出指令与诊断名称，严格 Schema、DLP、安全判分、最多调用次数和 TikTok 开关不变；本地确定性测试不能证明现场会产生安全 `delta`。

G5 R58 的 FAQ 草稿再次返回 `business_claims:missing,other,extra_forbidden`，说明提示文字与 JSON Output 未稳定满足业务结构。R59 候选仅将已注册 FAQ 草稿请求改为 DeepSeek Responses 的完整 `FaqAnswerModelOutput` JSON Schema；模型仍不能决定业务放行，应用仍逐项执行 Pydantic、证据、DLP 与独立安全复核。其他模型场景和调用次数不变。一次合成接口探针验证当前 staging 模型接受完整 Schema 并返回必需字段（HTTP 200，约 1.65 秒），不能替代真实 FAQ 安全 `delta`、延迟或 50 并发验收。

R60 真实单会话说明 JSON Schema 约束了字段形状，但 `business_claims` 仍被本地业务语义校验以泛化 `value_error` 拒绝。当前低敏记录不能确认具体不变量；服务已恢复 G3 模式，G5 保持 No-Go。后续诊断只能输出固定不变量类别，不保存声明值或模型正文，严格校验不能放宽。

R61 将业务声明的五条原有语义拒绝分别标成固定 Pydantic 类型：`claim_action_mismatch`、`claim_evidence_id_missing`、`claim_evidence_id_unexpected`、`claim_subject_id_missing`、`claim_scope_duplicate`。Provider 与持久化端口仍只接收最多八组白名单字段路径和类型，其他值不入库。FAQ Prompt `faq-answer-v1.6.2` 指定一般退货流程作为单条有 FAQ 引用的 `refund_policy/explain_policy`，避免把通用政策误写成某客户的退款结果或重复主体动作；注册摘要为 `efb00cc0dc7e82af925a61fe3bad6d26e64c30453c63b5b060e1253df09a970a`。严格业务校验、DLP、评分、模型调用上限及 TikTok 发送边界不变。本地测试不证明现场安全草稿与性能达标。

G5 R62 单会话已完成 FAQ 草稿和安全复核，却以 `transfer_human` 结束且没有安全 `delta`；记录中的 `safety_reasons=none` 和最终置信度 0 无法区分草稿要求人工、复核否决或置信度低。R63 仅在现有 Agent 运行摘要追加一个固定白名单 `decision_reason`，由既有决策输入在代码中确定。它区分 FAQ 草稿 `needs_human`、复核三项布尔否决和各段置信度不足；不在白名单的值收敛为 `unknown`，不持久化模型正文、字段值或原始异常。Agent 决策、严格 Schema、DLP、阈值、调用次数与 TikTok 发送边界均不变。现场安全 `delta` 和 50 并发须用新候选再次验证。

## Prompt 与策略版本

系统 Prompt、DLP 规则、结构化声明和回复策略使用可审计版本。Agent 配置只能选择受控语气、语言和品牌名，不能写任意 Prompt、模型或阈值。版本变化必须更新评测和发布基线。

## RAG

- Embedding：本地 BGE-M3，固定 Revision 与 SHA-256，向量维度 1024。
- 召回：Dense Top-20；重排：bge-reranker-large Top-5。
- 接受门槛：最高 Dense 相似度至少 `0.52`；低于门槛返回无可靠知识并转人工/保守回答。
- 引用：只允许本次已接受候选中的知识标识，不允许模型伪造引用。
- 评测：冻结数据集同时覆盖有答案和无答案样本，坏样本或模型资产不匹配直接失败。

## 知识语义与审批

知识条目明确区分事实/政策/操作建议等语义类型和客户范围。内容、语义类型或范围变化生成新 `document_version`，撤销上一版本审批。发布动作目前只产生 `approved_for_internal_review`；`approved_for_public_reply` 未开放，FAQ 审批不授予自动发送权限。

## 可信业务声明

订单状态、物流、退款、优惠、库存、政策和客户身份等声明必须来自当前工具结果或已审批知识，并携带内部可验证来源。DeepSeek 不是业务事实来源。缺少来源、来源冲突、数据过期或结构未知时，不生成确定性承诺，改为说明无法确认并转人工。

## 工具白名单

Agent 不直接访问业务数据库或平台 SDK。每个工具都必须有：

- 强类型输入/输出和字段允许列表；
- 店铺范围、角色权限和风险级别；
- 超时、幂等、审计和可观测字段；
- 明确的失败关闭与人工接管结果。

只读查询与建议生成可以进入 v0.1；外部写入只有人工确认的普通 TikTok 文本消息例外。高风险写入、自动营销和公开自动回复保持关闭。

## 回复、翻译与营销

回复先形成安全结构化草稿，再按坐席/客户语言渲染。翻译不得改变金额、订单号、政策、行动主体或风险级别。营销文案只能作为内部预览，不能绕过审批、幂等、频控和平台权限自动发送。

工作台单条中文辅助译文由坐席点击后触发，复用现有 `TranslationService` 和 DeepSeek 结构化输出；模型输入在现有 Prompt 安全/DLP 边界脱敏，结果只在当前会话页面展示，不写回 TikTok、不自动发送，也不批量回填历史。`WORKSPACE_MESSAGE_TRANSLATION_ENABLED` 独立于通用 `LLM_ENABLED`，默认关闭，当前仅供受审 staging 覆盖层启用。翻译失败保留原文并允许重试；生产翻译质量与数据边界仍由 `MVP-011` 独立验收。

`customer-translation-v1.0.1` 明确要求 DeepSeek JSON Output 恰好返回 `source_language`、`target_language`、`message_translation`、`draft_translation`；源/目标语言复制可信输入，没有草稿时最后一项为 `null`。模型输出继续按 Pydantic 必需字段及目标语言校验，缺字段不做猜测性兼容，失败关闭并允许人工重试。

## 终态与观测

关键终态包括：成功建议、无可靠知识、DLP 阻断、工具失败、模型失败、需要复核和转人工。观测至少覆盖首响应、总延迟、检索命中、拒判、结构失败、DLP、工具成功率、转人工率和 Provider 错误；日志只保存低敏聚合与标识，不保存完整输入输出。

G4 冻结合成评测对失败样本额外保存低敏定位提示：售后结构化声明仅列不匹配字段名；禁用词仅列冻结样本中的序号、是否所有命中均在引号内，以及是否所有命中附近都有禁止用语；缺失必需内容仅列冻结组的零基序号（0～7）。这些提示是保守的排查线索，不是语义安全裁定；既有判分、85% 门槛、冻结样本和失败关闭均不变。评测报告及工作流白名单禁止保存禁用词原文、必需词原文、模型草稿、客户正文和凭据；历史报告无法补算新增组序号。

staging Prompt `real-model-eval-v1.2.3` 的获批真实复测为 33/36：售后声明和引用禁用语两项已过，但否定、英文条件和西语英译三项失败。后续 `real-model-eval-v1.2.4` 保留有证据售后声明及禁用语改述规则，并明确区分页面未显示与实际退款结果、平台批准的前置条件与具体申请是否已批准、英译的准备中与尚未发货状态。该版本已独立获批发布并部署 staging；一次获批真实复测为 34/36，西语英译和上一轮的否定样本恢复，但另一个英文否定样本缺必需组 0、英文条件样本仍命中未引用禁用词。冻结数据、禁用词判分、85% 门槛和真实发送开关均未调整；数值达标不能宣称 G4 关闭。

`real-model-eval-v1.2.5` 曾对合成评测 Prompt 增加英文正向句式；2026-10-13 获批真实复测为 34/36，否定状态样本恢复，条件政策仍命中禁用内容，弃购样本新命中禁用内容。此为已被下一轮取代的历史现场结果，见 [R11 TR](../reports/tests/TR-MVP-005-20261013-R11.md)。

先前 staging 运行的 `real-model-eval-v1.2.6` 仅给既有合成评测 Prompt 增加输出前自检：英语条件政策删去对具体申请是否获批的断言，只保留一般现在时的批准前置规则；购物车营销草稿只写允许的查看或结算提醒，删去对缺席促销或库存紧迫话术的复述，包括否定句。Prompt 版本和契约测试同步更新；冻结数据、禁用词判分、85% 门槛、安全开关与公共接口不变。分别获批的镜像、staging 和单次真实复测见 [R13 TR](../reports/tests/TR-MVP-005-20261013-R13.md)：弃购样本本轮通过，条件政策仍命中禁用内容，售后样本新命中禁用内容。报告没有模型正文，不能反推具体措辞。

`real-model-eval-v1.2.7` 收敛合成评测政策答复：只按证据写申请资格、时限和审核流程；售后用正向申请与平台审核句式，英文条件政策用一般现在时说明批准是处理前置条件。正文止于规则，省略个案审批现状、结果保证和禁止断言的转述。移除旧版重复的条件政策反向禁令，保留结构化声明、冻结 36 条、严格判分、85% 门槛、DLP 与发送开关。该版本已部署 staging，[一次获批真实复测](../../release/evidence/ai/crm-staging-g4-v127-live-38344292398.json)为 34/36：售后样本本轮通过，英文条件政策仍命中冻结禁用词序号 0，西语问题的英语答复缺少审核必需组序号 1。低敏报告不保存模型正文，不能推断具体措辞或跨轮稳定性；G4 保持部分通过。

G4 离线评测流程 `policy-repair-v1` 在首个结构化草稿后，以本次合成证据进行独立的政策条件、审核步骤和引用校验。校验器不接收冻结答案或评分标签；可修复的草稿在一次性摘要授权、字段白名单和 DLP 检查后，最多请求一次完整重写。首轮与修复轮都重新检查结构、DLP、证据和政策安全；任何阻断或修复失败均隐藏正文、清空声明并转人工。每条真实样本最多两次模型调用，34 条最多 68 次，两条故障注入零调用；Token 总预算为 120000。原冻结评分器、36 条数据、85% 门槛和运行发送开关不变。报告分别保存首轮与终态的评分、哈希、低敏原因、用量、延迟和调用数，并用 `evaluation_flow_version` 区分旧单轮报告。`repair_success_count` 只计政策校验通过且确实产生草稿的修复；新增 `repair_final_pass_count` 才计其中通过冻结终态判分的修复。修复只返回转人工时仍失败关闭，但不计为修复成功。DLP 诊断仅保留固定规则类别，不保留命中文本或字段值。修复 Prompt、草稿原文、客户正文和凭据不进入报告。该流程已部署 staging；首次 live #38359902457 为 28/36、合法样本误拦 4，未通过 G4。正式回复工作流不使用此离线修复环。

政策校验在 `faq_chunk` 证据明确肯定“这个条件规则”时，可以将同一条合成提问中的“平台批准才开始处理”作为被证实规则的上下文；提问本身不能单独充当证据。证据否定确认、提问缺平台批准条件、草稿把批准者换成客户、证据引用不匹配或草稿声称个案已获批，仍阻断或进入受控修复。个案批准断言按句内否定逐项识别，其他句子的否定不能取消它。此修正仅作用于 G4 离线政策校验，不改变冻结判分、DLP 或正式回复路径。[新 live #38398552906](../../release/evidence/ai/crm-staging-g4-r22-live-38398552906.json) 中 `condition-open-002` 已通过，但整体仍有五条失败，不能据单项通过关闭 G4。

2026-10-13 的一次 live #38373134957 为 27/36，危险逃逸 0、合法误拦 5；多条草稿被 `DRAFT_DLP_UNCERTAIN_LOCATION` 失败关闭。随后固定类别诊断已部署 staging；[新 live #38379386241](../../release/evidence/ai/crm-staging-g4-location-live-38379386241.json) 为 28/36、危险逃逸 0、合法误拦 4，六条被拒输出均属于 `DRAFT_DLP_UNCERTAIN_LOCATION_SEPARATORS`，另有政策证据不足与一次修复无草稿。原文、命中片段和凭据仍不留存；固定形态只能定位规则，不能证明内容安全。原地址三态规则、冻结判分、85% 门槛及失败关闭不变；调整规则须有普通标点和真实地址的确定性反例与安全审查。

`real-model-eval-v1.2.8` 仅调整合成评测系统指令：草稿以完整短句逐项表达证据，避免逗号列表或多个逗号从句，同时禁止省略、合并或改变证据、否定、条件及翻译含义。该版已部署 staging，[live #38389129411](../../release/evidence/ai/crm-staging-g4-v128-live-38389129411.json) 为 30/36（83.33%），仍有三条 `LOCATION_SEPARATORS`、一条否定缺项、一条政策证据不足、一条修复无草稿。DLP 规则、结构化声明、冻结样本、严格判分、85% 门槛和真实发送开关不变。不同运行的分数变化不证明稳定因果，更不能证明剩余分隔符文本安全；G4 未过。

同一 Prompt `v1.2.8` 加离线政策指代修复后的 staging [live #38398552906](../../release/evidence/ai/crm-staging-g4-r22-live-38398552906.json) 为 31/36（86.11%）、危险逃逸 0、合法误拦 2；三条 `LOCATION_SEPARATORS`、一条否定缺项和一条多语言修复无合格草稿仍失败。综合分数虽越过 85%，报告 `passed=false`，不得放宽 DLP 或把固定形态诊断当作安全证据。

`real-model-eval-v1.2.9` 将 G4 离线评测流程标为 `policy-repair-dlp-regeneration-v1`：仅首稿命中固定的 `DRAFT_DLP_UNCERTAIN_LOCATION_SEPARATORS` 时，在预算内用原已验证合成输入和独立注册的系统指令重新生成一次；疑似首稿正文和声明绝不放入第二次请求。明确地址、邮箱、电话、密钥等阻断仍直接转人工。第二稿重新执行 DLP、政策证据和冻结判分，任何安全或政策未通过都隐藏正文并转人工；每条最多两次模型调用，政策修复和 DLP 再生成互斥。低敏报告分别统计两种二次尝试，保留首轮与终态、Token 和时延。冻结集、85% 门槛和真实发送开关不变。[staging live #38413001338](../../release/evidence/ai/crm-staging-g4-r24-live-38413001338.json) 为 33/36、合法误拦 1，G4 未通过。

2026-10-14 的低敏诊断为每条样本增加 `second_attempt_disposition` 枚举：`not_attempted`、`accepted`、`model_transfer`、`dlp_rejected`、`policy_rejected` 或 `provider_failed`。它只区分政策修复或 DLP 再生成的第二次调用终态，不保存第二稿内容，不作为评分或安全放行依据；预算耗尽或请求被拦截时仍为 `not_attempted`，具体状态继续由既有 `repair_outcome`/`regeneration_outcome` 表达。冻结集、Prompt `v1.2.9`、判分、调用上限、DLP 与 TikTok 发送开关均未改变。该版随 main `60bf105` 部署 staging；[R27 live](../../release/evidence/ai/crm-staging-g4-r27-live-38496772348.json) 终态 33/36、合法误拦 1：条件政策第二稿 `dlp_rejected`，多语言政策第二稿 `model_transfer`，否定说明未做第二次调用。报告没有草稿原文，不能据形态原因码认定被拒内容安全；G4 未过。

`real-model-eval-v1.2.10` 仅强化 G4 疑似分隔符草稿的第二次再生成指令：`content` 使用独立完整短句，不使用现有地址分隔符；保留证据含义、否定、条件、翻译及声明。首稿不进入再生成请求，第二稿仍从头执行原 DLP、政策和冻结评分，最多两次调用，失败转人工。普通双逗号政策句和混合政策地址的确定性安全对照见 [R28 TR](../reports/tests/TR-MVP-005-20261014-R28.md)。该候选已按 [R29 TR](../reports/tests/TR-MVP-005-20261014-R29.md) 部署 staging 并完成零调用 prepare；[R30 live](../reports/tests/TR-MVP-005-20261014-R30.md) 机器 `passed=true`、34/36、危险逃逸与合法误拦均 0，条件政策第二稿恢复，但否定与多语言仍各有逐项失败。G4 保持 `PARTIAL`。

`real-model-eval-v1.2.11` 针对 R30 两条逐项失败收紧指令：首稿对有证据的页面否定说明明确写出“未显示/没有显示”完成状态，不据此推断实际退款结果；一次性政策修复在证据同时给出申请时限和平台审核时，保留非空的人工审核草稿、两项事实及有证据的 `refund_policy` 声明。指令不包含冻结样本评分标签或样本答案；冻结集、评分器、DLP、调用上限、安全开关与真实发送模式均不变。[R32 部署](../reports/tests/TR-MVP-005-20261014-R32.md)后的 [R33 现场复测](../reports/tests/TR-MVP-005-20261014-R33.md)为 35/36，否定说明通过；多语言政策首稿仍缺平台审核步骤，第二次调用记为 `provider_failed` 并安全转人工，Provider 故障 1，机器 `passed=false`。工作流日志出现一条未绑定样本的 `deepseek_output_invalid`；低敏报告不能区分输出失败子类型或还原草稿，G4 仍为 `PARTIAL`，production No-Go。

`real-model-eval-v1.2.12` 只收紧 G4 离线政策修复 Prompt 的输出契约：列出严格 Schema 允许的七个 `reason_code`；有证据的 FAQ 政策人工复核使用 `human_review+policy_grounded`；输入中的政策诊断码只作修复提示，不得填入输出字段。R48 的低敏证据仅证明修复稿 `reason_code / literal_error` 并安全失败关闭，未保留非法原值；本修复仍须新镜像、staging 部署及另一次精确获批的真实 live 复测验证。冻结样本、Schema、评分、DLP、85% 门槛、最多两次调用和 TikTok 发送开关均不变。

[R52 单次获批真实复测](../reports/tests/TR-MVP-005-20261015-R52.md)确认 `v1.2.12` 的售后和多语言两条政策修复稿都在 `reason_code / literal_error` 严格 Schema 校验处失败关闭；报告未保存非法值，不能断言模型是否复制了输入诊断码。`real-model-eval-v1.2.13` 的离线修复请求将内部政策诊断码在本地映射为固定白名单自然语言要求后再外发，安全边界仍校验精确载荷哈希、字段集合和要求白名单。政策修复 Prompt 收窄为有证据草稿 `human_review+policy_grounded` 或真正证据不足时 `transfer_human+insufficient_evidence`；首稿已合法且证据充分时保留其 `reason_code`。输出仍由原严格 Schema、DLP、政策证据和冻结评分器逐层验证；任何失败继续隐藏正文并转人工。该候选已部署，且 [R56 一次真实复测](../reports/tests/TR-MVP-005-20261016-R56.md) 逐项 36/36、危险逃逸/合法误拦/Provider 故障均为 0；这只证明本轮冻结集通过；冻结数据、85% 门槛、两次调用上限、Token 预算及 TikTok 发送开关不变。

下一版 G4 离线评测仅增加低敏 Provider 失败诊断：每条失败样本保存稳定的 `provider_error_code`，DeepSeek 输出检查可再保存 `provider_output_failure_kind`，取值限定为 `unfinished`、`empty`、`invalid_structure`。未失败样本两个字段均为空；故障注入不计真实 Provider 失败。工作流白名单同时限制字段与枚举，不记录响应正文、Prompt、供应商请求 ID 或原始异常。此信息用于定位下一次受控复测，不回填 R33 历史报告，不改变冻结集、Prompt、评分、85% 门槛、失败关闭、两次调用上限或 TikTok 发送设置；只有新镜像部署后的新报告才含可用诊断。

R34 低敏诊断已随 R35 镜像部署 staging。[R37 单次获批 live](../reports/tests/TR-MVP-005-20261014-R37.md) 的新报告确认 35/36、危险逃逸 0、合法误拦 0、Provider 故障 1，机器 `passed=false`。唯一失败的多语言政策样本首稿缺审核步骤；第二稿的 `provider_error_code=LLM_OUTPUT_INVALID`、`provider_output_failure_kind=invalid_structure`，随后安全转人工。该类别仅表示 JSON 解析或结构 Schema 校验失败，不含具体字段或原文，不能据此确定模型输出的精确错误。冻结数据、严格评分、85% 门槛、失败关闭和发送开关不变；G4 继续 `PARTIAL`。

R38 候选仅收窄后续 G4 低敏诊断：DeepSeek 结构失败按 `invalid_json` 与 `invalid_schema` 区分，保留历史 `invalid_structure` 枚举兼容既有记录。Schema 失败最多保存八组经固定白名单映射的字段路径和 Pydantic 错误类型；未知字段只记 `unknown`，未知错误只记 `other`，不写模型正文、原始字段名/值、异常消息或供应商请求 ID。工作流复核两层白名单及数量，非 Schema 失败必须没有 Schema 明细。此诊断不改变原有 JSON/Schema 拒绝、失败关闭、评分器、冻结集、85% 门槛、调用上限、Prompt、DLP 或 TikTok 发送开关；现有 staging 镜像不含 R38，R37 原报告不可回填细分原因。部署与新付费 live 均需另行精确授权。

当前安全基线为 `AUTO_REPLY_ENABLED=false` 和 `REAL_TIKTOK_HIGH_RISK_WRITE_ENABLED=false`。任何开放都需要独立架构评审、真实门禁和回滚方案。
