# Phase 2 P2-03/P2-04/P2-07 M04 BGE 模型切换与重排序综合测试报告

## 1. 测试基本信息

| 项目 | 内容 |
| --- | --- |
| 测试报告编号 | Phase2-P2-03-P2-04-P2-07-M04-001 |
| Phase | Phase2 |
| 任务编号 | P2-03、P2-04、P2-07 |
| 模块编号 | M04 |
| 模块名称 | FAQ 检索与 Agent 工作流 |
| 被测主责 Agent | AIAgent开发工程师Agent |
| 被测协作 Agent | 全栈开发工程师Agent、架构师Agent |
| 测试执行 Agent | 测试工程师 Agent |
| 关联实施记录 | `共享记忆文档/实施记录/Phase2-P2-03-AIAgent开发工程师Agent-BGE推理依赖安全升级-003.md`、`共享记忆文档/实施记录/Phase2-P2-04-全栈开发工程师Agent-BGE知识库运行面适配-001.md` |
| 测试类型 | 综合测试、功能测试、集成测试、兼容性测试、安全测试、回归测试 |
| 执行日期 | 2026-08-21 |
| 测试结论 | 有条件通过 |

## 2. 测试依据与范围

### 2.1 测试依据

- `共享记忆文档/智能客服平台 — 产品需求文档（PRD）V2.0.md`
- `共享记忆文档/开发任务拆解（按人天分配）.md`
- `共享记忆文档/MVP范围与验收标准.md`
- `架构师/ADR-002-AI-采用本地BGE检索模型-v1.0.md`
- `AI agent 开发工程师/AI-002-RAG-FAQ检索与Agent工作流规范-v1.3.md`
- `共享记忆文档/实施记录/Phase2-P2-03-AIAgent开发工程师Agent-BGE混合检索与重排序-002.md`
- `共享记忆文档/实施记录/Phase2-P2-03-AIAgent开发工程师Agent-BGE推理依赖安全升级-003.md`
- `共享记忆文档/实施记录/Phase2-P2-04-全栈开发工程师Agent-BGE知识库运行面适配-001.md`

### 2.2 本次覆盖

- BGE-M3 本地模型资产、Revision、1024 维输出和 SHA-256 完整性。
- `bge-reranker-large` 本地模型资产、Revision、有限分数和候选重排。
- Dense Top 20、pg_trgm Lexical Top 20、RRF 候选融合和最终重排边界。
- 店铺隔离、`published + ready + current version` 检索门禁。
- 向量化队列、版本漂移保护和多 Worker `SKIP LOCKED` 并发认领。
- Torch/Transformers 依赖锁定、漏洞审计、离线加载和远程代码关闭。
- 模型服务 Bearer Token、非 root、健康检查、GPU 可见性和真实推理。
- 迁移 `001→015`、`015→014→015`、pgvector/pg_trgm 扩展和索引。

### 2.3 不纳入本次结论

- Recall@20、Rerank Recall@5、MRR、nDCG、无答案转人工率等正式 AI 质量评测。
- 50 并发压力、P95、吞吐、冷启动和 OOM 容量结论。
- 真实客户数据、真实平台发送、公开 `/suggest`、SSE 和自动回复发送。

## 3. 测试环境

| 项目 | 环境 |
| --- | --- |
| 操作系统 | Windows，PowerShell |
| Python | 3.11.15 |
| 后端 | FastAPI、SQLAlchemy 异步模式 |
| 模型服务依赖 | Torch 2.13.0+cu130、Transformers 5.5.4 |
| 向量模型 | `BAAI/bge-m3`，固定 Revision，1024 维 |
| 重排序模型 | `BAAI/bge-reranker-large`，固定 Revision |
| GPU | NVIDIA GeForce RTX 4060，CUDA 可见 |
| 数据库 | PostgreSQL 16 + pgvector + pg_trgm，隔离 `postgres-test` |
| 数据库 head | `015_vector_ops` |
| 测试模式 | 默认离线确定性测试 + 本地真实模型服务冒烟 |

密钥安全：本次使用临时进程环境 Token，未写入 `.env`、代码、报告或日志；未使用外部 LLM/API Key。

## 4. 执行命令与结果

### 4.1 后端质量与依赖安全

| 命令 | 实际结果 | 状态 |
| --- | --- | --- |
| `uv lock --check` | 124 packages resolved，锁文件一致 | 通过 |
| `uv run ruff check app migrations scripts tests` | All checks passed | 通过 |
| `uv run ruff format --check app migrations scripts tests` | 156 files already formatted | 通过 |
| `uv run mypy app scripts` | 116 个源文件无类型错误 | 通过 |
| `uv run pytest -q` | 87 passed，2 skipped，2 warnings | 通过 |
| `uv audit --locked` | 123 个包未发现已知漏洞或不良项目状态 | 通过 |

2 个默认跳过用例是未提供 `TEST_DATABASE_URL` 时的数据库集成用例；本次随后使用隔离 PostgreSQL 环境重新执行，未作为最终跳过结论。

### 4.2 模型资产与容器安全

| 检查项 | 实际结果 | 状态 |
| --- | --- | --- |
| BGE-M3 权重 | 2,271,145,830 bytes，SHA-256 与 manifest 一致 | 通过 |
| Reranker 权重 | 2,239,618,772 bytes，SHA-256 与 manifest 一致 | 通过 |
| 容器包版本 | `torch=2.13.0+cu130`、`transformers=5.5.4` | 通过 |
| Compose AI/GPU 配置 | 服务列表可解析，模型健康依赖存在 | 通过 |
| 容器 UID | `10001` | 通过 |
| 远程代码边界 | `local_files_only=True`、`trust_remote_code=False`，无 `Trainer`/`torch.jit.script` | 通过 |
| 模型服务健康 | BGE-M3、Reranker、1024 维契约返回正确 | 通过 |
| CUDA | `cuda_available=True`，设备为 RTX 4060 | 通过 |

### 4.3 真实本地模型冒烟

真实请求只使用无客户信息的测试文本：

| 场景 | 实际结果 | 状态 |
| --- | --- | --- |
| BGE-M3 Embedding | `provider=local_bge`，Revision 正确，向量长度 1024，全部有限 | 通过 |
| Reranker 候选排序 | 退货 FAQ 分数 `1.37109375`，物流 FAQ 分数 `-4.6953125`，排序正确 | 通过 |
| 模型服务认证 | 内部 Bearer Token 注入，未输出 Token | 通过 |
| 公开接口隔离 | 模型服务只通过内部 Compose 网络暴露 | 通过 |

## 5. 数据库迁移与集成结果

| 检查项 | 实际结果 | 状态 |
| --- | --- | --- |
| 空测试库升级 | `001→015` 全部成功 | 通过 |
| 回滚再升级 | `015→014→015` 成功，最终 `015_vector_ops (head)` | 通过 |
| 扩展 | `vector`、`pg_trgm` 均存在 | 通过 |
| 向量维度 | `knowledge_chunks.embedding` 为 `vector(1024)` | 通过 |
| 检索索引 | HNSW、pg_trgm、向量队列和店铺状态索引均存在 | 通过 |
| 店铺隔离 | 跨店铺候选未进入结果 | 通过 |
| 状态/版本门禁 | draft、archived、pending、旧版本均被排除 | 通过 |
| 并发认领 | 两个 Worker 使用 `FOR UPDATE SKIP LOCKED` 获得不同文档 | 通过 |

测试库使用 `postgres-test` 的 tmpfs，测试结束后已停止并移除，不影响开发数据库。

## 6. 功能与安全场景

| 场景 | 预期 | 结果 |
| --- | --- | --- |
| 配置 1536 维 | 启用本地 BGE 时拒绝，防止新旧向量混写 | 通过 |
| 空查询、超长查询、重复候选 ID | 稳定校验失败 | 通过 |
| NaN/Infinity 向量或分数 | 拒绝进入检索和排序 | 通过 |
| 模型服务超时/连接失败/5xx | 有界重试并返回稳定领域错误 | 通过 |
| 认证失败/非法请求 | 不重试绕过，不泄露响应正文 | 通过 |
| Reranker 返回未知候选 ID | 失败关闭，禁止跨租户候选注入 | 通过 |
| RAG 输入脱敏 | 邮箱、订单号不发送给 Embedding/检索端口 | 通过 |
| 上下文预算 | 不超过配置 Token 预算 | 通过 |
| RRF 候选顺序 | 候选融合后由 Reranker 决定最终顺序 | 通过 |
| 资产哈希不一致 | 应在模型服务启动时失败关闭 | 代码/契约通过，未篡改真实资产 | 通过 |

未发现客户原文、完整 FAQ 正文、API Key、Token 或完整模型响应写入测试报告和测试日志的证据。

## 7. 缺陷与遗留风险

### R-AI-BGE-004：升级后模型容量和正式质量门禁未完成

| 属性 | 内容 |
| --- | --- |
| 优先级 | P0，生产验收阻塞 |
| 类型 | 未完成正式质量/容量测试 |
| 现象 | 本次已完成单请求真实模型冒烟，但未执行 Recall、MRR、nDCG、50 并发、P95、吞吐和 OOM 测试 |
| 影响 | 不能证明 PRD 的 AI 独立解决率、响应速度和容量目标 |
| 建议 | 使用版本化 FAQ 评测集和固定 GPU 环境执行正式 AI 评测、性能和容量报告 |
| 当前状态 | 未关闭 |

### OBS-M04-001：单请求推理通过不代表并发容量通过

| 属性 | 内容 |
| --- | --- |
| 优先级 | P1 |
| 现象 | 本次只验证单条 Embedding 和两条候选 Reranker 请求 |
| 影响 | 无法确认 8 GB 显存下批量向量化和并发重排不会 OOM |
| 建议 | 测试工程师执行批量 32、并发 50、P95 和显存曲线测试 |
| 当前状态 | 待处理 |

除上述质量与容量门禁外，本次未发现代码级功能或安全阻断缺陷。

## 8. 回归结果

- Phase 1/Phase 2 既有后端回归未被破坏：87 passed，2 skipped（默认环境运行）。
- 隔离 PostgreSQL 集成测试补充执行后为 89 passed，2 warnings。
- 本地 BGE 真实模型服务、Embedding、Reranker、GPU 和容器非 root 门禁通过。
- 锁文件依赖安全审计通过，未发现此前报告的 Torch/Transformers 已知漏洞。
- 测试结束后已清理本轮启动的 `retrieval-model-service` 和 `postgres-test` 容器，未删除模型镜像、模型资产或项目数据。

## 9. 测试结论与验收建议

### 9.1 当前结论

重新选择的 BGE-M3 向量模型、bge-reranker-large 重排序模型、1024 维数据库结构、混合检索、租户隔离、依赖安全和真实单请求 GPU 运行面测试通过。未发现代码级缺陷。

### 9.2 是否建议验收

**建议：有条件通过，不建议作为正式生产 AI 质量验收通过。**

生产启用前必须完成：

1. FAQ 评测集 Recall@20、Rerank Recall@5、MRR、nDCG@5 和引用合法率测试。
2. 无答案正确转人工率和置信度阈值校准。
3. 50 并发、P95、吞吐、冷启动和 OOM 测试。
4. 测试工程师分别生成正式 AI 评测报告和性能/容量报告。

本报告证明了模型资产、依赖、数据库和真实单请求运行面的可用性，不将单请求冒烟结果外推为正式质量或容量结论。

## 10. 2026-08-21 生产门禁后续回归

本节是后续正式评测结果，不改写第 1～9 节的原始测试事实。下列两份权威报告已经完成本报告第 9.2 节要求的全部任务：

- `测试工程师/Phase2-P2-03-P2-07-AIAgent开发工程师Agent-M04-BGE混合检索与重排序-AI评测-001.md`
- `测试工程师/Phase4-P4-10-AIAgent开发工程师Agent-M04-BGE模型服务-性能测试-001.md`

回归结果：

| 遗留项 | 后续结果 | 当前状态 |
| --- | --- | --- |
| R-AI-BGE-004 | Recall@20、Rerank Recall@5、MRR、nDCG@5、引用合法率和无答案转人工率均达标；50 并发、P95/P99、吞吐、冷启动和 OOM 均通过 | 已关闭 |
| OBS-M04-001 | batch=32、候选=20、50 并发和 GPU 峰值显存 3697/8188 MB 已验证，无 OOM | 已关闭 |

Dense 门禁已从临时值 `0.45` 校准为 `0.52`。在当前固定模型 Revision、版本化评测集和 RTX 4060 单实例范围内，本报告原“有条件通过”结论由上述后续报告升级为“生产前模型质量与容量门禁通过”。
