# M04 回复、翻译、营销与评测规范

## 1. 文档信息

| 项目 | 内容 |
| --- | --- |
| 文档编号 | `AI-005-REPLY` |
| 模块编号 | M04 |
| 版本 | v1.3 |
| 日期 | 2026-08-25 |
| 适用阶段 | AI Agent Phase 4 与真实环境接入前安全整改 |
| 替代版本 | `AI-005-REPLY-回复翻译营销与评测规范-v1.2.md` |
| 代码基线 | Python 3.11.15、数据库迁移 `018_ai_observability` |

本版本根据第十三次综合复测关闭“发布 FAQ 自动授权”和“工具对象 ID 脱敏与声明绑定倒置”两条实现路径。它不修改公共 API、数据库结构、知识库发布契约或平台写边界。

## 2. 根因

### 2.1 FAQ 授权来源错误

`published + ready + 逐字一致` 只能证明文本来自当前知识库版本，不能证明该知识已经按业务事实类型完成审批。现有 FAQ 表和发布接口没有政策知识、客户实例状态、资金事实等确定性类型，也没有自动回复审批状态。把任意逐字 FAQ 视为自动授权，会让误配置、批量导入错误和知识污染绕过模型文本门禁。

### 2.2 工具声明职责冲突

工具 Prompt 会把订单号等对象 ID 替换为 `[SENSITIVE_ID]`，旧契约却要求模型在 `business_claims.subject_id` 中复述真实 ID。模型遵守脱敏输入会因对象不匹配失败，省略声明反而可能借代码模板获得更高权限。根因是让不持有可信 ID 的模型负责对象级授权声明。

## 3. 固定安全边界

### 3.1 FAQ

- `ReplyContentOrigin.TRUSTED_FAQ_TEMPLATE` 只记录逐字来源，不授予 `automatic_delivery_allowed`。
- 在知识库引入类型化事实范围和可审计发布审批前，所有 FAQ 草稿最高进入 `HUMAN_REVIEW`。
- 正常政策 FAQ、危险实例状态 FAQ、批量导入 FAQ 和模型逐字复制遵循同一规则，不再使用文本词表决定自动权限。
- FAQ 仍执行引用、敏感信息、结构化声明和独立依据复核；确定性阻断项仍进入 `TRANSFERRED`。
- 未来若恢复 FAQ 自动回复，必须先由架构师确认知识类型、审批字段、迁移、管理接口和历史数据回填，AI 模块不得自行推断。

### 3.2 查询工具

- 真实 `query_order`、`query_logistics` 的对象级权威声明由服务端执行层生成。
- 代码声明固定绑定当次成功的 `tool_call_id`、工具类型、当前店铺和工具结果中的真实主对象 ID。
- 只有已知有限状态可以生成代码声明和自动回复模板；未知状态、Mock、多结果和写工具不取得自动权限。
- 真实对象 ID 不发送给模型。工具回答模型固定返回 `BusinessClaimInventory(complete=true, claims=[])`。
- 为兼容旧模型输出，`[SENSITIVE_ID]` 仅在 `evidence_id + subject_type + action` 与代码声明完全一致时绑定到真实对象；其他值继续按跨订单、错工具或错对象失败关闭。
- 模型声明只做纵深检查，不能替换、扩展或授权代码声明。

### 3.3 低敏审计

`agent_runs.output_summary` 增加权威声明摘要：

```text
subject_type:action:evidence_type:evidence_id
```

摘要不保存 `subject_id`、订单号、物流号、消息正文、知识正文或工具原始结果。`evidence_id` 与同一运行的 `tool_calls` 形成可追踪对象链路。

## 4. 三态决策

```text
确定性阻断
→ TRANSFERRED，隐藏候选话术

安全但没有确定性自动授权
→ HUMAN_REVIEW，保留草稿

真实查询工具固定模板 + 代码声明 + 独立复核 + 置信度达标
→ AUTO_REPLY_READY，send_performed=false
```

自动回复、翻译和营销开关继续默认关闭；本规范不授权真实平台发送。

## 5. Prompt 版本

| 用途 | 版本 |
| --- | --- |
| 工作流 | `faq-agent-workflow-v1.6.0` |
| FAQ 回答 | `faq-answer-v1.5.0` |
| FAQ 依据复核 | `faq-grounding-review-v1.5.0` |
| 工具回答 | `tool-answer-v1.5.0` |
| 工具依据复核 | `tool-grounding-review-v1.5.0` |
| 翻译 | `customer-translation-v1.0.0` |
| 营销生成 | `marketing-copy-v1.3.0` |
| 营销独立复核 | `marketing-copy-review-v1.0.0` |

## 6. 回归要求

- 正常和受污染的逐字 FAQ 都不得进入 `AUTO_REPLY_READY`。
- FAQ 模型改写继续最高进入人工复核，确定性危险声明继续转人工。
- 工具 Prompt 不出现真实对象 ID，并明确模型 `claims=[]`。
- `[SENSITIVE_ID]` 兼容声明可绑定当前可信对象，不得造成合法查询误转人工。
- 跨订单、跨店铺、错工具、错主体和错误证据 ID 继续失败关闭。
- 自动工具运行摘要必须包含低敏权威声明，并且不包含原始对象 ID。
- 模型空声明不会造成审计缺失，因为权威声明来自执行层代码。
- 版本化固定评测、后端全量回归、真实 PostgreSQL、Ruff、格式和 mypy 均须通过；正式缺陷关闭仍由测试工程师独立确认。

## 7. 尚未解除的生产门禁

- `AUTO_REPLY_ENABLED=false`、`AI_TRANSLATION_ENABLED=false`、`AI_MARKETING_ENABLED=false` 保持不变。
- 真实 DeepSeek 安全评测、真实模型 SSE 50 并发、五天稳定性、密钥轮换证明和真实平台写联调仍未完成。
- 当前项目不是 Git 仓库，不能声明提交级不可变基线独立验证。
