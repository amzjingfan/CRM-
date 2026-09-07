# M04 回复、翻译、营销与评测规范

## 1. 文档信息

| 项目 | 内容 |
| --- | --- |
| 文档编号 | AI-005-REPLY |
| 模块编号 | M04 |
| 版本 | v1.2 |
| 日期 | 2026-08-24 |
| 适用阶段 | AI Agent Phase 4 与真实环境接入前安全整改 |
| 替代版本 | `AI-005-REPLY-回复翻译营销与评测规范-v1.1.md` |
| 代码基线 | Python 3.11.15、数据库迁移 `018_ai_observability` |

本版本根据综合测试 012 修正自动回复授权、工具证据对象绑定和营销复核边界。`BusinessClaimInventory` 仍用于解释、审计和纵深检查，但模型自报的 `complete=true` 不再拥有自动回复授权能力。

## 2. 根因与安全原则

此前反复出现危险漏放和合法误杀，并非少收录几个同义词，而是把开放语言分类结果错误地当成业务授权：

1. 有限正则无法同时完整识别新动作、新业务论元、否定、条件、引用和技术对象。
2. 同一个生成模型输出正文并自报声明，不能证明声明完整或分类正确。
3. 第二次模型布尔复核仍是概率判断，不能替代确定性授权。
4. 仅绑定 `tool_call_id + tool_name` 无法证明工具结果属于当前店铺和当前订单。
5. 单个 `is_safe` 同时表示“可供人工复核”和“可自动发送”，导致安全与可用性互相牵制。

固定原则：

- 文本和模型判断可以发现风险，但不能授予自动发送权限。
- 未解析、模型改写或旧兼容入口统一最高进入人工复核。
- 自动回复资格只来自代码根据当次可信数据确定性渲染的文本。
- 人工可见草稿与自动交付资格分别判断，不再要求开放语言二元分类器同时做到零漏放和零误杀。

## 3. 三态交付契约

`ReplySafetyResult` 分离以下两个概念：

- `is_safe`：没有命中确定性阻断项，可作为人工复核候选。
- `automatic_delivery_allowed`：文本来自可信确定性模板，且没有任何阻断项。

工作流固定为三态：

```text
确定性阻断项存在
→ TRANSFERRED，隐藏成功话术

没有阻断项，但 automatic_delivery_allowed=false
→ HUMAN_REVIEW，保留草稿供人工判断

没有阻断项，且 automatic_delivery_allowed=true，再满足置信度门槛
→ AUTO_REPLY_READY，send_performed=false
```

`AUTO_REPLY_READY` 仍不执行发送；全局 `AUTO_REPLY_ENABLED=false` 在正式独立验收前不得修改。

## 4. 自动回复允许来源

`ReplyContentOrigin` 固定为：

- `unstructured`：旧内部文本入口，只能人工复核。
- `model_generated`：模型自由生成或改写，只能人工复核。
- `trusted_faq_template`：逐字来自本次唯一 FAQ 引用的已发布答案。
- `trusted_tool_template`：代码根据本次唯一真实查询结果和有限状态表生成。

### 4.1 FAQ

- 只接受一个本次检索命中的 chunk。
- 从规范 FAQ 内容提取答案后，只做 Unicode 和空白归一化。
- 模型答案必须与可信答案逐字一致；同义改写、扩写、多引用或无法提取答案均降为人工复核。
- FAQ 仍须通过敏感信息、已知越权承诺和独立依据复核。

### 4.2 工具

- 自动模板仅覆盖真实成功的 `query_order` 和 `query_logistics` 有限状态。
- 未知状态、多个结果、Mock、写工具或模型改写均不得自动回复。
- 模板只描述工具返回的标准状态，不复述订单号、物流号、地址或其他敏感值。

## 5. 工具证据对象绑定

可信工具证据由执行层构造，模型无权创建或修改：

```text
TrustedToolEvidence
  tool_name
  store_id
  subject_ids
  mocked
```

每条工具声明必须同时满足：

- `tool_call_id` 属于本次成功调用。
- 工具类型匹配规范主体和动作。
- 证据 `store_id` 等于当前 Agent 命令店铺。
- 声明 `subject_id` 精确包含在工具结果提取的可信对象 ID 集合中。
- Mock 写结果不得支持真实完成声明。

任一条件不满足返回 `INVALID_BUSINESS_CLAIM_EVIDENCE` 或 `MOCK_COMPLETION_CLAIM` 并转人工。订单 A、其他店铺或其他业务对象的证据不能支持订单 B。

## 6. 结构化声明与旧文本扫描

- `BusinessClaimInventory` 继续用于 Schema 约束、证据解释、审计和风险发现。
- `complete=true` 只表示输出满足 Schema，不证明模型没有漏报或错分。
- 独立模型复核继续存在，但只作为附加门禁，不能单独把模型文本升级为自动回复。
- `RefundFactPolicy` 保留为旧入口和已知风险诊断；它的结果不得作为自动回复授权。
- 新增危险同义词或合法技术对象不再通过扩展词表解决；生产调用方必须使用 `automatic_delivery_allowed`。
- v1.1 所述“旧入口兼容”仅指可获得人工复核结果，不再表示该入口可以返回生产自动发送授权。

## 7. 营销与翻译

- 营销生成增加独立 `marketing-copy-review-v1.0.0` 复核，检查依据、安全和声明一致性。
- 根据 REAL-AI-04，当前营销链路没有可审计人工批准状态，因此无论两层模型是否通过，结果固定 `requires_human=true`、`is_safe=false`、`content=null` 和 `send_performed=false`。
- AI 营销不得因模型自报空声明、`other` 或错误极性而进入可发送状态。
- 翻译只处理已脱敏输入和已经通过主安全门禁的草稿；翻译不提升自动回复权限。

## 8. Prompt 版本

| 用途 | 版本 |
| --- | --- |
| 工作流 | `faq-agent-workflow-v1.4.0` |
| FAQ 回答 | `faq-answer-v1.3.0` |
| FAQ 依据复核 | `faq-grounding-review-v1.3.0` |
| 工具回答 | `tool-answer-v1.3.0` |
| 工具依据复核 | `tool-grounding-review-v1.3.0` |
| 翻译 | `customer-translation-v1.0.0` |
| 营销生成 | `marketing-copy-v1.2.0` |
| 营销独立复核 | `marketing-copy-review-v1.0.0` |

## 9. 测试与生产门禁

- 测试应分别断言“人工可复核”“确定性阻断”和“允许自动交付”，不得继续只用旧 `is_safe` 二元值衡量开放语言自动发送安全。
- 独立危险自由文本的安全要求是 `automatic_delivery_allowed=false`；独立合法自由文本可进入 `HUMAN_REVIEW`，不因词表命中被误报为已授权自动发送。
- 必须覆盖模型空声明、`other`、非业务对象错分、错误极性、只声明安全前缀、FAQ 危险扩写、跨订单/跨店铺证据和营销复核失败。
- 正式缺陷关闭、真实模型 live gate、50 并发和五天稳定性结论只由测试工程师生成。
- 自动回复、AI 翻译、AI 营销和真实平台写在正式验收前继续保持关闭。

