# CRM 智能聊天系统 FAQ RAG 与单 Agent 工作流规范 v1.4

## 1. 文档信息

| 项目 | 内容 |
| --- | --- |
| 文档编号 | AI-002-RAG |
| 版本 | v1.4 |
| 模块编号 | M04 |
| 主责 Agent | AIAgent开发工程师Agent |
| 状态 | 已实施，已通过本地模型质量与 RTX 4060 容量门禁 |
| 更新日期 | 2026-08-21 |
| 基础版本 | `AI-002-RAG-FAQ检索与Agent工作流规范-v1.3.md` |

## 2. 模型、依赖与数据基线

```text
embedding: BAAI/bge-m3@5617a9f61b028005a4858fdac845db406aefb181
dimensions: 1024
reranker: BAAI/bge-reranker-large@55611d7bca2a7133960a6d3b71e083071bbfc312
torch: 2.13.0
transformers: 5.5.4
database head: 015_vector_ops（BGE 结构迁移为 014_bge_hybrid）
dense top_k: 20
lexical top_k: 20
RRF k: 60
candidate top_k: 20
final top_k: 5
dense min score: 0.52
lexical min score: 0.10
```

模型服务依赖由 `backend/uv.lock` 固定。权重从 `deploy/models` 只读挂载，服务强制离线加载、单 Worker、内部 Bearer Token；backend 和 jobs 不安装重型推理依赖。

## 3. 正式检索链路

```text
可信 store_id + 脱敏查询
→ BGE-M3 1024 维 Dense 查询向量
→ pgvector Dense Top 20
  与 pg_trgm Lexical Top 20
→ RRF(k=60) 融合候选 Top 20
→ bge-reranker-large Cross-Encoder
→ Dense >= 0.52 或 Lexical >= 0.10 的最终 Top 5
→ 引用校验、回答生成、安全复核、置信度动作
```

两路数据库查询均强制过滤 `store_id`、`published`、`ready`、未删除和当前文档版本。Reranker 只能调整候选顺序，服务和 Agent 都校验候选 ID 集合完全一致，禁止增加跨租户候选。

## 4. 分数与阈值规则

- `dense_score` 是截断到 0–1 的 cosine 相似度，作为工作流 `retrieval_score`。
- `lexical_score` 是 PostgreSQL trigram similarity，只用于词法门禁和观测。
- `fusion_score` 是归一化 RRF 分数，只用于候选融合顺序。
- `reranker_score` 是未归一化 Cross-Encoder logit，只用于最终排序，不作为概率或业务置信度。
- Dense 正式门禁为 `0.52`。该值由 `faq-rag-v1.0.0.jsonl` 的 50 条有答案样本和 20 条拒判样本校准：Recall@5 与无答案转人工率均为 100%。
- `0.52` 只适用于本文固定的模型 Revision、1024 维实现、当前评测集和召回链路；模型、权重、切分、数据分布或查询预处理变化时必须重新评测。
- 同时低于 Dense/词法门禁、无候选、模型不可用、候选 ID 异常或安全复核失败时强制转人工。

## 5. 模型服务与安全

- 公开 CRM API 不暴露模型服务端点；内部端点为 `/internal/v1/embeddings` 和 `/internal/v1/rerank`。
- 推理输入只在请求内存中存在；日志不保存查询、FAQ 正文、向量、Token、模型路径或底层响应。
- 所有模型使用 `local_files_only=True`、`trust_remote_code=False` 加载；禁止运行时在线下载。
- BGE-M3 Pickle 权重必须匹配资产清单 SHA-256；生产启用 `RETRIEVAL_MODEL_VERIFY_HASHES=true`。
- 模型缺失、哈希错误、CUDA 不可用、OOM、超时或输出异常均失败关闭，不回退到无依据生成。
- `AUTO_REPLY_READY` 固定 `send_performed=false`；本规范不授权工具执行或平台发送。

## 6. 数据迁移与回滚

- `014_bge_hybrid` 删除可重新生成的 1536 维旧切片，不删除 FAQ 正文。
- 已发布文档重置为 `pending`，由 Jobs Worker 在迁移事务外重新向量化。
- 回滚到 `013_marketing` 会恢复 `vector(1536)` 并再次清理派生切片；不得截断、填零或投影伪造维度兼容。
- 新旧 Provider 不得在同一向量字段混写。

## 7. 生产门禁基线

2026-08-21 在本地固定模型与 RTX 4060 8 GB 环境完成：

- Dense Recall@20、Rerank Recall@5、MRR、nDCG@5、引用合法率：均为 100%。
- 无答案正确转人工率：100%；阈值由 0.45 校准为 0.52。
- 批量向量化 32、批量重排候选 20：均成功且输出有限。
- 50 并发 Embedding：P95 363.69 ms，吞吐 131.35 RPS，零失败。
- 50 并发 Reranker（每请求 20 候选）：P95 1878.94 ms，吞吐 25.23 RPS，零失败。
- 本地缓存镜像和模型资产条件下，服务进程到健康的冷启动为 24.256 秒。
- 负载峰值显存 3697/8188 MB，未发现 OOM 或致命日志。

权威结论见：

- `测试工程师/Phase2-P2-03-P2-07-AIAgent开发工程师Agent-M04-BGE混合检索与重排序-AI评测-001.md`
- `测试工程师/Phase4-P4-10-AIAgent开发工程师Agent-M04-BGE模型服务-性能测试-001.md`

## 8. 运行约束

- CPU 使用基础 Compose；正式 GPU 性能口径必须叠加 `docker-compose.gpu.yml`，不能用 profile 名替代覆盖文件。
- GPU 模型服务保持单 Worker 和单实例模型加载，避免 8 GB 显存重复常驻。
- 正式上线后持续记录 P95、错误率、显存、无答案率和知识命中漂移；达到扩缩容或质量告警阈值时重新评测。
- Fake Provider 只用于确定性测试，不得作为正式模型质量证据。
