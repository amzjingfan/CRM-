# CRM 智能聊天系统 FAQ RAG 与单 Agent 工作流规范 v1.2

## 1. 文档信息

| 项目 | 内容 |
| --- | --- |
| 文档编号 | AI-002-RAG |
| 版本 | v1.2 |
| 模块编号 | M04 |
| 主责 Agent | AIAgent开发工程师Agent |
| 状态 | 已实施，待正式质量评测 |
| 更新日期 | 2026-08-21 |
| 基础版本 | `AI-002-RAG-FAQ检索与Agent工作流规范-v1.1.md` |

## 2. 当前模型与数据基线

```text
embedding: BAAI/bge-m3@5617a9f61b028005a4858fdac845db406aefb181
dimensions: 1024
reranker: BAAI/bge-reranker-large@55611d7bca2a7133960a6d3b71e083071bbfc312
database head: 015_vector_ops（BGE 结构迁移仍为 014_bge_hybrid）
dense top_k: 20
lexical top_k: 20
RRF k: 60
candidate top_k: 20
final top_k: 5
```

模型服务使用 `torch 2.10.x` 与 `transformers 4.57.x`，依赖由 `uv.lock` 固定。权重从 `deploy/models` 只读挂载，服务强制离线加载、单 Worker、内部 Bearer Token；backend 和 jobs 不加载 Torch。

## 3. 当前检索链路

```text
可信 store_id + 脱敏查询
→ BGE-M3 1024 维 Dense 查询向量
→ pgvector Dense Top 20
  与 pg_trgm Lexical Top 20
→ RRF(k=60) 融合候选 Top 20
→ bge-reranker-large Cross-Encoder
→ Dense >= 0.45 或 Lexical >= 0.10 的最终 Top 5
→ 引用校验、回答生成、安全复核、置信度动作
```

两路数据库查询均强制过滤 `store_id`、`published`、`ready`、未删除和当前文档版本。Reranker 只能调整候选顺序，服务和 Agent 都校验候选 ID 集合完全一致，禁止增加跨租户候选。

## 4. 分数规则

- `dense_score` 是截断到 0–1 的 cosine 相似度，继续作为工作流 `retrieval_score`。
- `lexical_score` 是 PostgreSQL trigram similarity，只用于词法门禁和观测。
- `fusion_score` 是归一化 RRF 分数，只用于候选融合顺序。
- `reranker_score` 是未归一化 Cross-Encoder logit，只用于最终排序。
- 暂定安全门禁为 Dense 0.45 或词法 0.10，明确不是正式质量结论；测试工程师必须用项目 FAQ 评测集校准。
- 同时低于两路门禁、无候选、模型不可用、候选 ID 异常或安全复核失败时强制转人工。

## 5. 模型服务与安全

- 公开 CRM API 不暴露模型服务端点；内部端点为 `/internal/v1/embeddings` 和 `/internal/v1/rerank`。
- 推理输入只在请求内存中存在；日志不保存查询、FAQ 正文、向量、Token、模型路径或底层响应。
- BGE-M3 Pickle 权重必须匹配资产清单 SHA-256；可通过 `RETRIEVAL_MODEL_VERIFY_HASHES=true` 在冷启动时复核。
- 模型缺失、哈希错误、CUDA 不可用、OOM、超时或输出异常都失败关闭，不回退到无依据生成。
- `AUTO_REPLY_READY` 仍固定 `send_performed=false`，本次变更不增加工具执行或平台发送。

## 6. 数据迁移与回滚

- `014_bge_hybrid` 删除可重新生成的 1536 维旧切片，不删除 FAQ 正文。
- 已发布文档重置为 `pending`，由 Jobs Worker 在迁移事务外重新向量化。
- 回滚到 `013_marketing` 会恢复 `vector(1536)` 并再次清理派生切片；不得截断、填零或投影伪造维度兼容。
- 新旧 Provider 不得在同一向量字段混写。

## 7. 运行与评测

- 启动：CPU 使用 `docker-compose -f docker-compose.yml -f docker-compose.ai.yml --profile ai up -d --build`；GPU 再叠加 `docker-compose.gpu.yml`。AI 覆盖文件负责让 backend/jobs 等待模型健康，不得绕过该门禁单独启用 Worker。
- RTX 4060 8 GB 真实冒烟中，两模型 FP16 常驻约 2922 MiB；该数字只代表单样本冒烟，不代表并发容量结论。
- 正式门禁：Dense Recall@20、Rerank Recall@5、MRR、nDCG@5、无答案转人工率、引用合法率、P95、吞吐、冷启动和 OOM。
- Fake Provider 只用于确定性测试；正式 AI 质量与性能报告由测试工程师生成。
