# CRM 智能聊天系统总体架构设计 v1.2 增量说明

状态：已废弃

替代文档：`ARCH-001-SYS-系统总体架构设计-v1.3.md`。本文件保留为依赖安全升级与正式测试结论同步前的历史基线。

## 1. 版本关系

本文件继承 `ARCH-001-SYS-系统总体架构设计-v1.1.md` 的全部未变更内容，定义本地 BGE 检索模型带来的当前生效增量架构。v1.1 保留为历史基线。

## 2. 增量架构

```text
Jobs Worker / Agent Workflow
        ↓ 内部模型契约
单实例 Retrieval Model Service
        ├─ BGE-M3 Dense Embedding
        └─ BGE Reranker Cross-Encoder
        ↓
PostgreSQL
        ├─ pgvector(1024) Dense Top 20
        └─ pg_trgm Lexical Top 20
        ↓ RRF(k=60) 候选 Top 20
BGE Reranker → 最终 Top 5
```

- 模型服务是 AI 模块内部运行组件，不新增公开 HTTP API。
- backend、jobs 不直接加载权重，避免 8 GB 显存环境出现重复常驻。
- 模型目录从 `deploy/models` 只读挂载；应用镜像不包含模型权重。
- RAG 从单阶段 Top 5 改为 Dense/词法双路召回、RRF 融合候选 Top 20，再重排序为最终 Top 5。
- 模型服务错误、超时、OOM 或无结果时，Agent 强制转人工，不生成无依据答案。

## 3. 模块边界

- `knowledge_base` 继续负责店铺隔离、发布状态、版本和向量持久化。
- `agent` 继续负责检索编排、重排序契约、引用和动作决策。
- `retrieval_model_service` 只负责模型加载、Embedding 和 Rerank，不访问业务数据库。
- 全栈运行面使用基础 Compose + AI 启用覆盖文件 + 可选 GPU 覆盖文件；AI Agent 工程师负责模型契约、推理、融合与重排序逻辑。

## 4. 验收变化

- 增加模型资产哈希、离线加载、GPU 容量、候选召回和重排序质量测试。
- 原 Top 5 Recall 指标拆分为 Dense Recall@20 和重排序后 Recall@5。
- 本版本不改变平台发送、工具调用、人工接管和 `send_performed=false` 边界。

## 5. 当前实现与后续门禁

- BGE 结构迁移仍为 `014_bge_hybrid`；当前运行 head 为 `015_vector_ops`，新增向量化队列和店铺状态汇总索引，不改变向量结构和检索算法。
- 模型服务使用 Docker GPU 单实例、只读模型挂载、离线加载和内部 Bearer Token；基础 Compose 可回退 CPU。
- Reranker 原始分数只排序；业务 `retrieval_score` 继续使用 Dense cosine，暂定 Dense/词法门禁为 0.45/0.10，生产值待正式评测校准。
- `docker-compose.ai.yml` 让 backend/jobs 依赖模型服务健康状态；配置启动校验固定 `local_bge + BGE-M3 + 1024` 和至少 32 字符的内部 Token，防止 Worker 在模型不可用时抢跑回填。
- `/v1/health/ready` 检查 PostgreSQL、Redis、MinIO，并在 Embedding 启用时检查模型服务的模型 ID 和向量维度契约；知识库运营页可查看店铺级队列汇总并重试 `published + failed` 条目。
- 当前锁定的 PyTorch/Transformers 存在已知安全公告，生产启用继续受依赖升级兼容性和测试工程师安全复核门禁约束。
