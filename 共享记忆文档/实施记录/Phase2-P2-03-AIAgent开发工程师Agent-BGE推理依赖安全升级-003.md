# BGE 推理依赖安全升级实施记录

## 1. 基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase2 |
| 任务编号 | P2-03；关联 P2-04 |
| 模块编号 | M04 |
| 主责 Agent | AIAgent开发工程师Agent |
| 协作 Agent | 全栈开发工程师Agent、测试工程师Agent |
| 实施状态 | 部分完成 |
| 开始日期 | 2026-08-21 |
| 完成日期 | 未完成 |
| 代码位置 | `CRM智能聊天系统/` |

## 2. 需求与依据

- 交接依据：`共享记忆文档/实施记录/Phase2-P2-04-全栈开发工程师Agent-BGE知识库运行面适配-001.md` 中 `R-FS-BGE-001`。
- 架构依据：`架构师/ADR-002-AI-BGE本地混合检索与重排序架构决策-v1.0.md`。
- AI 规范：`AI agent 开发工程师/AI-002-RAG-FAQ检索与Agent工作流规范-v1.2.md`。
- 任务依据：`共享记忆文档/开发任务拆解（按人天分配）.md` 中 P2-03。
- 代码规范：`共享记忆文档/代码编写手册.md`。

## 3. 目标、范围与非目标

### 3.1 实施目标

- 处置模型服务锁定的 Torch/Transformers 已知漏洞，保持 Python 3.11 与 BGE 推理代码兼容。
- 防止依赖回退和远程代码、在线模型、未评审 API 重新进入模型运行面。

### 3.2 实施范围

- `retrieval-model` 可选依赖、`uv.lock`、模型服务安全契约测试、README 和 AI 规范。
- 确定性后端回归、OSV 锁文件审计以及新模型镜像构建尝试。

### 3.3 非目标

- 不改变 BGE 模型 Revision、1024 维数据库结构、混合检索算法、阈值、Prompt 或公开 API。
- 不生成正式安全、性能或 AI 质量测试报告。

## 4. 实施前确认

- [x] 已读取共享记忆文档文件清单。
- [x] 已读取相关 PRD、接口、任务拆解和验收标准。
- [x] 已读取代码编写手册及适用 Skill。
- [x] 已确认 Phase、任务编号、模块编号和主责 Agent。
- [x] 已确认依赖、风险和验收方式。

## 5. 实施方案

### 5.1 方案说明

将独立模型服务依赖从 `torch>=2.10,<2.11`、`transformers>=4.57,<4.58` 升级为 `torch>=2.13,<2.14`、`transformers>=5.5,<5.6`，最终锁定 2.13.0 和 5.5.4。通过测试固定依赖下界和上界，并检查引擎继续使用本地只读文件、关闭远程代码，且不引入审计涉及但本项目不需要的 Trainer 与 TorchScript API。

### 5.2 依赖关系

- 前置依赖：固定 Revision 和 SHA-256 的 BGE-M3、BGE Reranker 资产；独立模型服务边界。
- 后续依赖：测试工程师重建镜像，完成 RTX 4060 GPU、Embedding、Reranker、安全和容量正式复测。

### 5.3 风险控制

| 风险 | 影响 | 应对措施 |
| --- | --- | --- |
| 次版本回退 | 重新引入已处置公告 | pyproject 上下界和自动化版本门禁 |
| Transformers 5 API 变化 | 模型无法加载或推理 | 保留直接 AutoModel API，执行确定性契约测试并要求真实镜像复测 |
| CUDA 12→13 依赖变化 | RTX 4060 容器不兼容或镜像显著增大 | 禁止复用旧镜像验收，必须执行新镜像 GPU 冒烟 |
| BGE-M3 Pickle 权重 | 资产替换可能触发反序列化风险 | 固定官方 Revision、离线加载、禁用远程代码、生产启用 SHA-256 门禁 |

## 6. 实际变更

### 6.1 文件变更

| 文件路径 | 变更类型 | 变更说明 | 负责 Agent |
| --- | --- | --- | --- |
| `backend/pyproject.toml` | 修改 | 升级并限制 Torch/Transformers 安全兼容范围 | AIAgent开发工程师Agent |
| `backend/uv.lock` | 修改 | 锁定 Torch 2.13.0、Transformers 5.5.4 及 CUDA 13 依赖族 | AIAgent开发工程师Agent |
| `backend/tests/test_retrieval_runtime_dependencies.py` | 新增 | 依赖版本和离线安全加载回归门禁 | AIAgent开发工程师Agent |
| `README.md` | 修改 | 同步安全审计结果和新镜像 GPU 待复测状态 | AIAgent开发工程师Agent |
| `AI agent 开发工程师/AI-002-RAG-FAQ检索与Agent工作流规范-v1.3.md` | 新增 | 升级 AI 运行时安全规范，保留 v1.2 历史版本 | AIAgent开发工程师Agent |

### 6.2 接口、数据和配置变更

- API：无变化。
- 数据库：无迁移，head 保持 `015_vector_ops`。
- 配置项：无新增环境变量，不记录或读取真实 Token。
- AI：模型 ID、Revision、检索链路和阈值不变；仅升级模型推理运行时依赖。

### 6.3 关键实现说明

- 重型依赖仍只安装在 `retrieval-model-service`，backend 和 jobs 通过内部 HTTP 契约访问，避免扩大攻击面与显存占用。
- 加载仍要求 `local_files_only=True`、`trust_remote_code=False`，测试阻止回退为远程代码执行。
- 依赖测试先在旧版本下得到预期失败，再修改约束得到通过，遵循 TDD RED→GREEN。

## 7. 验证记录

| 验证项 | 命令或方法 | 预期结果 | 实际结果 | 状态 |
| --- | --- | --- | --- | --- |
| TDD RED | 聚焦依赖测试 | 旧版本约束失败 | 1 failed、1 passed | 通过 |
| 聚焦 GREEN | 模型运行时与 HTTP 契约测试 | 全部通过 | 9 passed | 通过 |
| 锁文件 | `uv lock --check` | 锁文件一致 | 124 packages resolved | 通过 |
| 依赖审计 | `uv audit --locked` | 无已知漏洞 | 123 packages 无已知漏洞和不良项目状态 | 通过 |
| Ruff | `uv run ruff check ...` | 无错误 | All checks passed | 通过 |
| 格式 | `uv run ruff format --check ...` | 无变更 | 156 files already formatted | 通过 |
| 类型 | `uv run mypy app scripts` | 无错误 | 116 source files 无错误 | 通过 |
| 后端全量 | `uv run pytest` | 不破坏基线 | 87 passed、2 skipped | 通过 |
| 新镜像冷构建 | Docker 模型服务 build | 生成升级镜像 | 首次 20 分钟无输出超时；第二次短窗口仍无输出，旧镜像未覆盖 | 失败 |
| 新镜像 GPU 冒烟 | 模型健康、Embedding、Reranker | Torch 2.13/Transformers 5.5 在 RTX 4060 可用 | 因新镜像未构建完成而未执行 | 未执行 |

## 8. 实施结果

- 完成项：依赖版本升级、锁文件、漏洞清零、版本回退门禁、离线加载边界测试、静态检查和后端全量回归。
- 未完成项：升级后模型镜像构建、实际包版本核验、RTX 4060 Embedding/Reranker 冒烟与正式测试报告。
- 与原方案差异：Docker/BuildKit 构建后端在本机长时间无进度，无法取得新镜像运行证据；没有使用旧镜像伪装验证通过。
- 当前状态：部分完成；`R-FS-BGE-001` 的代码与锁文件处置完成，但生产启用仍受新镜像 GPU 复测阻断。

## 9. 遗留问题与风险

| 编号 | 问题或风险 | 优先级 | 负责 Agent | 计划处理 Phase/任务 |
| --- | --- | --- | --- | --- |
| R-AI-BGE-004 | Torch 2.13/Transformers 5.5 新镜像尚未完成 RTX 4060 冒烟 | P0 | 测试工程师Agent、AIAgent开发工程师Agent | P2-03 正式复测 |
| R-FS-BGE-002 | 部署环境正式内部 Token 尚未配置 | P1 | 部署环境维护者、全栈开发工程师Agent | P4-11 |
| R-FS-BGE-003 | Recall、P95、吞吐和 OOM 正式结论仍缺失 | P0 | 测试工程师Agent、AIAgent开发工程师Agent | P2-03/P4-10 |

## 10. 交接事项

- 交接给：测试工程师Agent、全栈开发工程师Agent、架构师Agent。
- 后续任务：在 Docker/BuildKit 可正常输出的环境重建 `retrieval-model-service`，核验容器内包版本后执行 GPU、Embedding、Reranker、安全、质量与容量测试。
- 必须注意：旧镜像不能作为升级后验证证据；正式复测通过前生产不得启用 AI Profile。

## 11. 文档同步

- [x] 已同步接口变化（本次无接口变化）。
- [x] 已同步架构决策（无新决策，升级 AI 规范版本）。
- [x] 已同步任务状态。
- [x] 已通知测试工程师需要覆盖的范围。
- [ ] 测试报告索引将在正式测试完成后更新。
