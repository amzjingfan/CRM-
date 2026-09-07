# BGE 混合检索与重排序实施记录

## 1. 基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase2 |
| 任务编号 | P2-03；关联 P2-07 |
| 模块编号 | M04 |
| 主责 Agent | AIAgent开发工程师Agent |
| 协作 Agent | 架构师Agent、全栈开发工程师Agent、测试工程师Agent |
| 实施状态 | 部分完成 |
| 开始日期 | 2026-08-21 |
| 完成日期 | 未完成；正式质量与容量门禁待测试工程师验证 |
| 代码位置 | `CRM智能聊天系统/` |

## 2. 需求与依据

- 产品需求：`共享记忆文档/CRM智能聊天系统产品需求文档.md` 中 FAQ 智能回复与多店铺隔离要求。
- 接口依据：本任务不新增公开 HTTP API，继续使用 P2-03/P2-07 内部 Agent 契约。
- 架构依据：`架构师/ADR-002-AI-采用本地BGE检索模型-v1.0.md`、`架构师/ARCH-001-SYS-系统总体架构设计-v1.2.md`、`架构师/ARCH-003-DATA-数据库与向量库初版设计-v1.1.md`。
- 任务依据：`共享记忆文档/开发任务拆解（按人天分配）.md` 中 P2-03 和 P2-07。
- 验收依据：AI Agent Phase 2 RAG 计划中的店铺隔离、Top 5、引用合法、保守转人工和可观测性要求。
- 代码规范：`共享记忆文档/代码编写手册.md`。

## 3. 目标、范围与非目标

### 3.1 实施目标

- 将 FAQ Embedding 从 OpenAI 1536 维切换为本地 BGE-M3 1024 维。
- 使用 pgvector Dense 与 PostgreSQL `pg_trgm` 词法双路召回，经 RRF 融合后由 `bge-reranker-large` 重排序。
- 保持 Agent 不直接访问平台、不发送消息、不执行工具和不跨店铺检索的既有边界。

### 3.2 实施范围

- 本地 Embedding/Reranker 契约、单实例内部模型服务、Compose CPU/GPU 运行面。
- 数据库迁移 `014_bge_hybrid`、向量化 Worker、知识库混合检索端口和 LangGraph RAG 节点。
- 配置、离线评测脚本、自动化测试、架构与交接文档。

### 3.3 非目标

- 不新增 `/suggest`、SSE 或其他公开 API。
- 不执行平台发送、订单工具或营销动作。
- 不把 Reranker 原始 logit 当作 0 到 1 的业务置信度。
- 不在本记录中生成正式测试报告、AI 质量结论或生产验收结论。

## 4. 实施前确认

- [x] 已读取共享记忆文档文件清单。
- [x] 已读取相关 PRD、接口、任务拆解和验收标准。
- [x] 已读取代码编写手册和适用的 Agent、Python、PostgreSQL、TDD、安全与可观测性 Skill。
- [x] 已确认 Phase2、P2-03/P2-07、M04 和主责 Agent。
- [x] 已确认架构师批准 ADR-002-AI，依赖、风险和验收方式明确。

## 5. 实施方案

### 5.1 方案说明

```text
FAQ 发布/更新
→ Jobs Worker 原子认领 pending 文档
→ 内部模型服务生成 BGE-M3 1024 维 Dense 向量
→ 按文档版本安全替换 knowledge_chunks

用户查询
→ BGE-M3 查询向量
→ pgvector Dense Top 20 + pg_trgm Lexical Top 20
→ RRF(k=60) 融合候选 Top 20
→ bge-reranker-large Cross-Encoder 重排序
→ 临时知识门禁
→ 最终 Top 5 引用进入 LangGraph
```

模型服务只读挂载固定 Revision 模型，使用内部 Bearer Token、离线加载和单 Worker。BGE-M3 使用 CLS Pooling 与 L2 归一化；Reranker 原始分数仅确定顺序。当前临时门禁为 Dense cosine 不低于 0.45 或 trigram similarity 不低于 0.10，正式值必须由评测集重新标定。

### 5.2 依赖关系

- 前置依赖：P2-03/P2-07 历史实现、Phase3 知识库端口、已下载并校验的固定 BGE 模型资产、架构师确认 ADR-002-AI。
- 后续依赖：测试工程师执行检索质量与容量测试；全栈工程师后续提供受认证的建议 API/SSE；AI 工程师根据正式结果标定阈值。

### 5.3 风险控制

| 风险 | 影响 | 应对措施 |
| --- | --- | --- |
| 1536 与 1024 维不兼容 | 新旧向量混写或查询失败 | 迁移清理可再生旧切片、原子变更维度、发布 FAQ 重置为 pending |
| Reranker 分数误用 | 错误提高自动回复置信度 | 原始 logit 只排序，最终置信度继续使用 Dense cosine 与既有安全分数 |
| 模型服务泄密或越权 | 模型路径、Token 或业务数据暴露 | 内部 Bearer Token、SecretStr、稳定错误、日志不记录正文和密钥 |
| 多进程重复占用 GPU | OOM 和延迟抖动 | 独立单实例模型服务，backend/jobs 只调用内部 HTTP |
| 阈值未经正式标定 | 误拒答或低质量建议 | AI 默认关闭，临时门禁明确标记，生产开放依赖测试工程师结论 |

## 6. 实际变更

### 6.1 文件变更

| 文件路径 | 变更类型 | 变更说明 | 负责 Agent |
| --- | --- | --- | --- |
| `backend/app/retrieval_model_service/` | 新增 | 本地 BGE Embedding/Reranker 内部服务、离线加载和健康检查 | AIAgent开发工程师Agent |
| `backend/app/agent/retrieval_models.py` | 新增 | 重排序契约、结果类型、稳定错误和内部客户端 | AIAgent开发工程师Agent |
| `backend/app/agent/embeddings.py` | 修改 | 新增 LocalBgeEmbeddingProvider 并切换默认生产 Provider | AIAgent开发工程师Agent |
| `backend/app/agent/rag.py`、`factory.py`、`workflow.py` | 修改 | Dense/词法/RRF/重排序编排、门禁和故障转人工 | AIAgent开发工程师Agent |
| `backend/app/agent/schemas.py`、`repository.py` | 修改 | 返回和运行摘要增加安全的检索模型元数据 | AIAgent开发工程师Agent |
| `backend/app/knowledge_base/models.py`、`schemas.py`、`vector_port.py` | 修改 | 1024 维约束、混合检索、RRF 分数和租户/版本门禁 | AIAgent开发工程师Agent |
| `backend/app/shared/config/settings.py` | 修改 | 本地模型服务、候选数、RRF、门禁和设备配置 | AIAgent开发工程师Agent |
| `backend/migrations/versions/014_switch_knowledge_vectors_to_bge_hybrid.py` | 新增 | 1536→1024、HNSW 重建、pg_trgm GIN、文档待回填 | AIAgent开发工程师Agent |
| `backend/scripts/verify_bge_hybrid_runtime.py` | 新增 | PostgreSQL 门禁、混合检索和并发认领运行验证 | AIAgent开发工程师Agent |
| `backend/scripts/evaluate_rag.py` | 修改 | 输出 Dense Recall@20、Rerank Recall@5、MRR、nDCG 和拒判指标 | AIAgent开发工程师Agent |
| `backend/tests/test_local_retrieval_models.py`、`test_retrieval_model_service.py` | 新增 | 本地模型客户端、服务鉴权、维度、有限值和排序测试 | AIAgent开发工程师Agent |
| `backend/tests/test_agent_rag.py` 等测试 | 修改 | 混合检索、重排序、质量门禁和 1024 维回归 | AIAgent开发工程师Agent |
| `backend/pyproject.toml`、`backend/uv.lock` | 修改 | 锁定 retrieval-model 可选依赖 | AIAgent开发工程师Agent |
| `Dockerfile.model-service`、`docker-compose.gpu.yml` | 新增 | 单实例模型镜像和 NVIDIA GPU 覆盖配置 | AIAgent开发工程师Agent |
| `docker-compose.yml`、`.env.example` | 修改 | `ai` Profile、只读模型挂载、内部 Token 和 BGE 配置 | AIAgent开发工程师Agent |
| `README.md`、`deploy/models/README.md`、`model-manifest.json` | 修改 | 当前接入状态、启动方式、固定资产和质量门禁 | AIAgent开发工程师Agent |
| `AI agent 开发工程师/AI-002-...-v1.2.md`、`AI-003-...-v1.0.md` | 新增/修改 | 当前 RAG 规范和模型下载、校验、启用指南 | AIAgent开发工程师Agent |
| `架构师/ADR-002-AI-...`、`ARCH-001-...-v1.2.md`、`ARCH-003-...-v1.1.md` | 修改 | 已确认的模型服务、混合检索和数据库设计 | 架构师Agent、AIAgent开发工程师Agent |

### 6.2 接口、数据和配置变更

- API：不新增公开 API；内部模型服务新增 `/internal/v1/embeddings`、`/internal/v1/rerank` 和健康检查。
- 数据库：新增可逆迁移 `014_bge_hybrid`；`knowledge_chunks.embedding` 改为 `vector(1024)`，重建 HNSW cosine 索引并新增 `content gin_trgm_ops` 索引。
- 配置项：Embedding 默认 Provider/模型/维度改为 `local_bge`、`BAAI/bge-m3`、1024；新增模型服务地址/Token、模型路径/Revision/哈希、设备/FP16、Reranker、Dense/词法候选数、RRF 和临时门禁配置。所有 AI 功能默认关闭。
- AI：BGE-M3 Dense Top 20 + pg_trgm Top 20 → RRF(k=60) Top 20 → `bge-reranker-large` Top 5；Reranker 不直接进入最终置信度。

### 6.3 关键实现说明

- 迁移不转换无意义的旧向量；只删除可重新生成的 chunk，保留 FAQ 正文并让发布文档重新排队。
- Dense 与词法 SQL 都重复店铺、发布状态、ready 状态、软删除和当前版本门禁；词法通道使用 `%` 运算符命中 trigram GIN 候选索引。
- Worker 外部推理期间不持有数据库长事务，回写前再次校验文档版本，避免旧结果覆盖新正文。
- 模型服务禁用 `trust_remote_code`，按固定 SHA-256 可选强校验权重，错误响应不返回模型正文、路径、Token 或底层堆栈。
- LangGraph 在 Embedding/Reranker 配置、超时、输出异常或无合格知识时保守转人工，不创建业务消息。

## 7. 验证记录

| 验证项 | 命令或方法 | 预期结果 | 实际结果 | 状态 |
| --- | --- | --- | --- | --- |
| 锁文件 | `uv lock --check` | 锁文件一致 | 117 个包解析一致 | 通过 |
| Ruff | `uv run ruff check app migrations scripts tests` | 无静态错误 | All checks passed | 通过 |
| 格式 | `uv run ruff format --check app migrations scripts tests` | 全部已格式化 | 152 files already formatted | 通过 |
| mypy | `uv run mypy app scripts` | 无类型错误 | 115 个源文件无问题 | 通过 |
| 全量 pytest | `uv run pytest` | 新增功能和既有回归通过 | 78 passed，2 skipped；跳过项为需显式 PostgreSQL URL 的宿主集成测试 | 通过 |
| Compose 基础配置 | `docker-compose config --services` | 基础服务可解析 | 7 个服务可解析 | 通过 |
| Compose AI 配置 | `docker-compose -f docker-compose.yml -f docker-compose.gpu.yml --profile ai config --services` | 模型服务可解析 | 包含 `retrieval-model-service` 的 8 个服务可解析 | 通过 |
| 迁移可逆性 | `alembic upgrade 014`、`downgrade 013`、重新 `upgrade 014` | 升级、回滚、重升均成功 | 三步均成功；执行前无 FAQ/chunk 业务数据 | 通过 |
| 当前迁移 head | `docker-compose exec -T backend alembic current` | `014_bge_hybrid` | `014_bge_hybrid (head)` | 通过 |
| PostgreSQL 运行链路 | `docker-compose exec -T backend python scripts/verify_bge_hybrid_runtime.py` | 隔离、状态/版本门禁、混合检索和并发认领通过 | `BGE hybrid runtime verification passed`，脚本已清理临时数据 | 通过 |
| 模型镜像 | `docker-compose ... build retrieval-model-service` | 镜像可构建并离线加载固定模型 | 构建成功，缓存重建成功 | 通过 |
| 真实模型冒烟 | 内部 Embedding/Rerank 请求 | 1024 维有限向量且相关文档优先 | 1024 维、全部有限；退货政策排在尺码指南之前 | 通过 |
| GPU 冒烟 | RTX 4060 8 GB 双模型常驻 | 无 OOM | 模型服务约占用 2922 MiB；仅为冒烟值 | 通过 |
| 正式质量/容量评测 | 测试工程师评测 | 达到 Recall、拒判、引用、P95 和并发门禁 | 尚未执行 | 未执行 |

宿主 Windows 上直接运行 PostgreSQL asyncpg 集成测试曾出现连接被远端重置，因此没有用该失败冒充通过；相同业务门禁已改在项目 backend 容器内连接实际 PostgreSQL/pgvector 完成运行验证。

## 8. 实施结果

- 完成项：本地 BGE Provider、Reranker、单实例模型服务、1024 维可逆迁移、混合召回、RRF、最终 Top 5、Worker 接入、LangGraph 接入、运行追踪、单元/回归/容器运行验证和文档同步。
- 未完成项：正式 Dense Recall@20、Rerank Recall@5、MRR、nDCG、无答案转人工、引用合法、P95、吞吐、冷启动、并发和 OOM 评测；生产阈值标定；现有发布 FAQ 的真实业务全量回填（当前开发库无待回填正文）。
- 与原方案差异：混合检索词法通道采用 PostgreSQL `pg_trgm`，暂不启用 BGE-M3 Sparse/ColBERT；基础 Compose 保留 CPU 路径，GPU 通过覆盖文件显式启用。
- 当前状态：部分完成；工程实现和开发运行验证已完成，AI 默认关闭，生产验收依赖测试工程师独立质量与容量结论。

## 9. 遗留问题与风险

| 编号 | 问题或风险 | 优先级 | 负责 Agent | 计划处理 Phase/任务 |
| --- | --- | --- | --- | --- |
| R-BGE-101 | 正式检索质量、拒判率和引用合法率尚未验证 | P0 | 测试工程师Agent、AIAgent开发工程师Agent | Phase2/P2-03 质量评测 |
| R-BGE-102 | Dense 0.45、词法 0.10 为临时门禁 | P0 | AIAgent开发工程师Agent、测试工程师Agent | 质量评测后标定 |
| R-BGE-103 | P95、吞吐、冷启动、并发和 OOM 尚无正式结论 | P0 | 测试工程师Agent、全栈开发工程师Agent | 部署容量测试 |
| R-BGE-104 | BGE-M3 使用官方 Pickle 权重格式 | P1 | AIAgent开发工程师Agent、运维负责人 | 持续供应链校验 |
| R-BGE-105 | 宿主 Windows asyncpg 集成连接不稳定 | P2 | 全栈开发工程师Agent | 测试环境治理 |

## 10. 交接事项

- 交接给：测试工程师Agent、全栈开发工程师Agent、架构师Agent。
- 后续任务：测试工程师执行 P2-03 检索质量与 GPU 容量报告；AI 工程师按报告标定门禁；全栈工程师在后续建议 API/SSE 中调用内部 Agent 契约。
- 必须注意：先迁移 014，再启动向量化回填；没有 `ready + current version` 的 FAQ 不得参与检索。禁止旧 1536 维写入、禁止绕过模型服务重复加载模型、禁止把 Reranker logit 当置信度、禁止在正式评测前启用生产自动回复。

## 11. 文档同步

- [x] 已同步接口变化：无公开 API，已记录内部模型服务契约。
- [x] 已同步架构决策：ADR-002-AI 状态为已确认并实施。
- [x] 已同步任务状态：新增 P2-03 后续实施记录并保留历史记录。
- [x] 已通知测试工程师需要覆盖质量、隔离、性能、故障和安全范围。
- [x] 测试报告索引保持不变，待测试工程师生成正式报告后更新。
