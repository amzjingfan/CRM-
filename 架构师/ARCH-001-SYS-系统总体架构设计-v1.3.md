# CRM 智能聊天系统总体架构设计 v1.3 增量说明

状态：已确认

## 1. 版本关系

本文件继承 `ARCH-001-SYS-系统总体架构设计-v1.2.md` 的全部未变更内容，并同步 BGE 依赖安全升级、正式质量/容量门禁、Phase 3 业务工具安全接管和 M03 第六次复测的当前结论。v1.2 已标记为历史版本并保留追溯。

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
- RAG 使用 Dense/词法双路召回、RRF 融合候选 Top 20，再重排序为最终 Top 5。
- 模型服务错误、超时、OOM 或无结果时，Agent 强制转人工，不生成无依据答案。

## 3. 模块边界

- `knowledge_base` 负责店铺隔离、发布状态、版本、向量持久化和向量化运行面。
- `agent` 负责检索编排、重排序契约、引用、动作决策和受控工具选择。
- `retrieval_model_service` 只负责模型加载、Embedding 和 Rerank，不访问业务数据库。
- `tools` 负责业务动作的权限、店铺范围、参数、幂等、超时、脱敏和审计；Agent 不直接调用第三方平台或写业务表。
- 全栈运行面使用基础 Compose + AI 启用覆盖文件 + 可选 GPU 覆盖文件；AI Agent 工程师负责模型契约、推理、融合、重排序和 Agent 工具编排。

## 4. 当前验收结论

- BGE-M3 正式质量门禁已通过，Dense 门禁由暂定值校准为 `0.52`；词法门禁保持 `0.10`。
- 模型服务 50 并发、冷启动、显存和 OOM 容量门禁已通过；模型、数据分布、GPU 或候选参数变化后必须重新评测。
- 七个白名单工具的可信上下文、写批准、店铺隔离、幂等、审计、失败关闭和人工接管已通过独立测试。
- Phase 3 M03 在当前契约级 Mock 范围通过第六次独立复测；该结论不代表真实第三方平台写操作或公开 AI 回复已经验收。
- 权威测试结论分别见：
  - `测试工程师/Phase2-P2-03-P2-07-AIAgent开发工程师Agent-M04-BGE混合检索与重排序-AI评测-001.md`；
  - `测试工程师/Phase4-P4-10-AIAgent开发工程师Agent-M04-BGE模型服务-性能测试-001.md`；
  - `测试工程师/Phase3-P3-00-AIAgent开发工程师Agent-M04-业务工具与安全接管-综合测试-001.md`；
  - `测试工程师/Phase3-P3-00-全栈开发工程师Agent-M03-知识库、业务工具与主动营销-综合测试-006.md`。

## 5. 当前实现与后续门禁

- BGE 结构迁移为 `014_bge_hybrid`；当前运行 head 为 `015_vector_ops`，新增向量化队列和店铺状态汇总索引，不改变向量结构和检索算法。
- 模型服务使用 Docker GPU 单实例、只读模型挂载、离线加载和内部 Bearer Token；基础 Compose 可以显式禁用模型能力。
- Reranker 原始分数只用于排序；业务 `retrieval_score` 使用 Dense cosine，当前 Dense/词法门禁为 `0.52/0.10`。
- `docker-compose.ai.yml` 让 backend/jobs 依赖模型服务健康状态；配置启动校验固定 `local_bge + BGE-M3 + 1024` 和至少 32 字符的内部 Token，防止 Worker 在模型不可用时抢跑回填。
- `/v1/health/ready` 检查 PostgreSQL、Redis、MinIO，并在 Embedding 启用时检查模型服务的模型 ID 和向量维度契约；知识库运营页可查看店铺级队列汇总并重试 `published + failed` 条目。
- 当前锁定依赖已完成安全升级；测试工程师对 123 个锁定包执行 `uv audit --locked`，未发现已知漏洞或不良状态。原依赖安全缺陷 `DEF-P3-013` 已关闭。
- 未来升级 PyTorch、Transformers、模型权重或 CUDA 运行时，仍必须重新执行依赖审计、离线加载安全检查、AI 质量回归和容量测试，不能沿用本次结论。

## 6. 仍未完成的生产边界

- TikTok Shop、Shopee、Amazon 真实平台写操作联调。
- 公开 `/suggest`、SSE 自动回复和 AI 营销文案生产验收。
- 真实平台凭证、审核权限、沙箱/生产环境和线上数据漂移验证。

