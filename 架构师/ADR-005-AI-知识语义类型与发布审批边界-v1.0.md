# ADR-005：知识语义类型与发布审批边界

## 1. 决策信息

| 项目 | 内容 |
| --- | --- |
| 编号 | `ADR-005-AI` |
| 版本 | `v1.0` |
| 状态 | `Accepted` |
| 决策日期 | 2026-09-01 |
| 决策 Agent | 架构师Agent |
| 实施 Agent | AIAgent开发工程师Agent、全栈开发工程师Agent |
| 验证 Agent | 测试工程师Agent |
| 关联任务 | `REAL-AI-03` |
| 关联缺陷 | `DEF-P4-AI-008`、`DEF-P4-AI-009` |

## 2. 背景

第八次独立测试用 48 条冻结后开放样本验证文本退款门禁，危险事实漏放 6 条、合法技术/非断言内容误杀 23 条，整体通过率 39.58%。连续八轮结果证明，自然语言中的金融对象、技术用途和非断言关系是开放集合，继续扩充正则不能同时满足 P1 零漏放和 P2 零误杀。

已发布 FAQ 只能证明文本来源，不能证明它有权陈述当前客户实例事实；模型生成的空业务声明也不能证明正文没有业务事实。因此需要把安全授权从开放文本猜测迁移到人工维护、逐版本审批、可审计的结构化元数据。

## 3. 决策

### 3.1 权威字段

`knowledge_documents` 保存当前版本的权威字段：

```text
statement_type:
  policy | technical_artifact | customer_instance_fact |
  non_assertive_proposition | unknown

customer_scope:
  none | generic | specific_customer

publication_approval:
  draft | approved_for_internal_review | approved_for_public_reply

semantic_schema_version: 1
approved_by: user UUID
approved_at: UTC timestamptz
```

审批人和审批时间只能由具有 `knowledge.manage` 权限的服务端发布操作产生。Embedding、LLM、导入文件和客户端均无权创建或提升审批状态。

### 3.2 版本和发布

- 正文、语义类型或客户范围发生实际变化时递增 `document_version`，撤销审批并恢复 `draft + pending`。
- `unknown` 和非法语义/客户范围组合禁止发布。
- 当前公开发布接口只产生 `approved_for_internal_review`；不开放公共回复审批入口。
- 批量导入只能创建草稿；历史知识迁移后保持 `unknown + draft`，禁止自动回填提升权限。

### 3.3 向量与检索

- 文档权威字段复制到 `knowledge_chunks.metadata.knowledge_safety`，并包含店铺、文档版本和审批版本。
- 向量写入时比较切片副本和文档权威值；不一致时拒绝写入。
- Dense 和 Hybrid 检索重复执行店铺、版本、发布、ready、语义类型和审批门禁。
- `KnowledgeRetrievalHit` 返回受 Pydantic 校验的 `KnowledgeSafetyMetadata`；缺失、损坏、伪造或版本漂移统一降级为未审批。

### 3.4 Agent 决策矩阵

| 类型与状态 | Agent 结果 |
| --- | --- |
| `policy/technical_artifact/non_assertive_proposition` + 当前店铺/版本 + 已批准内部复核 | 可保留安全草稿，最高 `HUMAN_REVIEW` |
| `customer_instance_fact` | 必须绑定当前店铺、当次、非 Mock 的真实查询工具证据；否则转人工并隐藏草稿 |
| `unknown/draft/缺失/损坏/跨店铺/版本漂移` | 转人工并隐藏草稿 |

FAQ 在本 ADR 下永远返回 `automatic_delivery_allowed=false`。公开 AI 回复、AI 营销、自动回复和 AI 触发的平台写操作继续由生产开关阻断。

## 4. 迁移决策

- 新迁移：`020_knowledge_safety`，前置为 `019_tiktok_channel_unique`。
- 迁移可升级、可回滚；不得修改 `001～019` 历史迁移。
- 旧数据默认 `statement_type=unknown`、`customer_scope=none`、`publication_approval=draft`。
- 人工治理顺序固定为：分类 → 审批当前版本 → 重新向量化 → 测试工程师独立复测。

## 5. 后果

正向结果：

- 安全授权变为可审计、可版本化、可测试的有限状态空间。
- 技术资产和非断言命题不再依赖不断增长的白名单。
- 客户实例事实无法通过 FAQ 发布状态绕过真实工具证据。

代价与约束：

- 存量 FAQ 必须人工分类和审批后才能重新参与检索。
- 运营人员错误分类仍属于治理风险，需要权限、二次确认、审计和独立抽检共同控制。
- 本决策只解决知识类型与发布审批边界，不代表真实模型质量、公开 SSE、稳定性或平台写操作通过。

## 6. 验收与回滚

必须验证：

- `019 → 020 → 019 → 020` 数据库迁移闭环。
- 存量知识未被自动批准。
- 发布失败不污染文档状态；内容/类型变化撤销审批。
- Dense、Hybrid、向量 Worker 和完整 Agent 工作流使用同一元数据。
- 报告 008 的失败样本进入结构化回归，且测试工程师另行设计未进入开发集的新开放样本。

回滚时关闭知识向量 Worker 和 AI 建议入口，降级到 `019` 后所有 FAQ 继续按旧的保守文本门禁处理；不得在回滚中自动恢复公共回复或平台写开关。
