# Rootless Staging 部署实施记录

## 1. 基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | PhaseX |
| 任务编号 | PX-00（跨阶段部署治理编号，正式专项编号待补充）；关联 P4-11、REAL-FS-01/G0，Rootless 计划 Tasks 1～6 |
| 模块编号 | M00 |
| 主责 Agent | 全栈开发工程师Agent |
| 协作 Agent | 架构师Agent、共享记忆文档Agent；测试工程师Agent待独立复核 |
| 实施状态 | 部分完成 |
| 开始日期 | 2026-09-09 |
| 完成日期 | 未完成（仓库工程已交付，真实部署待执行） |
| 代码位置 | `CRM智能聊天系统/`；根工作流/属性和跨角色文档 |
| 分支/工作树 | `feature/rootless-staging` / `.worktrees/rootless-staging` |
| 服务器变更 | 无 |

## 2. 需求与依据

- 产品需求：`共享记忆文档/智能客服平台 — 产品需求文档（PRD）V2.0.md` 第 2 节首版范围说明；保留三平台产品定义。
- 接口依据：`共享记忆文档/智能客服平台 — 管理端接口文档.md` §11.7 OAuth、§11.17 人工发送、§11.18 SSE。
- 架构依据：ADR-004、ADR-006、`架构师/ADR-007-INFRA-Rootless-Staging部署边界-v1.0.md`；已批准 Rootless design。
- 任务依据：`共享记忆文档/开发任务拆解（按人天分配）.md` P4-11；`docs/superpowers/plans/2026-09-09-rootless-staging-deployment.md` Tasks 1～6。
- 验收依据：`共享记忆文档/MVP范围与验收标准.md` §1.1、§3.7；生产放行检查表 v1.1 G0～G6/G8。
- 代码规范：`共享记忆文档/代码编写手册.md`；本记录遵守实施记录文档规范。

## 3. 目标、范围与非目标

### 3.1 实施目标

交付可审阅的 Rootless staging 工程、运维步骤和证据边界，使后续在 `/home/crmdeploy` 独立部署具有可重放依据。

### 3.2 实施范围

精确回调、Compose overlay、staging 脚本、主机/入口资产、runner 工具链、工作流、配置示例、ADR/运行手册/报告及索引。当前记录截至 Task 6；Task 12 在此追加现场事实。

### 3.3 非目标

本轮无服务器安装/连接、DNS/TLS 操作、模型复制、runner 注册、GHCR 发布/拉取、部署/恢复/回滚或真实店铺/模型调用。系统 Docker 与公司容器不停止、不重启、不迁移、不修复、不接管。production 方案未决定，不实现其他两平台或自动发送。

## 4. 实施前确认

- [x] 已读取共享记忆文档清单。
- [x] 已读取 PRD、接口、任务拆解、团队职责和 MVP 标准。
- [x] 已读取代码编写手册、实施记录/测试命名规范和所需任务指引。
- [x] 已确认 Phase、任务编号、M00 和主责 Agent。
- [x] 已确认依赖、风险和验收方式；接口历史固定地址冲突经架构师批准最小勘误。

## 5. 实施方案

### 5.1 方案说明

Rootless 用户固定 UID/GID 1004、home `/home/crmdeploy`、socket `unix:///run/user/1004/docker.sock`、Compose 项目 `crm-staging`。只有 systemd 80/443 socket proxy 转发至回环 10080/10443。staging 使用独立域名，integration/production 固定 www；全部真实能力在基础部署与回滚中关闭。

### 5.2 依赖关系

- 前置：既有 main `433b3e5`、设计 `7bac358`、计划 `b5a639f`、用户批准方式 1。
- 后续：Task 7 工程复核/CI/PR；Tasks 8～11 主机、runner、外部材料、真实部署与恢复；Task 12 现场证据；之后 G1～G6。

### 5.3 风险控制

| 风险 | 影响 | 应对措施 |
| --- | --- | --- |
| Docker context 覆盖 host | 误操作系统 daemon | 清除并恢复 context，精确 UID socket |
| 公司负载变化 | 越界或错误归因 | 五字段前后快照，差异立即硬停，不自动修复 |
| 空间/身份/路径漂移 | 数据落错磁盘 | 最小包安装、根盘 1.5 GiB 门槛、实际 Rootless 数据路径校验 |
| 凭据或供应链泄露 | 服务器/仓库风险 | 官方摘要、短期 stdin Token、关闭 Bash allexport、低敏输出 |
| 本地测试被误当现场通过 | 提前放行 | 四阶段独立结论；当前现场项全部待执行 |

## 6. 实际变更

### 6.1 文件变更

以下路径相对根 Git 仓库。Tasks 1～5 的源码范围以表中精确文件及提交为准；不包含模型、凭据或主机取证文件。

| 文件路径 | 变更类型 | 变更说明 | 负责 Agent |
| --- | --- | --- | --- |
| `CRM智能聊天系统/backend/app/shared/config/settings.py` | 修改 | 按环境固定 OAuth | 全栈开发工程师Agent |
| `CRM智能聊天系统/backend/tests/test_real_runtime_config.py` | 修改 | 回调/overlay 契约 | 全栈开发工程师Agent |
| `CRM智能聊天系统/backend/tests/test_real_fs05_sse_runtime.py` | 修改 | Task 7 修正两处旧 staging 回调测试输入，保留 SSE/DeepSeek 原断言 | 全栈开发工程师Agent |
| `CRM智能聊天系统/docker-compose.rootless-staging.yml` | 新增 | 回环端口与四服务关闭能力 | 全栈开发工程师Agent |
| `CRM智能聊天系统/scripts/Test-StagingProductionGates.ps1` | 修改 | Rootless validate/deploy | 全栈开发工程师Agent |
| `CRM智能聊天系统/scripts/Invoke-StagingRollbackDrill.ps1` | 修改 | Rootless 回滚门禁 | 全栈开发工程师Agent |
| `CRM智能聊天系统/backend/tests/test_production_gate_scripts.py` | 修改 | context/工作流/门禁回归 | 全栈开发工程师Agent |
| `CRM智能聊天系统/deploy/staging/rootless/bootstrap-host.sh` | 新增 | 最小主机引导与容器保护证据 | 全栈开发工程师Agent |
| `CRM智能聊天系统/deploy/staging/rootless/install-entry-proxy.sh` | 新增 | 可逆入口、激活后幂等 | 全栈开发工程师Agent |
| `CRM智能聊天系统/deploy/staging/rootless/systemd/crm-staging-http.socket` | 新增 | 80 监听 | 全栈开发工程师Agent |
| `CRM智能聊天系统/deploy/staging/rootless/systemd/crm-staging-http.service` | 新增 | 转发回环 10080 | 全栈开发工程师Agent |
| `CRM智能聊天系统/deploy/staging/rootless/systemd/crm-staging-https.socket` | 新增 | 443 监听 | 全栈开发工程师Agent |
| `CRM智能聊天系统/deploy/staging/rootless/systemd/crm-staging-https.service` | 新增 | 转发回环 10443 | 全栈开发工程师Agent |
| `CRM智能聊天系统/backend/tests/test_rootless_staging_assets.py` | 新增 | 静态资产与局部 Bash Token 回归 | 全栈开发工程师Agent |
| `.gitattributes` | 修改 | systemd 单元 LF | 全栈开发工程师Agent |
| `CRM智能聊天系统/deploy/staging/rootless/install-runner.sh` | 新增 | 校验归档、用户安装和注册 | 全栈开发工程师Agent |
| `CRM智能聊天系统/deploy/staging/rootless/toolchain-manifest.json` | 新增 | 固定 Runner/PowerShell 官方版本摘要 | 全栈开发工程师Agent |
| `CRM智能聊天系统/deploy/staging/rootless/systemd/user/crm-staging-runner.service` | 新增 | 用户 runner、固定 socket/PATH | 全栈开发工程师Agent |
| `.github/workflows/staging-gates.yml` | 修改 | staging URL、UID/DockerHost、短期 GHCR | 全栈开发工程师Agent |
| `CRM智能聊天系统/deploy/staging/rootless/README.md` | 新增 | 唯一运维步骤、停点与证据边界 | 全栈开发工程师Agent |
| `架构师/ADR-007-INFRA-Rootless-Staging部署边界-v1.0.md` | 新增 | 落实已批准架构决策 | 架构师Agent/全栈开发工程师Agent |
| `CRM智能聊天系统/.env.example` | 修改 | 注释 staging 示例、保留生产值 | 全栈开发工程师Agent |
| `CRM智能聊天系统/deploy/production/README.md` | 修改 | Rootless 链接、生产与历史镜像边界 | 全栈开发工程师Agent |
| `架构师/ADR-004-REAL-真实平台与DeepSeek生产接入边界-v1.0.md` | 修改 | 分环境固定地址表 | 全栈开发工程师Agent |
| `架构师/验收-001-CROSS-真实环境生产放行检查表-v1.1.md` | 修改 | 四结论分离，现场项待执行 | 全栈开发工程师Agent |
| `共享记忆文档/智能客服平台 — 管理端接口文档.md` | 修改 | 架构批准的 §11.7 最小地址勘误 | 全栈开发工程师Agent |
| `CRM智能聊天系统/README.md` | 修改 | 架构批准的历史回调勘误 | 全栈开发工程师Agent |
| `全栈开发工程师/PLAN-002-REAL-真实TikTok与DeepSeek运行面实施计划-v1.0.md` | 修改 | 架构批准的历史回调勘误 | 全栈开发工程师Agent |
| `测试工程师/Phase4-P4-00-全栈开发工程师Agent-M00-Rootless-Staging运行面-综合测试-007.md` | 新增 | 工程证据汇编，独立结论待复核 | 全栈开发工程师Agent |
| `共享记忆文档/实施记录/PhaseX-PX-00-全栈开发工程师Agent-Rootless-Staging部署-001.md` | 新增 | 本记录 | 全栈开发工程师Agent |
| `共享记忆文档/测试报告索引.md` | 修改 | 007 报告与当前边界 | 共享记忆文档Agent/全栈开发工程师Agent |
| `共享记忆文档/实施记录索引.md` | 修改 | 登记部分完成 | 共享记忆文档Agent/全栈开发工程师Agent |

提交链（保留每次修复，不改写历史）：

| 提交 | 主题 |
| --- | --- |
| `a6ef811` | feat: isolate staging TikTok callback |
| `9853ff4` | build: add rootless staging compose overlay |
| `a23d070` | build: enforce rootless staging gates |
| `2a9e749` | fix: clear inherited docker context |
| `2c38c92` | build: add rootless staging host bootstrap |
| `8436cbd` | fix: preserve entry proxy idempotency after activation |
| `42e06a6` | ci: connect staging gates to rootless runner |
| `205a6ca` | fix: prevent runner token allexport leakage |

Task 6 文档提交主题固定 `docs: document rootless staging operations`；自身提交通过 `git log --follow -- <本记录路径>` 解析，避免自引用摘要。Tasks 1～5 的本地交接记录是来源，正式工程证据汇编在测试工程师目录。

### 6.2 接口、数据和配置变更

- API：不新增或改变请求/响应，只有 staging 回调配置精确映射变化。
- 数据库：无新迁移，目标 head 继续 `023_marketing_review_idempotency`，真实主机未验证。
- 配置：新增固定 Rootless socket/项目/overlay；四个 staging 公网变量作为注释示例，生产值保留。
- AI：不改 Prompt、RAG、模型策略或阈值；部署能力全部失败关闭。

### 6.3 关键实现说明

精确回调和固定环境阻止跨环境误配；门禁把 DockerHost/context 纳入环境快照并恢复。入口安装器验证逐字 unit/权限/端口/PID，失败撤销本次新增变化。Runner 在读取 Token 前关闭 allexport 并清理导出属性，摘要验证后才解压，用户服务不具 root 权限。复杂分支已在代码中保留中文注释。

## 7. 验证记录

完整命令、RED/GREEN 历史、准确数量和边界只在 007 报告维护；本记录不复制完整测试结论。

| 验证项 | 命令或方法 | 预期结果 | 实际结果 | 状态 |
| --- | --- | --- | --- | --- |
| Tasks 1～5 工程交接 | 逐份报告与 git log 对照 | 提交/数量可追溯 | 八个实现/修复提交均存在；最终四套回归 193 passed、2 skipped（开发自测） | 通过 |
| 公网地址 | 两次 `git grep -n` 精确回调 | 保留生产，staging 仅环境语境 | www 27 行、staging 15 行；历史跨环境说法已加架构批准勘误，历史测试报告不改写 | 通过 |
| 文档空白 | `git diff --check`、`git diff --cached --check` | 无输出、exit 0 | 两项均无输出、exit 0 | 通过 |
| Task 6 审阅修复 | Windows PowerShell 5.1/PowerShell 7.6.5 原生管道 → 本地 Bash 严格读取替身 | CRLF 转 LF；非零退出和 finally 清理保留 | 原命令 RED；文档规范化后两环境共 4 个聚焦断言通过，详见 007 报告；安装器代码和服务器均未变更 | 通过 |
| 索引/镜像/低敏 | 路径存在、清单比对、变更扫描及人工复核 | 无缺文件/摘要漂移/真实凭据 | 测试索引 92 路径、实施索引 122 路径均存在；3/3 镜像逐字符合清单；高置信凭据模式零命中，无新增真实凭据或现场摘要 | 通过 |
| Ubuntu/现场 | Tasks 8～11 | 隔离、健康、恢复与回滚可证 | 无现场执行；DNS/TLS/模型/配置/runner 待提供 | 未执行 |

## 8. 实施结果

2026-09-09 Task 7 聚焦修复补充：首次全量复核发现的两处旧 staging 测试输入已修正，提交主题为 `test: align staging runtime fixtures`（完整 SHA 通过该主题的 `git log` 解析）。没有修改产品校验或 integration/production 回调。两个原失败案例与环境映射/SSE 模块回归、静态质量检查已有新证据，详见 007 报告 §7.1；控制器仍负责修复后的全量后端复核。当前实施和现场验收状态不变。

- 完成项：Tasks 1～5 工程资产及修复；Task 6 文档/ADR/示例/报告/索引同步。
- 未完成项：Task 7 全量复核及远端集成；Tasks 8～12 现场部署与证据；G1～G6；production。
- 与原方案差异：架构师批准在共享接口、产品 README 和全栈 PLAN-002 各追加一条 dated 勘误，不重写历史或修改接口结构；若不修正会导致运行配置与共享接口权威冲突，并让操作人沿用错误 staging 回调。入口 socket 先于首次 deploy 监听以满足脚本公网探针，监听不等于健康；已识别历史回滚版本回调不兼容、辅助模型摘要不足，均列为停点。
- 当前状态：部分完成。仓库工程交付不构成基础运行面、失败关闭部署、真实门禁或生产签署通过。

## 9. 遗留问题与风险

| 编号 | 问题或风险 | 优先级 | 负责 Agent | 计划处理 Phase/任务 |
| --- | --- | --- | --- | --- |
| R-RLS-001 | Ubuntu 原生依赖、主机状态和 systemd 动态行为未验证 | P1 | 全栈开发工程师Agent/测试工程师Agent | Task 8～9 |
| R-RLS-002 | DNS/TLS/真实配置/外部模型及新 main 镜像尚未取得 | P1 | 全栈开发工程师Agent | Task 7/10 |
| R-RLS-003 | 历史 f7c0f9f9 不接受 staging 专用回调，回滚兼容性阻断 | P1 | 架构师Agent | Task 11 前 |
| R-RLS-004 | 四个辅助模型 JSON 缺少清单 SHA-256；只有两份权重已登记 | P2 | AIAgent开发工程师Agent/架构师Agent | Task 10 |
| R-RLS-005 | 独立日志复测及 G1～G6 真实验证未完成 | P1 | 测试工程师Agent | G0～G6 |

## 10. 交接事项

- 交接给：架构师Agent、测试工程师Agent、后续部署执行者。
- 后续任务：Task 7 分支复核后按已批准计划逐项执行；Task 12 追加低敏现场记录。
- 必须注意：任何系统容器五字段变化都硬停；旧版本回调与模型辅助摘要问题先确认；原始配置、Token、私钥、模型和业务数据不得进入报告或 Git；数据删除需要单独明确批准。

## 11. 文档同步

- [x] 已同步接口变化（§11.7 勘误，不改接口结构）。
- [x] 已同步架构决策 ADR-007/ADR-004。
- [x] 已同步任务状态到本记录和两个索引，保持部分完成。
- [x] 已在 007 报告列明测试工程师待覆盖范围。
- [x] 测试报告索引已登记工程证据与“独立测试结论待复核”，正式现场复核后再更新。
