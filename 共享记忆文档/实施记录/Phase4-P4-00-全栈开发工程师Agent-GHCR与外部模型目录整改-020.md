# GHCR 与外部模型目录整改实施记录

## 1. 基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase4 |
| 任务编号 | P4-00；关联 REAL-FS-01/G0、P4-11 |
| 模块编号 | M00 |
| 主责 Agent | 全栈开发工程师Agent |
| 协作 Agent | 架构师Agent、测试工程师Agent |
| 实施状态 | 已完成 |
| 验收边界 | 仅工程整改已完成；真实服务器部署、回滚和 G0 仍待验证 |
| 开始日期 | 2026-09-08 |
| 完成日期 | 2026-09-08 |
| 代码位置 | `CRM智能聊天系统/`、`.github/workflows/` |

## 2. 需求与依据

- 产品需求：Docker Compose 一键部署和基础日志/异常处理能力。
- 接口依据：不改变公开 API。
- 架构依据：生产放行检查表 v1.1 的 G0 和不可变镜像策略。
- 任务依据：用户要求完善 GHCR 拉取认证和服务器外部模型目录。
- 验收依据：staging 工作流能鉴权拉取 GHCR；权重位于仓库外、只读挂载并强制校验固定摘要。
- 代码规范：`共享记忆文档/代码编写手册.md`。

## 3. 目标、范围与非目标

### 3.1 实施目标

- 为 staging 自托管 runner 增加最小权限 GHCR 登录。
- 生产 Compose 固定使用服务器仓库外模型目录并在启动时校验权重哈希。

### 3.2 实施范围

- GitHub Actions staging workflow。
- 生产 Compose、预检/回滚脚本、脱敏环境变量示例和部署说明。

### 3.3 非目标

- 不提交模型权重、真实 Token、服务器路径或环境文件。
- 不执行真实服务器部署、回滚和健康检查。
- 不修改镜像 RepoDigest 或启用 TikTok/AI 生产能力。

## 4. 实施前确认

- [x] 已读取共享记忆文档文件清单。
- [x] 已读取 PRD、接口、任务拆解、MVP 范围和权威测试结论。
- [x] 已读取代码编写手册和适用 Skill。
- [x] 已确认 Phase、任务编号、模块编号和主责 Agent。
- [x] 已确认依赖、风险和验收方式。

## 5. 实施方案

### 5.1 方案说明

workflow 使用 GitHub Actions 提供的短期 `GITHUB_TOKEN` 登录 GHCR，只授予 `packages: read`。外部环境文件新增 `RETRIEVAL_MODEL_ASSET_DIR`，门禁要求其为存在的绝对路径、位于完整 Git checkout 外、不含符号链接/reparse point，并包含推理引擎所需六个固定普通文件。生产 Compose 将该目录只读挂载为 `/models`，模型服务固定开启 SHA-256 校验；实时部署和回滚使用 Compose v2 健康等待后才进入外部探针与证据写入。

### 5.2 依赖关系

- 前置依赖：已发布的三类 GHCR RepoDigest、已登记的 BGE 权重清单。
- 后续依赖：服务器连接、模型文件受控传输、staging `validate/deploy/rollback`。

### 5.3 风险控制

| 风险 | 影响 | 应对措施 |
| --- | --- | --- |
| GHCR 私有包不可读 | runner 无法拉取镜像 | `packages: read` + 固定 SHA login action + 仓库 Actions 包访问权 |
| checkout 更新丢失权重 | RAG 服务无法启动 | 模型目录必须为仓库外绝对路径 |
| 权重被替换或损坏 | 推理供应链风险 | 只读挂载并在每次生产启动时强制 SHA-256 校验 |
| 路径或权重缺失后仍部署 | 部署中途失败 | 预检和回滚脚本在 Compose 启动前失败关闭 |
| 模型服务尚未 healthy 就写通过证据 | 假阳性放行 | 每次 `docker compose up` 使用 `--wait --wait-timeout 600` |

## 6. 实际变更

### 6.1 文件变更

| 文件路径 | 变更类型 | 变更说明 | 负责 Agent |
| --- | --- | --- | --- |
| `.github/workflows/staging-gates.yml` | 修改 | 增加最小 GHCR 拉取权限和固定 action 登录 | 全栈开发工程师Agent |
| `CRM智能聊天系统/docker-compose.prod.yml` | 修改 | 只读挂载服务器外部模型并开启哈希校验 | 全栈开发工程师Agent |
| `CRM智能聊天系统/scripts/Test-StagingProductionGates.ps1` | 修改 | 校验真实 Git 根、六文件资产和合并 Compose 契约，等待容器健康 | 全栈开发工程师Agent |
| `CRM智能聊天系统/scripts/Invoke-StagingRollbackDrill.ps1` | 修改 | 回滚前执行同等模型资产门禁和 Compose 健康等待 | 全栈开发工程师Agent |
| `CRM智能聊天系统/backend/tests/test_production_gate_scripts.py` | 修改 | 新增两个脚本的目录边界、六文件、健康失败关闭测试，并归一化跨平台 PowerShell ANSI 与自动换行栏输出 | 全栈开发工程师Agent |
| `CRM智能聊天系统/frontend/tests/compose.test.mjs` | 修改 | 新增 staging GHCR 工作流契约测试 | 全栈开发工程师Agent |
| `CRM智能聊天系统/.env.example`、`deploy/production/README.md`、`deploy/models/README.md` | 修改 | 补充脱敏配置和服务器准备说明 | 全栈开发工程师Agent |
| `共享记忆文档/实施记录索引.md` | 修改 | 登记本实施记录 | 共享记忆文档Agent |
| `共享记忆文档/实施记录/Phase4-P4-00-全栈开发工程师Agent-GHCR与外部模型目录整改-020.md` | 修改 | 补充审阅整改、验证和遗留状态 | 全栈开发工程师Agent |

### 6.2 接口、数据和配置变更

- API：无。
- 数据库：无。
- 配置项：新增部署变量 `RETRIEVAL_MODEL_ASSET_DIR`，必须为服务器仓库外绝对路径。
- AI：模型、Prompt、RAG 算法和阈值不变；生产模型服务强制 `RETRIEVAL_MODEL_VERIFY_HASHES=true`。

### 6.3 关键实现说明

低敏证据只记录 `external_model_assets_validated=true` 和变量名，不记录服务器绝对路径。脚本通过 `git rev-parse --show-toplevel` 和规范化路径识别完整 checkout，而不是只检查嵌套产品目录。工作流不保存个人访问令牌；其 `GITHUB_TOKEN` 只在当前 job 用于 GHCR 登录。

## 7. 验证记录

| 验证项 | 命令或方法 | 预期结果 | 实际结果 | 状态 |
| --- | --- | --- | --- | --- |
| TDD 红灯 | 运行脚本和 workflow 聚焦测试 | 缺少目录门禁和 GHCR 登录时失败 | 后端 5 项、前端 1 项按预期失败 | 通过 |
| 脚本聚焦绿灯 | `pytest tests/test_production_gate_scripts.py -q --basetemp {系统临时目录}` | 全部通过 | 15 passed | 通过 |
| Compose/workflow 聚焦绿灯 | `node frontend/tests/compose.test.mjs` | 全部通过 | 10 passed | 通过 |
| 后端完整工程门禁 | `ruff check .`、`ruff format --check .`、`mypy app scripts`、`pytest -q --basetemp {仓库外临时目录}` | 全部通过 | 合入最新 `main` 后复验：Ruff 与格式通过；mypy 166 个源文件通过；1367 passed、14 skipped、2 个既有依赖弃用警告 | 通过 |
| 前端完整工程门禁 | `npm test`、`npm run typecheck`、`npm run lint`、`npm run build` | 全部通过 | 40 tests passed；类型检查通过；lint 0 error、2 个既有导航警告；生产构建成功并生成 12 个路由 | 通过 |
| Windows 脚本兼容性 | Windows PowerShell 5.1 解析两个门禁脚本 | 均可解析 | 两个脚本均 parse OK | 通过 |
| 审阅补充红灯 | 运行 Git 根、六文件、Compose 健康等待和链接绕过行为测试 | 原实现应暴露四类缺口 | 首轮 16 failed；链接测试另确认 2 failed，分别命中两个脚本 | 通过 |
| 审阅补充绿灯 | `pytest tests/test_production_gate_scripts.py -q` | 两个脚本的失败关闭契约全部通过 | 34 passed、2 个 Windows 文件符号链接能力跳过；新增 ANSI 归一化回归覆盖，Ubuntu CI 将执行真实链接分支 | 通过 |

## 8. 实施结果

- 完成项：GHCR runner 登录、完整 Git checkout 外模型路径、六个运行文件、只读挂载、启动哈希和 Compose 健康等待均完成工程整改。
- 未完成项：目标服务器目录创建、模型传输、GHCR 包访问权确认和真实部署/回滚。
- 与原方案差异：审阅后把两权重存在性检查扩展为与引擎一致的六文件契约，并要求 Compose v2 健康等待。
- 当前状态：工程整改已完成，真实 G0 仍待服务器证据。

## 9. 遗留问题与风险

| 编号 | 问题或风险 | 优先级 | 负责 Agent | 计划处理 Phase/任务 |
| --- | --- | --- | --- | --- |
| R-001 | 服务器 `/srv/crm/models` 尚未创建和传输权重 | P1 | 全栈开发工程师Agent | 服务器连接后 G0 |
| R-002 | GHCR 私有包的 Actions 读取权尚未在真实 runner 验证 | P1 | 全栈开发工程师Agent | staging validate/deploy |
| R-003 | 真实回滚和健康证据未产生 | P1 | 测试工程师Agent | staging rollback |

## 10. 交接事项

- 交接给：服务器运维操作人、测试工程师Agent。
- 后续任务：连接服务器，准备仓库外模型目录和环境文件，再运行 staging 三阶段门禁。
- 必须注意：环境文件路径可以进入 GitHub Environment Secret，但环境文件正文、GitHub PAT 和模型权重不得进入仓库。

## 11. 文档同步

- [x] 已同步接口变化（无接口变化）。
- [x] 已同步架构决策（沿用 G0 与不可变镜像边界）。
- [x] 已同步任务状态。
- [x] 已通知测试工程师服务器验证范围。
- [ ] 真实测试报告索引将在服务器门禁执行后更新。
