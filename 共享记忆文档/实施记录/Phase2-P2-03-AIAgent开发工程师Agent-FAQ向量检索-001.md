# FAQ 向量检索实施记录

## 1. 基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase2 |
| 任务编号 | P2-03 |
| 模块编号 | M04 |
| 主责 Agent | AIAgent开发工程师Agent |
| 协作 Agent | 全栈开发工程师Agent、架构师Agent、测试工程师Agent |
| 实施状态 | 部分完成 |
| 开始日期 | 2026-08-20 |
| 完成日期 | 未完成 |
| 代码位置 | `CRM智能聊天系统/` |

## 2. 需求与依据

- 产品需求：`共享记忆文档/智能客服平台 — 产品需求文档（PRD）V2.0.md` 中 AI 智能问答和 FAQ C 层。
- 接口依据：`共享记忆文档/智能客服平台 — 管理端接口文档.md` 第 11.4 节。
- 架构依据：`架构师/ARCH-001-SYS-系统总体架构设计-v1.1.md`、`ARCH-003-DATA-数据库与向量库初版设计-v1.0.md`。
- 任务依据：`共享记忆文档/开发任务拆解（按人天分配）.md` 中 P2-03。
- 验收依据：`共享记忆文档/MVP范围与验收标准.md` 中 FAQ Top-5、分数、来源和无结果处理。
- 代码规范：`共享记忆文档/代码编写手册.md`。

## 3. 目标、范围与非目标

### 3.1 实施目标

- 使用 OpenAI `text-embedding-3-small` 生成 1536 维 FAQ 向量。
- 使用 pgvector cosine 检索当前店铺 Top 5，并强制发布、ready 和当前版本门禁。
- 通过 Jobs Worker 完成原子认领、切分、向量化、版本安全替换和失败状态。

### 3.2 实施范围

- Embedding Provider、错误码、批处理和三次重试。
- FAQ 800 Token/80 Token 重叠切分。
- 知识库向量写入端口、查询端口和 Worker 接入。
- 50 条有目标 FAQ、20 条无答案的版本化 RAG 数据集和 live 评测命令。

### 3.3 非目标

- 不新增数据库迁移，不更改 `vector(1536)` 和 HNSW 索引。
- 不新增公开 HTTP API，不修改前端，不执行平台发送。
- Fake Embedding 不作为正式评测通过证据。

## 4. 实施前确认

- [x] 已读取共享记忆文档文件清单。
- [x] 已读取 PRD、接口、任务拆解、验收、架构和交接记录。
- [x] 已读取代码编写手册和 Agent/Python/PostgreSQL/TDD/安全/可观测性 Skill。
- [x] 已确认模块编号为 M04，数据库 head 为 013。
- [x] 已确认 AI 只能通过知识库内部端口访问向量数据。

## 5. 实施方案

### 5.1 方案说明

Jobs Worker 使用 `FOR UPDATE SKIP LOCKED` 认领 `published + pending` FAQ 并立即提交 `processing`。外部 Embedding 发生在事务之外。每片重复问题前缀；向量数量、维度和有限数值通过后，只在文档版本和状态仍一致时原子替换切片并标记 `ready`。

查询先脱敏，再生成查询向量。知识端口按 `store_id`、`published`、`ready`、当前版本和未删除条件执行 pgvector cosine Top-5，默认阈值 0.70、上下文预算 6000 Token。

### 5.2 依赖关系

- 前置依赖：P2-01/P2-02、Phase3 知识库表和向量端口、迁移 011。
- 后续依赖：P2-07 Agent 编排、全栈 `/suggest` 接入、测试工程师真实 RAG 评测。

### 5.3 风险控制

| 风险 | 影响 | 应对措施 |
| --- | --- | --- |
| 跨店铺向量召回 | 数据泄露 | 查询强制同时过滤 chunk 和 document 的 `store_id` |
| 旧任务覆盖新版本 | 回答使用过期内容 | 替换和失败更新都校验版本与 `processing` 状态 |
| Worker 并发重复处理 | 成本和重复写入 | `FOR UPDATE SKIP LOCKED` 原子认领 |
| 非有限向量进入数据库 | pgvector 查询异常 | Provider 和 `VectorChunkInput` 双重校验 |
| tokenizer 首次联网 | Worker 首次任务失败 | Docker 构建阶段预热 `cl100k_base` 缓存 |
| 本地密钥曾有暴露风险 | 凭证泄露 | 真实 live gate 前必须轮换；报告不记录密钥 |

## 6. 实际变更

### 6.1 文件变更

| 文件路径 | 变更类型 | 变更说明 | 负责 Agent |
| --- | --- | --- | --- |
| `backend/app/agent/embeddings.py` | 新增 | OpenAI Embedding、错误映射和批处理重试 | AIAgent开发工程师Agent |
| `backend/app/agent/chunking.py` | 新增 | FAQ Token 切分和问题前缀 | AIAgent开发工程师Agent |
| `backend/app/agent/vectorization.py` | 新增 | 向量化周期编排 | AIAgent开发工程师Agent |
| `backend/app/agent/rag.py` | 新增 | 查询脱敏、Embedding 和上下文预算 | AIAgent开发工程师Agent |
| `backend/app/knowledge_base/vector_port.py` | 修改 | 原子认领、版本安全替换、pgvector Top-5 | AIAgent开发工程师Agent |
| `backend/app/jobs/worker.py` | 修改 | 接入默认关闭的 FAQ 向量化周期 | AIAgent开发工程师Agent |
| `backend/evals/faq-rag-v1.0.0.jsonl` | 新增 | 70 条版本化 RAG 评测样本 | AIAgent开发工程师Agent |
| `backend/scripts/evaluate_rag.py` | 新增 | 真实 Embedding Recall@5 live gate | AIAgent开发工程师Agent |

### 6.2 接口、数据和配置变更

- API：不新增 HTTP 接口。
- 数据库：不新增迁移；继续使用迁移 011 的 `vector(1536)` 和 HNSW 索引。
- 配置项：新增 `EMBEDDING_*`、`RAG_TOP_K`、`RAG_MIN_SCORE`、`RAG_MAX_CONTEXT_TOKENS`；默认关闭。
- AI：Embedding 为 OpenAI `text-embedding-3-small`；默认 Top 5、最低分 0.70。

### 6.3 关键实现说明

- SDK 重试关闭，应用最多重试三次；认证、权限、参数和配置错误立即失败。
- 向量化单文档失败不终止同批其他文档，日志只记录实体 ID、版本和异常类型。
- 无有效命中时返回空检索结果，由 Agent 工作流转人工，不生成猜测答案。

## 7. 验证记录

| 验证项 | 命令或方法 | 预期结果 | 实际结果 | 状态 |
| --- | --- | --- | --- | --- |
| 自动化回归 | `uv run pytest -q` | 新旧测试通过 | 64 passed，2 个 PostgreSQL 用例默认跳过 | 通过 |
| pgvector 集成 | 隔离数据库执行集成测试 | 门禁和并发认领通过 | 2 passed，测试库已删除 | 通过 |
| Ruff | `uv run ruff check ...` | 无问题 | All checks passed | 通过 |
| 格式 | `uv run ruff format --check ...` | 无格式差异 | 144 files formatted | 通过 |
| mypy | `uv run mypy app scripts` | 严格类型通过 | 110 个源文件无问题 | 通过 |
| 依赖审计 | `uv audit --locked` | 无已知漏洞 | 85 个包无已知漏洞 | 通过 |
| 镜像构建 | `docker-compose build backend jobs` | 依赖和 tokenizer 可构建 | backend/jobs 构建成功 | 通过 |
| Worker 启动 | 重建 jobs 并检查状态 | 进程持续运行 | 容器 Up，无异常日志 | 通过 |
| 真实 RAG 评测 | `scripts.evaluate_rag` | Recall@5 等达到门禁 | 密钥轮换未确认，未执行 | 未执行 |

## 8. 实施结果

- 完成项：生产代码、锁文件、配置、向量化 Worker、pgvector 检索、确定性测试、集成测试、评测集和 live 命令。
- 未完成项：使用轮换后真实 OpenAI Key 执行 70 条 live RAG 评测。
- 与原方案差异：LangGraph 实际锁定为 1.2.11；数据库 head 保持 013。
- 当前状态：部分完成；工程实现和数据库集成通过，正式真实模型评测待测试工程师复核。

## 9. 遗留问题与风险

| 编号 | 问题或风险 | 优先级 | 负责 Agent | 计划处理 Phase/任务 |
| --- | --- | --- | --- | --- |
| R-RAG-001 | 真实 OpenAI RAG live gate 未执行 | P0 | AIAgent开发工程师Agent、测试工程师Agent | Phase2/P2-03 |
| R-SEC-001 | 本地 DeepSeek Key 轮换状态无法由代码验证 | P0 | 环境维护者 | Phase2/P2-03 前置门禁 |
| R-RAG-002 | 0.70 阈值需要真实语料校准 | P1 | AIAgent开发工程师Agent | Phase2/P2-03 复测 |

## 10. 交接事项

- 交接给：测试工程师Agent、全栈开发工程师Agent。
- 后续任务：测试工程师使用真实轮换密钥执行 live gate；全栈通过内部 Agent 契约接入建议接口。
- 必须注意：不得把 Fake Provider 结果写成正式 AI 评测通过；不得绕过知识端口查询向量。

## 11. 文档同步

- [x] 已同步内部接口变化。
- [x] 已同步 AI 工作流规范。
- [x] 已同步实施记录索引。
- [x] 已通知测试工程师需要覆盖的范围。
- [ ] 正式测试报告索引待测试工程师完成 live gate 后更新。

## 12. 后续方案说明

2026-08-21 已完成 BGE-M3 与 `bge-reranker-large` 本地模型资产下载和登记，详见 `PhaseX-PX-00-AIAgent开发工程师Agent-BGE本地模型资产登记-001.md`。本记录仍准确描述 OpenAI 1536 维历史实现；本地 BGE 尚未启用，后续需要 1024 维迁移和重新评测。

### 13.2 本地 BGE 接入后续记录

2026-08-21 架构师确认 ADR-002-AI 后，P2-03 已由后续实施记录 `Phase2-P2-03-AIAgent开发工程师Agent-BGE混合检索与重排序-002.md` 升级：Embedding 改为本地 BGE-M3 1024 维，新增 `pg_trgm` 词法召回、RRF 候选融合与 `bge-reranker-large` 最终 Top 5 重排序。本文件作为 OpenAI 1536 维历史实现证据保留，不再代表当前运行时契约。
