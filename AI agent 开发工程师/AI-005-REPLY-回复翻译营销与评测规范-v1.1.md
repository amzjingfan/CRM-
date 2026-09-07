# M04 回复、翻译、营销与评测规范

## 1. 文档信息

| 项目 | 内容 |
| --- | --- |
| 文档编号 | AI-005-REPLY |
| 模块编号 | M04 |
| 版本 | v1.1 |
| 日期 | 2026-08-24 |
| 适用阶段 | AI Agent Phase 4 与真实环境接入前安全整改 |
| 替代版本 | `AI-005-REPLY-回复翻译营销与评测规范-v1.0.md` |
| 代码基线 | Python 3.11.15、数据库迁移 `018_ai_observability` |

本版本根据综合测试 011 修正退款自然语言安全边界。核心变化是把业务授权从自由文本正则迁移到结构化业务声明与可信证据绑定；文本扫描只保留为兼容和纵深防御。

## 2. 责任和系统边界

- AI Agent 负责语言识别、结构化回复、`BusinessClaimInventory`、证据绑定请求、独立依据复核、翻译、安全决策和低敏追踪。
- 全栈服务负责认证、店铺隔离、可信 FAQ 命中、可信工具结果、公开 API、SSE、业务表和平台写。
- 测试工程师负责独立安全样本、真实模型质量、并发、平台与稳定性正式结论。
- Agent 结果固定 `send_performed=false`；`AUTO_REPLY_READY` 不等于消息已经发送。
- `AUTO_REPLY_ENABLED`、`AI_TRANSLATION_ENABLED`、`AI_MARKETING_ENABLED` 默认保持 `false`。

## 3. 结构化业务声明

FAQ、工具和营销生成输出必须返回：

```text
BusinessClaimInventory
  complete = true
  claims[]
    subject_type
    subject_id
    action
    tense
    polarity
    condition
    evidence_type
    evidence_id
    confidence
```

规范字段要求：

- `subject_type` 只允许退款政策、退款申请、退款决定、退款资金、订单、物流、客户画像、地址、优惠券、平台消息、非业务对象和 `other`。
- `action` 只允许政策说明、提交申请、批准、拒绝、执行、资金划转、资金接收、状态说明、查询、更新、发送、展示和 `other`。
- 主体与动作组合由 Pydantic 校验；模型不能把“资金划转”重新定义成“政策说明”。
- `polarity` 为 `affirmed/negated/uncertain`；`condition` 为 `actual/conditional/hypothetical/quoted/example`。
- FAQ/工具事实必须提供 UUID `evidence_id`；无具体证据和触发摘要不得伪造 ID。
- 声明不保存客户正文、知识正文、完整工具结果或密钥。

## 4. 确定性证据门禁

门禁顺序：

```text
结构 Schema 校验
→ 主体/动作组合校验
→ evidence_id 是否属于本次运行
→ 业务动作与证据工具是否匹配
→ 文本纵深扫描检查声明遗漏
→ 独立模型复核正文与声明一致性
→ 置信度和人工接管决策
```

固定规则：

- FAQ chunk 只能支持政策说明，不能证明具体客户退款申请已提交、退款已批准/拒绝、款项已执行/划转/到账。
- 当前白名单没有退款事实工具，因此上述具体退款结果统一返回 `UNAUTHORIZED_COMMITMENT`。
- 订单、物流、客户画像、地址、优惠券和平台消息事实必须绑定匹配的成功 `tool_call_id`。
- Mock 写工具不能支持真实完成声明，命中 `MOCK_COMPLETION_CLAIM`。
- 跨运行、未知或不匹配证据返回 `INVALID_BUSINESS_CLAIM_EVIDENCE`。
- 正文触发已知高风险模式但声明清单没有对应命题时返回 `BUSINESS_CLAIM_INVENTORY_MISMATCH`。
- 独立复核必须返回 `business_claims_consistent=true`；否则隐藏草稿并转人工。

## 5. 文本兼容扫描

`RefundFactPolicy` 不再是生产授权来源，只承担两项职责：

1. 兼容仍直接调用 `ReplySafetyPolicy.evaluate(answer, evidence_kind=...)` 的旧内部入口。
2. 对结构化清单做遗漏检测，发现已知高风险文本但没有声明时失败关闭。

兼容扫描规则：

- 业务主体对资金、账户、钱包或收款方的自然过去完成表达视为高风险候选，不要求固定出现“已/has”。
- 页面、表单、面板、字段、模板、说明页、配置和流程图属于非业务对象。
- 否定、证据不足、引用和示例必须直接支配结果候选；前置政策或否定不能掩盖后置独立资金事实。
- 同一命题只经过一个作用域结论；不得在局部作用域判安全后再被宽松 fallback 重复判定。
- 文本规则不能形式化覆盖开放语言，不得据此开启生产自动回复。

## 6. Prompt 版本

| 用途 | 版本 |
| --- | --- |
| 工作流 | `faq-agent-workflow-v1.3.0` |
| FAQ 回答 | `faq-answer-v1.2.0` |
| FAQ 依据复核 | `faq-grounding-review-v1.2.0` |
| 工具回答 | `tool-answer-v1.2.0` |
| 工具依据复核 | `tool-grounding-review-v1.2.0` |
| 翻译 | `customer-translation-v1.0.0` |
| 营销 | `marketing-copy-v1.1.0` |

回答和营销 Prompt 必须要求完整声明全部业务命题；复核 Prompt 必须独立检查正文、声明和证据是否一致。Prompt、Schema 或规范动作变化时必须同步升级版本并重新评测。

## 7. 翻译、营销和可观测性

- 翻译只处理已脱敏客户消息和已经通过主安全门禁的草稿；翻译失败不改变主决策。
- 营销生成只接收最小可信触发摘要，输出同样必须携带完整业务声明；安全通过后仍只交给受控工具链路。
- `agent_runs.output_summary` 只记录节点、Prompt 版本、稳定原因码、语言和低敏统计，不保存正文或完整模型响应。
- 本次不新增数据库字段、公开 API、SSE 字段或环境变量。

## 8. 测试与生产门禁

- 010 固定 32 条、011 固定 44 条和结构化 Schema/证据绑定用例必须全部通过。
- Phase 4、Agent 工作流、全后端和隔离 PostgreSQL 测试必须无回归。
- 测试工程师必须使用未提供给开发实现的独立危险与合法样本验证泛化。
- 真实模型评测必须检查声明完整率、主体动作准确率、证据合法率、危险漏放率和合法误杀率。
- 项目当前没有 Git，不得声称完成基于不可变提交的独立验证。
- 正式测试结论只由测试工程师在 `测试工程师/` 目录生成；本规范和实施记录不能替代正式验收。
