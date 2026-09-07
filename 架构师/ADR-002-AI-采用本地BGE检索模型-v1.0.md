# 采用本地 BGE 检索模型

## 1. 决策信息

| 项目 | 内容 |
| --- | --- |
| 文档编号 | ADR-002-AI |
| 版本 | v1.0 |
| 状态 | 已确认并实施 |
| 提出日期 | 2026-08-21 |
| 提出 Agent | AIAgent开发工程师Agent |
| 评审 Agent | 架构师Agent、全栈开发工程师Agent、测试工程师Agent |

## 2. 背景

本 ADR 提出时，M04 使用 OpenAI `text-embedding-3-small` 生成 1536 维向量，并直接从 pgvector Top 5 结果构造回答上下文。项目随后下载固定版本的 BGE-M3 和 `bge-reranker-large`，目标是改为本地向量生成与二阶段重排序，降低外部 Embedding 依赖并增强中英文 FAQ 检索。

上述内容是决策前背景。当前运行时代码、数据库迁移和配置契约已经切换；是否生产开放仍受本 ADR 第 8 节的正式质量和容量门禁约束。

## 3. 决策

- Dense 向量模型使用 `BAAI/bge-m3`，输出维度固定为 1024。
- 重排序模型使用 `BAAI/bge-reranker-large`，只使用 Safetensors 权重。
- 新增单实例内部检索模型服务，集中加载两套模型；backend 和 jobs 通过内部契约调用。
- 模型目录以只读方式挂载，不把权重打入应用镜像或版本库。
- 第一阶段执行 BGE-M3 Dense Top 20 与 PostgreSQL `pg_trgm` 词法 Top 20 双路召回，使用 RRF（`k=60`）融合为 20 条候选，再由 Cross-Encoder 生成最终 Top 5。
- Reranker 原始分数只用于排序，不直接参与最终业务置信度，直到评测确定归一化方案。
- 保留现有 Embedding Provider 抽象，切换期间禁止 1536 维和 1024 维数据混写。

## 4. 数据与迁移要求

- 迁移 `014_bge_hybrid` 已把知识向量切换为 `vector(1024)`，重建 HNSW cosine 索引并增加 `pg_trgm` GIN 索引。
- 不尝试把 1536 维旧向量转换为 1024 维；所有已发布 FAQ 必须重新进入 `pending` 并重新向量化。
- 迁移必须区分结构迁移和后台回填，避免在 Alembic 事务中执行模型推理。
- 回填完成并通过质量门禁前，本地 Provider 不得成为生产默认值。
- 回滚需要恢复旧结构或使用迁移前备份，并重新生成与目标维度匹配的向量。

## 5. 运行与容量要求

- 开发机为 RTX 4060 8 GB，默认使用 FP16 和小批量。
- 必须测量两模型常驻显存、单批峰值、并发延迟和 OOM；未通过前不得承诺生产容量。
- 模型服务不可用时必须返回稳定错误并转人工，不得绕过 RAG 生成无依据答案。
- 开发基线采用 Docker Desktop/WSL2 NVIDIA GPU，通过独立 `docker-compose.gpu.yml` 启用；基础 Compose 保留 CPU 回退能力。

## 6. 影响

### 正向影响

- FAQ 文本和查询不再发送到外部 Embedding 服务。
- 支持中英文 Dense 召回和 Cross-Encoder 二阶段排序。
- 模型版本、权重和运行环境可由项目自行控制。

### 代价与风险

- 需要新增 GPU 推理运行面、监控和容量治理。
- pgvector 维度变化会导致全部现有向量失效。
- BGE-M3 的相似度分布与 OpenAI 不同，原 0.70 阈值不可直接复用。
- BGE-M3 官方 PyTorch 权重存在 Pickle 供应链风险，必须固定 Revision 和 SHA-256。

## 7. 验收门禁

- 模型 Revision、关键文件和 SHA-256 与资产清单一致。
- Recall@20、重排序后 Recall@5、nDCG/MRR 和无答案转人工率达到测试工程师确定的门禁。
- 引用合法率为 100%，模型故障路径全部转人工。
- 单店铺隔离、当前文档版本、发布状态和 ready 状态过滤不回退。
- GPU 显存、P95 延迟、吞吐和冷启动完成实测。

## 8. 当前结论

架构师已确认本 ADR。本地 Provider、单实例模型服务、1024 维迁移、Dense+词法+RRF 混合召回及 Reranker 已实施，并在 RTX 4060 8 GB 上完成真实离线冒烟。正式 Recall、MRR、nDCG、无答案拒判率、P95 和并发容量仍由测试工程师独立评测后决定生产门禁。

## 9. 全栈运行面补充（2026-08-21）

- 新增 `015_vector_ops` 运维索引、店铺级向量状态接口、失败重试接口和管理端状态面板，不改变本 ADR 的检索算法决策。
- AI 启用改用 `docker-compose.ai.yml`，backend/jobs 必须等待模型服务健康；GPU 能力继续由 `docker-compose.gpu.yml` 单独叠加。
- 应用就绪探针在 Embedding 启用时校验 BGE-M3/1024 维契约，返回内容保持低敏。
- OSV 对当前 PyTorch/Transformers 锁定版本报告已知漏洞；生产启用增加“依赖升级兼容性评估与安全复核”门禁，固定 Revision、离线模式、禁用 `trust_remote_code`、只读挂载和非 root 运行只作为纵深防御。
