# Rootless Staging 部署实施记录

## 1. 基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | PhaseX |
| 任务编号 | PX-00（跨阶段部署治理编号，正式专项编号待补充）；关联 P4-11、REAL-FS-01/G0，Rootless 计划 Tasks 1～9 与 Task 10 域名前置 |
| 模块编号 | M00 |
| 主责 Agent | 全栈开发工程师Agent |
| 协作 Agent | 架构师Agent、共享记忆文档Agent、测试工程师Agent |
| 实施状态 | 部分完成 |
| 开始日期 | 2026-09-09 |
| 完成日期 | 未完成（Tasks 8/9 基础设施现场完成，应用部署待执行） |
| 代码位置 | `CRM智能聊天系统/`；根工作流/属性和跨角色文档 |
| 分支/工作树 | 初始 `feature/rootless-staging` / `.worktrees/rootless-staging`；域名切换 `fix/staging-domain-overselfx` / `.worktrees/staging-domain-overselfx` |
| 服务器变更 | 有；`/home/crmdeploy` Rootless 运行面及 GitHub Runner，系统 Docker 与公司容器未变更 |

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

精确回调、Compose overlay、staging 脚本、主机/入口资产、runner 工具链、工作流、配置示例、ADR/运行手册/报告及索引。当前记录已追加 Tasks 8/9 基础设施现场事实和 2026-09-10 staging 域名切换；Task 12 将继续汇总后续部署与门禁证据。

### 3.3 非目标

Tasks 8/9 仅建立 `/home/crmdeploy` Rootless 运行面与 GitHub Runner，不执行 DNS/TLS、模型复制、GHCR 应用镜像拉取、应用部署/恢复/回滚或真实店铺/模型调用。系统 Docker 与公司容器不停止、不重启、不迁移、不修复、不接管。production 方案未决定，不实现其他两平台或自动发送。

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
- 后续：Tasks 8/9 已完成基础设施现场；下一步为 Task 10 外部材料、Task 11 真实部署与恢复、Task 12 汇总证据，之后 G1～G6。

### 5.3 风险控制

| 风险 | 影响 | 应对措施 |
| --- | --- | --- |
| Docker context 覆盖 host | 误操作系统 daemon | 清除并恢复 context，精确 UID socket |
| 公司负载变化 | 越界或错误归因 | 五字段前后快照，差异立即硬停，不自动修复 |
| 空间/身份/路径漂移 | 数据落错磁盘 | 最小包安装、根盘 1.5 GiB 门槛、实际 Rootless 数据路径校验 |
| 凭据或供应链泄露 | 服务器/仓库风险 | 官方摘要、短期 stdin Token、关闭 Bash allexport、低敏输出 |
| 基础设施通过被误当应用通过 | 提前放行 | Tasks 8/9 与 Task 10/11、G1～G6、production 分别结论 |

## 6. 实际变更

### 6.1 文件变更

以下路径相对根 Git 仓库。Tasks 1～5 的源码范围以表中精确文件及提交为准；不包含模型、凭据或主机取证文件。

| 文件路径 | 变更类型 | 变更说明 | 负责 Agent |
| --- | --- | --- | --- |
| `CRM智能聊天系统/backend/app/shared/config/settings.py` | 修改 | 按环境固定 OAuth；Task 7 将 staging 纳入部署基础安全校验 | 全栈开发工程师Agent |
| `CRM智能聊天系统/backend/app/integrations/adapters.py` | 修改 | Task 7 在所有环境按显式 Mock 开关失败关闭 resolver 与 defensive send | 全栈开发工程师Agent |
| `CRM智能聊天系统/backend/tests/test_platform_adapters.py` | 修改 | Task 7 真实 resolver/send 行为测试，覆盖关闭与开发/测试显式开启对照 | 全栈开发工程师Agent |
| `CRM智能聊天系统/backend/tests/test_real_runtime_config.py` | 修改 | 回调/overlay 契约；Task 7 staging/production 基础安全矩阵及夹具环境对照 | 全栈开发工程师Agent |
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

### 6.4 2026-09-10 域名切换文件范围

- 运行行为与 CI：`.github/workflows/staging-gates.yml`、`CRM智能聊天系统/backend/app/shared/config/settings.py`。
- 测试与夹具：`test_real_runtime_config.py`、`test_platform_adapters.py`、`test_production_gate_scripts.py`、`test_real_fs05_sse_runtime.py`。
- 配置与运行文档：`CRM智能聊天系统/.env.example`、产品/production/Rootless README、Rootless design 与 implementation plan、全栈 PLAN-002。
- 权威契约与证据：ADR-004、ADR-007、管理端接口文档、本实施记录、007 测试报告以及实施/测试两个索引。
- 未变更：API 请求/响应、数据库迁移、production 域名、产品/UI 三平台定义、AI/RAG 行为和服务器运行状态。

## 7. 验证记录

完整命令、RED/GREEN 历史、准确数量和边界只在 007 报告维护；本记录不复制完整测试结论。

| 验证项 | 命令或方法 | 预期结果 | 实际结果 | 状态 |
| --- | --- | --- | --- | --- |
| Tasks 1～5 工程交接 | 逐份报告与 git log 对照 | 提交/数量可追溯 | 八个实现/修复提交均存在；最终四套回归 193 passed、2 skipped（开发自测） | 通过 |
| 公网地址 | 新旧域名行为测试与精确文本审计 | 保留 production；新 staging 精确接受，旧 staging 失败关闭 | 2026-09-10 新域名聚焦 9 passed，受影响模块 278 passed、2 skipped；历史测试事实未改写 | 通过 |
| 文档空白 | `git diff --check`、`git diff --cached --check` | 无输出、exit 0 | 两项均无输出、exit 0 | 通过 |
| Task 6 审阅修复 | Windows PowerShell 5.1/PowerShell 7.6.5 原生管道 → 本地 Bash 严格读取替身 | CRLF 转 LF；非零退出和 finally 清理保留 | 原命令 RED；文档规范化后两环境共 4 个聚焦断言通过，详见 007 报告；安装器代码和服务器均未变更 | 通过 |
| 索引/镜像/低敏 | 路径存在、清单比对、变更扫描及人工复核 | 无缺文件/摘要漂移/真实凭据 | 测试索引 92 路径、实施索引 122 路径均存在；3/3 镜像逐字符合清单；高置信凭据模式零命中，无新增真实凭据或现场摘要 | 通过 |
| Task 8/9 Ubuntu 基础设施 | 主责取证及测试工程师Agent 独立只读复核 | Rootless/Runner 可用且系统 Docker 不变 | Rootless active/enabled、数据根正确、容器 0；Runner `2.336.0` online；系统 Docker 14/12 和五字段摘要不变 | 通过 |
| Task 10/11 应用现场 | 外部材料、部署、健康、迁移、恢复与回滚 | 真实应用运行面可证 | 新域名 DNS A 已确认；公网监听/TLS/六文件模型/配置/镜像/部署/恢复/回滚待执行 | 部分完成 |

## 8. 实施结果

2026-09-09 Task 7 最终控制器复核：在 `0eb399c763928586276f8c7aa6746f95f663608d` 上，计划要求的四文件聚焦结果为 `245 passed, 2 skipped in 26.69s`，后端全量为 `1527 passed, 14 skipped, 2 warnings in 35.18s`，两项 exit 0。两条 warning 是既有 Starlette/httpx 与 passlib/argon2 依赖弃用警告；跳过项不计通过。来源为控制器新运行结果，本次仅记录，详见 007 报告 §7.4。本地仓库实现验证通过。该段保留 Task 7 结束时状态；Tasks 8/9 的后续现场结论见下方 2026-09-10 补充，Task 10～12、G1～G6 和 production 仍待执行。

2026-09-09 Task 6 最终审阅计划勘误：修改 `docs/superpowers/plans/2026-09-09-rootless-staging-deployment.md` 的 Task 10 模型摘要门槛、Task 11 入口安装/部署后激活验证顺序及兼容上一版三摘要要求，并同步既有 007 报告。当前仅两个权重摘要有清单权威，四个辅助摘要缺失则硬停；历史 `f7c0f9f9` 不直接用于成功回滚。提交主题 `docs: correct rootless live execution plan`，完整 SHA 可按精确主题查询；只校正文档，无服务器变更，live/G1～G6 仍待执行。

2026-09-09 Task 7 审阅覆盖补充：新增 integration 拒绝 staging 回调、TikTok 真实能力交叉隔离，并用 fake Docker 实际命令日志检验两个脚本各可达 Compose 操作的固定项目/profile/三层文件参数。没有修改生产代码或重写先前安全修复提交。最终聚焦 13 passed，三个完整模块 250 passed、2 skipped；Ruff/format/diff 通过。详细命令与边界在 007 报告 §7.3；提交主题 `test: harden staging boundary regressions`，完整 SHA 可按该精确主题查询。该段保留当时状态；后续控制器全量及 Tasks 8/9 结论已补充，Task 10～12/G1～G6 仍待执行。

2026-09-09 Task 7 应用安全修复：基础配置校验扩展至 staging/production；Mock resolver 与直接发送以 `ALLOW_MOCK_PLATFORM_ADAPTERS` 为授权依据，关闭时所有环境均失败关闭。development/test/integration 基础夹具以及单独的 SSE/LLM 门禁保留，三平台 UI 和真实 TikTok 能力条件不变。新增行为先 RED（52 failed、50 passed），修复后同集 GREEN（102 passed）；完整 settings/SSE/adapter 模块 213 passed，TikTok 邻接模块 64 passed，Ruff/format/diff 检查通过。准确命令、失败分解、夹具修复和时间只维护于 007 报告 §7.2。提交主题 `fix: enforce staging application security`，完整 SHA 通过 `git log --all --format='%H %s' --grep='^fix: enforce staging application security$'` 解析。该段保留产品修复当时状态；控制器全量和 Tasks 8/9 后续已补充，Task 10～12 与 G1～G6 仍待执行。

2026-09-09 Task 7 聚焦修复与全量验证补充：首次全量复核发现的两处旧 staging 测试输入已修正，提交为 `6323316f35560b6f9c755c5e46966f3ac5da27cb`（`test: align staging runtime fixtures`）。没有修改产品校验或 integration/production 回调。控制器在该修复后使用仓库外 basetemp 完成后端全量复核：`1422 passed, 14 skipped, 2 warnings in 30.00s`，exit 0；较早的新聚焦回归为 `193 passed, 2 skipped in 25.61s`，exit 0。两条依赖弃用警告与跳过项、原失败案例及静态质量证据详见 007 报告 §7.1。本次还将唯一误跟踪的 SDD `task-1-report.md` 移出 Git 索引，保留本地被忽略的原始证据。当前实施和现场验收状态不变。

2026-09-10 Tasks 8/9 基础设施现场补充：`crmdeploy` UID/GID 1004 的 Rootless Docker active/enabled，数据根 `/home/crmdeploy/.local/share/docker`，容器 0；Runner 工具链从清单官方 URL 经 SHA-256 密封缓存安装，PowerShell `7.6.5`、Runner.Listener `2.336.0`，用户服务 active/enabled/running。GitHub 唯一 runner `crm-staging-192-168-110-210` online、busy=false、四个标签完整。系统 Docker 仍为 `/var/lib/docker`、14 个/运行中 12 个，五字段 SHA-256 `d807427f814e97ffb27ed16a5c6409ab732def8b27841fe209a9b47880226cdb` 与基线一致。测试工程师Agent 独立只读现场复核 READY，Critical/Important/Minor 均为 0。完整归档、版本资产、PR/CI 和失败关闭证据见 007 报告 §8.1 与 Runner 001 报告。

2026-09-10 staging 域名切换补充：经用户批准，当前 staging 公共地址、OAuth callback、Webhook、TLS 目录、GitHub Actions 精确门禁及活动运行文档统一切换到 `staging.overselfx.com`；production 地址保持 `www.hophorsefit.com`。测试先 RED（3 failed、6 passed），修复后聚焦 9 passed，四个受影响模块 278 passed、2 skipped，后端全量 1552 passed、16 skipped、2 个既有依赖 warning，Ruff check/format 通过。当前执行环境的系统解析器已将 DNS A 记录解析到 `183.158.225.78`；NAT 为用户确认，需入口监听后复验，TLS 和其余 Task 10/11 材料仍未完成。完整证据见 007 报告 §8.2。

- 完成项：Tasks 1～7 仓库工程及文档；Task 8 Rootless 主机基础运行面；Task 9 Runner 官方工具链、用户服务和 GitHub online 现场验收。
- 未完成项：Task 10 外部材料、Task 11 应用部署/恢复/回滚、Task 12 后续汇总；G1～G6；production。
- 与原方案差异：架构师批准在共享接口、产品 README 和全栈 PLAN-002 各追加一条 dated 勘误，不重写历史或修改接口结构；若不修正会导致运行配置与共享接口权威冲突，并让操作人沿用错误 staging 回调。入口 socket 先于首次 deploy 监听以满足脚本公网探针，监听不等于健康；已识别历史回滚版本回调不兼容、辅助模型摘要不足，均列为停点。
- 当前状态：部分完成。Tasks 8/9 基础设施运行面就绪；尚不构成 staging 应用可用、G1～G6 或 production 签署通过。

## 9. 遗留问题与风险

| 编号 | 问题或风险 | 优先级 | 负责 Agent | 计划处理 Phase/任务 |
| --- | --- | --- | --- | --- |
| R-RLS-001 | Ubuntu 主机、Rootless、Runner 原生依赖和 systemd 动态行为（Tasks 8/9 现场及独立只读复核通过） | Closed | 全栈开发工程师Agent/测试工程师Agent | Task 8～9 |
| R-RLS-002 | DNS A 已确认；入口监听后的公网 TCP、公信 TLS、真实配置、外部模型及新 main 镜像尚未取得 | P1 | 全栈开发工程师Agent | Task 10 |
| R-RLS-003 | 历史 f7c0f9f9 不接受 staging 专用回调，回滚兼容性阻断 | P1 | 架构师Agent | Task 11 前 |
| R-RLS-004 | 四个辅助模型 JSON 缺少清单 SHA-256；只有两份权重已登记 | P2 | AIAgent开发工程师Agent/架构师Agent | Task 10 |
| R-RLS-005 | 独立日志复测及 G1～G6 真实验证未完成 | P1 | 测试工程师Agent | G0～G6 |

## 10. 交接事项

- 交接给：架构师Agent、测试工程师Agent、后续部署执行者。
- 后续任务：按已批准计划继续准备 Task 10 TLS、模型、配置与候选镜像材料，入口监听后复验公网 NAT 并 validate；通过后执行 Task 11 应用部署/恢复/回滚，Task 12 继续追加低敏现场记录。
- 必须注意：任何系统容器五字段变化都硬停；旧版本回调与模型辅助摘要问题先确认；原始配置、Token、私钥、模型和业务数据不得进入报告或 Git；数据删除需要单独明确批准。

## 11. 文档同步

- [x] 已同步接口变化（§11.7 勘误，不改接口结构）。
- [x] 已同步架构决策 ADR-007/ADR-004。
- [x] 已同步任务状态到本记录和两个索引，保持部分完成。
- [x] 已在 007 报告追加 Task 9 主责和独立现场证据，并保留 Task 10～12/G1～G6 边界。
- [x] 测试报告索引已更新 Tasks 8/9 基础设施结论，production 状态保持未放行。
