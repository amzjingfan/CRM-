# CRM 智能聊天系统 FAQ RAG 与单 Agent 工作流规范 v1.1

## 1. 文档信息

| 项目 | 内容 |
| --- | --- |
| 文档编号 | AI-002-RAG |
| 版本 | v1.1 |
| 模块编号 | M04 |
| 主责 Agent | AIAgent开发工程师Agent |
| 状态 | 已由 v1.2 替代 |
| 更新日期 | 2026-08-21 |
| 基础版本 | `AI-002-RAG-FAQ检索与Agent工作流规范-v1.0.md` |

本版本继承 v1.0 的模块边界、LangGraph 状态、Prompt、置信度、引用和人工接管规则，仅记录本地 BGE 方案的评审稿。当前生效实现见 `AI-002-RAG-FAQ检索与Agent工作流规范-v1.2.md`。

## 2. 目标模型基线

```text
embedding provider: local_bge
embedding model: BAAI/bge-m3
embedding revision: 5617a9f61b028005a4858fdac845db406aefb181
embedding dimensions: 1024
reranker model: BAAI/bge-reranker-large
reranker revision: 55611d7bca2a7133960a6d3b71e083071bbfc312
candidate top_k: 20
final top_k: 5
```

模型资产位于 `CRM智能聊天系统/deploy/models`，状态为“已下载、未启用”。模型权重不进入版本库，Revision、SHA-256 和文件大小以 `deploy/models/model-manifest.json` 为准。

## 3. 目标检索链路

```text
租户安全查询上下文
→ 输入脱敏
→ BGE-M3 生成 1024 维 Dense 查询向量
→ pgvector 店铺隔离 Top 20 候选召回
→ bge-reranker-large 对查询/候选片段打分
→ 按重排序分数稳定排序
→ 最终 Top 5
→ 引用校验、回答生成和安全复核
```

向量召回继续强制过滤 `store_id`、`published`、`ready`、当前文档版本和未删除状态。Reranker 只能缩小或调整当前店铺候选集合，不能增加未被向量召回的文档，也不能绕过知识库内部端口。

## 4. 分数与动作规则

- BGE-M3 的相似度阈值必须使用项目 FAQ 评测集重新标定，禁止直接复制 OpenAI 的 0.70。
- Reranker 原始分数不是业务概率，第一阶段只决定候选顺序。
- `retrieval_score` 的新定义、归一化和阈值只有在评测与 ADR 确认后才能进入最终置信度。
- 无候选、模型不可用、重排序失败、非法候选 ID 或质量门禁失败时强制转人工。
- `auto_reply` 仍只表示 `AUTO_REPLY_READY`，固定 `send_performed=false`。

## 5. 模型服务边界

- 单实例内部模型服务统一加载 BGE-M3 和 Reranker。
- backend 与 jobs 只调用类型化内部契约，不直接加载权重或管理 CUDA。
- 模型服务不访问 PostgreSQL、Redis、平台适配器、会话、订单或消息表。
- 输入只包含脱敏后的查询和当前店铺候选片段；输出只包含向量或候选 ID 与分数。
- 日志不保存查询正文、FAQ 正文、向量、模型原始输出或权重路径中的本机隐私信息。

## 6. 数据迁移门禁

- `knowledge_chunks.vector(1536)` 必须通过独立 Alembic 迁移切换为 1024 维。
- 所有 1536 维旧向量作废并重新向量化，禁止通过截断、填零或投影伪造兼容。
- 迁移前后不得在同一字段混写不同 Provider 或不同维度。
- 新 Provider 未通过回填、召回质量和回滚验证前，生产默认值不得切换。

## 7. 测试与评测

后续正式测试至少覆盖：

- 模型 Revision、SHA-256、离线加载和缺失文件失败。
- 1024 维、有限数值、归一化、批处理、超时和 OOM。
- Dense Recall@20、重排序后 Recall@5、MRR、nDCG 和引用合法率。
- 中英文、错别字、短查询、无答案、混合问题和 Prompt 注入。
- 店铺隔离、文档状态、当前版本和并发向量化回归。
- RTX 4060 8 GB 下的显存峰值、P95 延迟、吞吐、冷启动和并发上限。

Fake Provider 只能用于确定性测试。正式质量和性能结论由测试工程师在本地真实模型上生成报告。

## 8. 当前未完成项

- ADR-002-AI 尚待架构师确认。
- 本地模型服务、BGE Provider 和 Reranker 契约尚未实现。
- 1024 维数据库迁移和全量重新向量化尚未实施。
- 新的分数阈值、质量门禁和生产回滚尚未确认。
