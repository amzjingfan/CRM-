# Phase 2 P2-03/P2-07 M04 FAQ 检索与 Agent 工作流第二次综合测试报告

## 1. 测试基本信息

| 项目 | 内容 |
| --- | --- |
| 测试报告编号 | Phase2-P2-03-P2-07-M04-002 |
| Phase | Phase2 |
| 任务编号 | P2-03、P2-07 |
| 模块编号 | M04 |
| 模块名称 | FAQ 检索与 Agent 工作流 |
| 被测主责 Agent | AIAgent开发工程师Agent |
| 被测协作 Agent | 架构师Agent、全栈开发工程师Agent |
| 测试执行 Agent | 测试工程师 Agent |
| 关联修复记录 | `共享记忆文档/实施记录/Phase2-P2-03-AIAgent开发工程师Agent-BGE测试问题修复与状态同步-005.md` |
| 测试类型 | 综合测试、AI评测、集成测试、性能回归、安全测试、回归测试 |
| 执行日期 | 2026-08-21 |
| 测试结论 | 通过 |

## 2. 复测背景与测试依据

### 2.1 复测背景

原报告 `Phase2-P2-03-P2-07-AIAgent开发工程师Agent-M04-FAQ检索与Agent工作流-综合测试-001.md` 基于 OpenAI `text-embedding-3-small` 1536 维方案，遗留：

- DEF-M04-001：真实模型 RAG 质量门禁未执行。
- ENV-M04-002：Windows 主机到 Docker PostgreSQL 的 asyncpg 连接重置。

架构随后通过 ADR-002/ADR-003 将正式向量模型改为本地 `BAAI/bge-m3`，维度改为 1024，并引入 `bge-reranker-large`、Dense/词法混合召回和 RRF 重排序。旧报告保留历史事实，本报告依据当前 BGE-M3 正式契约执行独立复测。

### 2.2 测试依据

- `共享记忆文档/智能客服平台 — 产品需求文档（PRD）V2.0.md`
- `共享记忆文档/智能客服平台 — 管理端接口文档.md`
- `共享记忆文档/开发任务拆解（按人天分配）.md`
- `共享记忆文档/MVP范围与验收标准.md`
- `架构师/ADR-002-AI-采用本地BGE检索模型-v1.0.md`
- `架构师/ADR-003-AI-BGE检索阈值与RTX4060容量基线-v1.0.md`
- `AI agent 开发工程师/AI-002-RAG-FAQ检索与Agent工作流规范-v1.4.md`
- `AI agent 开发工程师/AI-003-MODEL-BGE本地模型下载与校验指南-v1.0.md`
- `共享记忆文档/实施记录/Phase2-P2-03-AIAgent开发工程师Agent-BGE推理依赖安全升级-003.md`
- `共享记忆文档/实施记录/Phase2-P2-03-AIAgent开发工程师Agent-BGE阈值校准与生产门禁-004.md`
- `共享记忆文档/实施记录/Phase2-P2-03-AIAgent开发工程师Agent-BGE测试问题修复与状态同步-005.md`

## 3. 测试范围与非目标

### 3.1 本次覆盖

- BGE-M3 和 BGE Reranker 固定 Revision、权重大小及 SHA-256。
- BGE-M3 1024 维契约、RAG Dense 门禁 `0.52` 和最终 Top 5。
- 70 条版本化 FAQ 数据的真实本地模型质量门禁。
- 50 并发 Embedding 和 Reranker 性能回归、批量 32、候选 20 及 OOM 错误检查。
- 迁移 `001→015`、`015→014→015`、pgvector/pg_trgm、1024 维字段和索引。
- 店铺隔离、发布/ready/当前版本门禁和 `FOR UPDATE SKIP LOCKED` 并发认领。
- LangGraph、运行追踪、引用合法性、低置信度/无答案转人工和 `send_performed=false` 回归。
- 依赖漏洞、非 root、CUDA、离线模型和内部 Token 失败关闭边界。

### 3.2 非目标

- 真实客户线上数据漂移和客服独立解决率。
- 公开 `/suggest`、SSE、平台发送和工具真正执行。
- 真实 TikTok、Shopee、Amazon 平台联调。
- 全新服务器首次下载模型和首次构建镜像耗时。

## 4. 测试环境

| 项目 | 实际环境 |
| --- | --- |
| 操作系统 | Windows，PowerShell，Docker Desktop |
| Python | 3.11.15 |
| 向量模型 | `BAAI/bge-m3@5617a9f61b028005a4858fdac845db406aefb181` |
| 向量维度 | 1024 |
| 重排序模型 | `BAAI/bge-reranker-large@55611d7bca2a7133960a6d3b71e083071bbfc312` |
| GPU | NVIDIA GeForce RTX 4060 |
| 推理模式 | CUDA、FP16、单实例、单 Worker |
| 数据库 | PostgreSQL 16、pgvector、pg_trgm，tmpfs 隔离测试库 |
| 数据库 head | `015_vector_ops` |
| Dense 阈值 | 0.52 |
| 测试数据 | `backend/evals/faq-rag-v1.0.0.jsonl`，50 条有答案 + 20 条拒判 |

本次真实模型服务使用进程级随机临时 Token。Token 未写入 `.env`、代码、证据、日志或报告；测试结束后随容器删除失效。

## 5. 静态质量与自动化回归

| 验证项 | 实际结果 | 状态 |
| --- | --- | --- |
| `uv lock --check` | 124 packages resolved，锁文件一致 | 通过 |
| Ruff check | All checks passed | 通过 |
| Ruff format check | 156 files already formatted | 通过 |
| mypy | 116 个源文件无类型错误 | 通过 |
| 全量 pytest | 88 passed，2 skipped，2 warnings | 通过 |
| BGE/Agent 专项 pytest | 76 passed，1 warning | 通过 |
| `uv audit --locked` | 123 个包无已知漏洞和不良项目状态 | 通过 |
| Base/AI/GPU Compose | 三种组合均可解析 | 通过 |

全量 pytest 中默认跳过的 2 项为未注入隔离 `TEST_DATABASE_URL` 的 PostgreSQL 集成用例。本次随后在 tmpfs 隔离数据库中独立执行并通过，不作为最终跳过结论。

## 6. 模型资产与运行安全

| 检查项 | 实际结果 | 状态 |
| --- | --- | --- |
| BGE-M3 权重大小 | 2,271,145,830 bytes | 通过 |
| BGE-M3 SHA-256 | `b5e0ce3470abf5ef3831aa1bd5553b486803e83251590ab7ff35a117cf6aad38` | 通过 |
| Reranker 权重大小 | 2,239,618,772 bytes | 通过 |
| Reranker SHA-256 | `c5ae4e262c60ed2fb507ec587358285377ec36ee0a2e6da029f0534272b06d36` | 通过 |
| 资产清单门禁 | `production_quality_gate=passed`，报告路径有效 | 通过 |
| 模型服务 UID | 10001，非 root | 通过 |
| CUDA | `cuda=True`，RTX 4060 | 通过 |
| 模型服务健康 | healthy | 通过 |
| OOM/致命日志 | 无匹配 | 通过 |
| 缺失 Token | 服务按配置校验失败关闭 | 通过 |

模型服务首次启动时未提供 32 字符以上 Token，Pydantic 配置校验拒绝启动；注入仅用于本轮的随机临时 Token 后健康启动。该行为证明内部认证配置失败关闭生效，不构成产品缺陷。

## 7. 真实 BGE-M3 AI 质量复测

低敏聚合证据：`测试工程师/evidence/bge-quality-retest-002-20260821.json`。

| 指标 | 门禁 | 本次结果 | 状态 |
| --- | ---: | ---: | --- |
| Dense Recall@20 | ≥90% | 50/50，100% | 通过 |
| Rerank Recall@5 | ≥90% | 50/50，100% | 通过 |
| MRR | ≥0.90 | 1.0000 | 通过 |
| nDCG@5 | ≥0.90 | 1.0000 | 通过 |
| 引用合法率 | 100% | 100% | 通过 |
| 0.52 阈值后有答案 Recall@5 | ≥90% | 100% | 通过 |
| 无答案正确转人工率 | ≥90% | 20/20，100% | 通过 |
| 失败有答案样本 | 0 | 0 | 通过 |
| 失败拒判样本 | 0 | 0 | 通过 |

本次独立网格结果再次确认：`0.52～0.56` 同时保持有答案 Recall@5 和无答案转人工率 100%；`0.57` 起有答案召回开始下降。因此当前默认值 `0.52` 与 ADR-003 一致。

## 8. 并发与性能回归

低敏聚合证据：`测试工程师/evidence/bge-capacity-retest-002-20260821.json`。

| 指标 | Embedding | Reranker（20 候选） | 状态 |
| --- | ---: | ---: | --- |
| 批量结果 | 32 个 1024 维有限向量 | 20 个有限分数 | 通过 |
| 50 并发成功数 | 50/50 | 50/50 | 通过 |
| 失败数 | 0 | 0 | 通过 |
| 吞吐 | 131.70 RPS | 26.34 RPS | 通过 |
| 平均延迟 | 216.69 ms | 999.96 ms | 通过 |
| P95 | 363.39 ms | 1799.62 ms | 通过 |
| P99 | 374.61 ms | 1892.62 ms | 通过，均小于 5 秒 |
| 最大延迟 | 374.61 ms | 1892.62 ms | 通过 |
| OOM | 未发现 | 未发现 | 通过 |

本次容量复测未重新采集显存曲线；显存峰值仍引用前序权威性能报告的 3697/8188 MB。本次不以未采样值替代该历史实测。

## 9. 数据库迁移与 pgvector 集成复测

| 场景 | 本次结果 | 状态 |
| --- | --- | --- |
| 空测试库升级 | `001→015` 成功 | 通过 |
| 当前 head | `015_vector_ops` | 通过 |
| 回滚再升级 | `015→014→015` 成功 | 通过 |
| 扩展 | `vector`、`pg_trgm` 均存在 | 通过 |
| 向量字段 | `knowledge_chunks.embedding=vector(1024)` | 通过 |
| 检索索引 | HNSW、trigram、向量队列和店铺状态索引存在 | 通过 |
| 店铺隔离与状态门禁 | 跨店铺、draft、archived、pending、旧版本被排除 | 通过 |
| 并发认领 | 两个 Worker 认领不同文档 | 通过 |
| 集成用例 | 2 passed | 通过 |

本次使用 `postgres-test` tmpfs 隔离数据库，通过宿主机端口 5433 成功执行 asyncpg 集成用例，未复现旧报告的连接重置。测试后已删除 `crm-postgres-test-1`，其临时数据不可恢复且不涉及项目持久化数据库。

## 10. Agent 工作流与安全边界回归

| 场景 | 预期 | 结果 |
| --- | --- | --- |
| BGE 配置为 1536 维 | 启动阶段拒绝，禁止新旧向量混写 | 通过 |
| 无知识或低于检索门禁 | 不生成猜测答案，转人工 | 通过 |
| 未知、混合、上下文不足 | `intent=null` 并转人工 | 通过 |
| 订单/实时物流 | 只声明白名单工具，不执行 | 通过 |
| 空引用、越界引用、候选 ID 注入 | 失败关闭并转人工 | 通过 |
| Prompt 注入 | 知识视为不可信数据 | 通过 |
| 最终置信度 | 由意图、检索和依据分数最小值计算 | 通过 |
| 0.60/0.80 阈值 | 人工复核/自动回复就绪分流正确 | 通过 |
| 自动回复就绪 | `AUTO_REPLY_READY` 且 `send_performed=false` | 通过 |
| 模型超时、连接失败、输出异常 | 稳定错误并转人工，不无依据降级 | 通过 |
| 运行追踪 | 不保存客户原文、FAQ 正文、完整模型输出或 Token | 通过 |

## 11. 原问题关闭情况

### DEF-M04-001：真实模型 RAG 质量门禁未执行

| 项目 | 结果 |
| --- | --- |
| 原优先级 | P0，验收阻塞 |
| 修复变化 | OpenAI 1536 维方案已由 ADR-002 正式替换为本地 BGE-M3 1024 维方案 |
| 本次证据 | BGE-M3 真实质量集 70 条完成；Recall、排序、引用和拒判门禁全部通过 |
| 当前状态 | 已关闭 |

### ENV-M04-002：Windows 主机 PostgreSQL 集成测试连接重置

| 项目 | 结果 |
| --- | --- |
| 原优先级 | P1，环境阻塞 |
| 修复变化 | 使用 Compose `postgres-test`、tmpfs 和独立 5433 端口 |
| 本次证据 | 迁移升级/回滚/再升级通过，两个 asyncpg 集成用例 `2 passed` |
| 当前状态 | 已关闭 |

## 12. 新发现与风险

本次未发现新的 P0、P1 或 P2 缺陷。

| 编号 | 风险 | 优先级 | 处理建议 |
| --- | --- | --- | --- |
| OBS-M04-002 | pytest 有 Starlette/httpx 和 argon2 包元数据弃用警告 | P3 | 后续依赖维护窗口升级并回归，不阻塞当前验收 |
| R-M04-DRIFT-001 | 固定离线集不能覆盖真实客户数据漂移 | P3 | 上线后持续监测命中率、拒判率并周期复评 |
| R-M04-CAP-002 | GPU、Worker、候选数或模型 Revision 变化会使容量结论失效 | P3 | 部署参数变化后重新执行质量和容量门禁 |

## 13. 回归结果与最终结论

### 13.1 回归结果

- 全量后端自动化：88 passed，2 个默认数据库用例随后在隔离库补测为 2 passed。
- BGE/Agent 专项：76 passed。
- 真实 BGE-M3 质量：全部门禁通过。
- 50 并发性能：零失败，P99 均小于 5 秒。
- 迁移、1024 维、店铺隔离和并发认领：通过。
- 依赖安全、模型哈希、非 root、CUDA 和失败关闭：通过。
- 主数据库保持 `015_vector_ops (head)`，后端健康检查通过。

### 13.2 是否建议验收

**结论：通过。建议验收 Phase 2 M04 当前 BGE-M3 契约范围。**

原报告中的 DEF-M04-001 和 ENV-M04-002 均已关闭。当前结论适用于固定 BGE-M3/Reranker Revision、1024 维、Dense 阈值 0.52、候选 20、单 Worker、RTX 4060 和当前版本化评测集。

本结论不授权平台自动发送。`AUTO_REPLY_READY` 仍只表示满足候选回复条件，必须保持 `send_performed=false`；真实平台联调、线上数据漂移和公开 `/suggest` 不属于本次验收范围。

## 14. 测试清理

- 已删除本次创建的 `crm-postgres-test-1` 和 `crm-retrieval-model-service-1` 容器。
- `postgres-test` 使用 tmpfs，临时测试数据随容器删除且不可恢复。
- 模型镜像、模型资产、开发数据库和项目持久化卷未删除。

