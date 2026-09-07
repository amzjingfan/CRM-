# BGE 本地模型资产登记实施记录

## 1. 基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | PhaseX |
| 任务编号 | PX-00，待架构师分配正式接入任务编号 |
| 模块编号 | M04 |
| 主责 Agent | AIAgent开发工程师Agent |
| 协作 Agent | 架构师Agent、全栈开发工程师Agent、测试工程师Agent |
| 实施状态 | 已完成 |
| 开始日期 | 2026-08-21 |
| 完成日期 | 2026-08-21 |
| 代码位置 | `CRM智能聊天系统/deploy/models/`，不涉及运行时代码 |

## 2. 需求与依据

- 产品需求：`共享记忆文档/智能客服平台 — 产品需求文档（PRD）V2.0.md` 中知识库和 RAG 能力。
- 接口依据：本任务不新增公开接口。
- 架构依据：`ARCH-001-SYS-系统总体架构设计-v1.1.md`、`ARCH-003-DATA-数据库与向量库初版设计-v1.0.md`。
- 任务依据：用户确认的 BGE 本地模型下载与后续文档更新方案；正式接入任务编号待补充。
- 验收依据：固定 Revision、关键文件、大小、SHA-256、排除重复权重和未启用边界。
- 代码规范：`共享记忆文档/代码编写手册.md`；本任务未修改 Python 产品代码。

## 3. 目标、范围与非目标

### 3.1 实施目标

- 下载并校验固定版本 BGE-M3 和 `bge-reranker-large`。
- 登记模型 Revision、权重格式、大小、SHA-256、许可证和本地目录。
- 更新 AI、架构、数据库、README 和共享实施文档，明确后续迁移边界。

### 3.2 实施范围

- `deploy/models` 模型资产、说明和清单。
- BGE 下载与校验指南、RAG v1.1 增量规范和评审中 ADR。
- 架构与数据库增量说明、实施记录和索引。

### 3.3 非目标

- 不安装 PyTorch、Transformers 或 FlagEmbedding 到产品依赖。
- 不实现本地 Provider、Reranker、模型服务或 Docker GPU 配置。
- 不修改 `.env.example`、数据库迁移、pgvector 维度、FAQ 数据或运行中的服务。
- 不执行真实模型推理、RAG 质量评测或性能测试。

## 4. 实施前确认

- [x] 已读取共享记忆文档文件清单。
- [x] 已读取 PRD、接口、任务拆解、团队职责、架构和 M04 测试结论。
- [x] 已读取代码手册及 Agent、Python、PostgreSQL、安全和文档 Skill。
- [x] 已确认模块编号 M04，任务编号暂用 PX-00。
- [x] 已确认下载目录、固定 Revision、风险和验收方式。

## 5. 实施方案

### 5.1 方案说明

使用一次性 Hugging Face Hub CLI 按完整 Revision 下载官方 BAAI 模型。BGE-M3 排除 ONNX 和图片，保留 Dense、Sparse、ColBERT 所需文件；Reranker 排除 ONNX 和重复 Pickle 权重，只保留 Safetensors。下载后对关键文件、禁止文件、元数据 Revision、大小和 SHA-256 进行校验。

模型下载和项目切换分离。资产状态记录为 `downloaded_not_enabled`，当前 OpenAI 1536 维实现保持不变。

### 5.2 依赖关系

- 前置依赖：P2-03 FAQ 向量检索和 P2-07 Agent 编排。
- 后续依赖：架构师确认 ADR-002-AI；AI 工程师实现本地 Provider/Reranker；全栈工程师提供模型运行面；测试工程师执行质量和性能测试。

### 5.3 风险控制

| 风险 | 影响 | 应对措施 |
| --- | --- | --- |
| BGE-M3 为 1024 维 | 与当前 1536 维数据库不兼容 | 不启用；单独迁移并全量重新向量化 |
| PyTorch Pickle 权重 | 供应链代码执行风险 | 仅官方 BAAI、固定 Revision、SHA-256 和禁用远程代码 |
| 8 GB 显存不足 | OOM 或延迟抖动 | 单实例服务、FP16、小批量和正式容量测试 |
| Reranker 分数误用 | 错误影响业务置信度 | 第一阶段只排序，归一化待评测与 ADR 确认 |
| 大文件进入版本库 | 仓库膨胀和分发风险 | `.gitignore` 排除权重与缓存，只提交清单 |

## 6. 实际变更

### 6.1 文件变更

| 文件路径 | 变更类型 | 变更说明 | 负责 Agent |
| --- | --- | --- | --- |
| `CRM智能聊天系统/deploy/models/bge-m3/` | 新增 | 固定版本 BGE-M3 权重和配置 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/deploy/models/bge-reranker-large/` | 新增 | 固定版本 Reranker Safetensors 和配置 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/deploy/models/model-manifest.json` | 新增 | Revision、大小、哈希和启用状态 | AIAgent开发工程师Agent |
| `AI agent 开发工程师/AI-003-MODEL-BGE本地模型下载与校验指南-v1.0.md` | 新增 | 下载、校验和安全指南 | AIAgent开发工程师Agent |
| `AI agent 开发工程师/AI-002-RAG-FAQ检索与Agent工作流规范-v1.1.md` | 新增 | 本地 BGE 二阶段检索增量规范 | AIAgent开发工程师Agent |
| `架构师/ADR-002-AI-采用本地BGE检索模型-v1.0.md` | 新增 | 待架构师评审的技术决策 | AIAgent开发工程师Agent |
| `架构师/ARCH-001-SYS-系统总体架构设计-v1.2.md` | 新增 | 模型服务增量架构 | AIAgent开发工程师Agent |
| `架构师/ARCH-003-DATA-数据库与向量库初版设计-v1.1.md` | 新增 | 1024 维迁移增量说明 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/README.md`、`.gitignore` | 修改 | 资产状态、目录和版本库排除规则 | AIAgent开发工程师Agent |

### 6.2 接口、数据和配置变更

- API：无。
- 数据库：无；迁移 head 和 1536 维结构保持不变。
- 配置项：无；`.env.example` 未修改。
- AI：新增本地模型资产，但 Provider 未启用，RAG 运行行为未改变。

### 6.3 关键实现说明

- dry-run 发现 `huggingface_hub<1.0` 不支持 `--dry-run`，实际改用一次性 `huggingface_hub>=1,<2`；该工具未进入项目依赖。
- BGE-M3 Revision 为 `5617a9f61b028005a4858fdac845db406aefb181`。
- Reranker Revision 为 `55611d7bca2a7133960a6d3b71e083071bbfc312`。
- 下载使用匿名公共仓库，没有使用或记录任何 API Key。

## 7. 验证记录

| 验证项 | 命令或方法 | 预期结果 | 实际结果 | 状态 |
| --- | --- | --- | --- | --- |
| dry-run | `hf download ... --dry-run` | 两模型各约 2.3 GB | BGE-M3 15 文件 2.3G；Reranker 8 文件 2.3G | 通过 |
| BGE-M3 关键文件 | `Test-Path`、大小检查 | 权重和配置完整 | 权重 2,271,145,830 字节；有效目录约 2189.10 MiB | 通过 |
| Reranker 关键文件 | `Test-Path`、大小检查 | Safetensors 和配置完整 | 权重 2,239,618,772 字节；有效目录约 2157.04 MiB | 通过 |
| 排除项 | 递归检查 | 无 Reranker Pickle 和 ONNX | 禁止文件数量 0 | 通过 |
| Revision | Hugging Face 下载元数据 | 与固定提交一致 | 两模型均一致 | 通过 |
| SHA-256 | `Get-FileHash -Algorithm SHA256` | 与 Xet 元数据一致 | 两模型均一致 | 通过 |
| 推理加载 | 不适用 | 本任务不安装运行依赖 | 未执行，不影响资产下载验收 | 未执行 |
| 数据库和运行回归 | 不适用 | 本任务不修改运行时 | 未执行，运行时保持原状 | 未执行 |

## 8. 实施结果

- 完成项：两套固定版本模型下载、完整性校验、资产清单、版本库排除和相关文档同步。
- 未完成项：本地 Provider、Reranker、模型服务、数据库迁移、重新向量化、质量与性能测试。
- 与原方案差异：一次性下载 CLI 从 `<1.0` 调整为 `>=1,<2`，因为旧 CLI 不支持 dry-run；BGE-M3 额外排除根目录演示图片。
- 当前状态：已完成；完成范围仅为模型资产下载、校验和文档登记。

## 9. 遗留问题与风险

| 编号 | 问题或风险 | 优先级 | 负责 Agent | 计划处理 Phase/任务 |
| --- | --- | --- | --- | --- |
| R-BGE-001 | ADR-002-AI 尚待架构师确认 | P0 | 架构师Agent | 待分配 |
| R-BGE-002 | 1024 维迁移和全量重新向量化未实施 | P0 | AIAgent开发工程师Agent、全栈开发工程师Agent | 待分配 |
| R-BGE-003 | 真实检索质量、阈值和 Reranker 策略未评测 | P0 | AIAgent开发工程师Agent、测试工程师Agent | 待分配 |
| R-BGE-004 | RTX 4060 8 GB 容量和运行方式未验证 | P1 | AIAgent开发工程师Agent、全栈开发工程师Agent | 待分配 |

## 10. 交接事项

- 交接给：架构师Agent、全栈开发工程师Agent、测试工程师Agent。
- 后续任务：确认 ADR、设计模型服务、实施 1024 维迁移和 Provider，再执行 AI 质量与 GPU 性能报告。
- 必须注意：模型已下载但未启用；禁止直接修改环境变量绕过 1536 维校验，禁止新旧向量混写。

## 11. 文档同步

- [x] 已同步接口变化：无接口变化并明确记录。
- [x] 已同步架构决策：ADR 状态为评审中。
- [x] 已同步任务状态：资产下载完成，接入任务待分配。
- [x] 已通知测试工程师需要覆盖的范围。
- [x] 测试报告索引保持不变；正式模型测试尚未开始。

## 12. 后续接入引用

2026-08-21 架构师已确认 ADR-002-AI，模型资产已由 P2-03 后续任务接入本地 Provider、单实例模型服务、1024 维迁移、混合检索和重排序。完整变更与验证证据见 `共享记忆文档/实施记录/Phase2-P2-03-AIAgent开发工程师Agent-BGE混合检索与重排序-002.md`。本记录仍只证明模型资产下载与校验，不改写其历史实施范围。
