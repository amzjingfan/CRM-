# CRM 智能聊天系统数据库与向量库设计 v1.1 增量说明

状态：已确认并实施

## 1. 版本关系

本文件继承 `ARCH-003-DATA-数据库与向量库初版设计-v1.0.md` 的全部未变更内容，说明当前 BGE-M3 1024 维和混合检索结构。迁移 `014_bge_hybrid` 已实施；v1.0 及迁移 011 的 1536 维设计仅作为历史基线。

## 2. 目标结构

```sql
embedding vector(1024) NOT NULL
```

目标索引继续使用 pgvector HNSW cosine：

```sql
CREATE INDEX idx_knowledge_chunks_embedding_hnsw
ON knowledge_chunks
USING hnsw (embedding vector_cosine_ops);
```

词法召回使用 `pg_trgm`：

```sql
CREATE INDEX idx_knowledge_chunks_content_trgm
ON knowledge_chunks
USING gin (content gin_trgm_ops);
```

## 3. 迁移原则

- 1536 维 OpenAI 向量不能转换或填充为有效的 1024 维 BGE-M3 向量。
- 结构迁移只负责字段、约束、索引和状态；模型回填由 Jobs Worker 在迁移事务外执行。
- 所有已发布文档重新标记为 `pending`，旧 chunk 不得参与新 Provider 检索。
- 只有 BGE-M3 当前版本切片全部写入并标记 `ready` 后，文档才能进入正式检索。
- 迁移和回滚都必须保留店铺隔离、文档版本和软删除过滤。

## 4. 推荐迁移序列

1. `014_bge_hybrid` 清理与 1536 维绑定的旧 chunk，保留 FAQ 正文并把已发布文档统一重置为 `pending`。
2. 将字段改为 `vector(1024)`，重建 HNSW 索引并创建 `pg_trgm` GIN 索引。
3. Jobs Worker 通过内部 BGE 服务在事务外回填，按文档版本安全替换 chunk。
4. 查询分别取得 Dense 与词法候选，RRF 仅按排名融合，不在数据库保存 Reranker 分数。
5. 迁移已完成升级、回滚和重新升级；正式召回质量和生产窗口仍由测试工程师与架构师验收。
6. `015_vector_ops` 增加 `vectorization_status, updated_at, id` 队列索引和 `store_id, vectorization_status` 汇总索引；二者只覆盖未删除的已发布 FAQ，回滚不修改业务数据。

## 5. 重排序数据边界

Reranker 不新增数据库向量字段。候选片段内容只在单次请求内送入本地模型服务，运行记录只保存候选 ID、最终引用 ID、模型 Revision、耗时和稳定错误码，不保存完整 FAQ 正文或原始模型输出。

## 6. 当前状态

数据库 head 为 `015_vector_ops`，`knowledge_chunks.embedding` 为 `vector(1024)`，HNSW、trigram GIN、向量化队列和店铺状态汇总索引均已创建。`015` 已完成 `014→015→014→015` 可逆性验证且不修改业务正文或向量数据。
