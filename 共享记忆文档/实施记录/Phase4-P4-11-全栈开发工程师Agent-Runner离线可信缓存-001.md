# Runner 离线可信缓存实施记录

## 1. 基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase4 |
| 任务编号 | P4-11；关联 Rootless 部署计划 Task 9 |
| 模块编号 | M00 |
| 主责 Agent | 全栈开发工程师Agent |
| 协作 Agent | 架构师Agent、测试工程师Agent、共享记忆文档Agent |
| 实施状态 | 已完成（仓库工程范围） |
| 开始日期 | 2026-09-09 |
| 完成日期 | 2026-09-10 |
| 代码位置 | `CRM智能聊天系统/deploy/staging/rootless/`、`CRM智能聊天系统/backend/tests/` |
| 分支/工作树 | `fix/runner-offline-cache` / `.worktrees/runner-offline-cache` |
| 基础提交 | `77d9f8f78844f08e5840e505af53ef87e9484c0b` |
| 服务器变更 | 无 |

## 2. 需求与依据

- 产品需求：`共享记忆文档/智能客服平台 — 产品需求文档（PRD）V2.0.md`（首发 TikTok 人工辅助范围）。
- 接口依据：`共享记忆文档/智能客服平台 — 管理端接口文档.md`；本次不变更 API。
- 架构依据：`架构师/ADR-007-INFRA-Rootless-Staging部署边界-v1.0.md`。
- 任务依据：`共享记忆文档/开发任务拆解（按人天分配）.md` P4-11；`docs/superpowers/plans/2026-09-09-runner-offline-trusted-cache.md` Tasks 1～3。
- 验收依据：`共享记忆文档/MVP范围与验收标准.md` 第 3.7 节及 Rootless 运行手册 Task 9。
- 代码规范：`共享记忆文档/代码编写手册.md`。

## 3. 目标、范围与非目标

### 3.1 实施目标

- 让 Runner 安装器优先使用经清单 SHA-256 复核的本地密封归档。
- 密封归档不可信时失败关闭；只有路径不存在时才保留官方 GitHub HTTPS 下载。

### 3.2 实施范围

- Runner 安装器、Rootless 资产测试、运行手册、ADR-007 补充、实施/测试记录及两个索引。

### 3.3 非目标

- 不连接或修改服务器，不下载真实大归档，不申请/传递 Runner Token。
- 不修改 Rootless Docker、公司系统 Docker、systemd Runner 身份、API、数据库、镜像或 production 方案。

## 4. 实施前确认

- [x] 已读取共享记忆文档文件清单及相关 PRD、接口、任务、团队职责和 MVP 标准。
- [x] 已读取代码手册、实施记录规范、测试报告命名规范和 TDD/验证 Skill。
- [x] 已确认 Phase4/P4-11/M00、主责 Agent、依赖、验收与不触及服务器的范围。
- [x] 文档之间无本任务冲突。

## 5. 实施方案

### 5.1 方案说明

已验证的 JSON 清单同时输出工具名、官方文件名、URL 和 SHA-256。安装路径先校验 `/home/crmdeploy` 及遍历到的全部既有目录是 UID 1004 拥有、非链接且组/其他用户不可写；`prepare_verified_archive` 再对 `sealed-<filename>` 执行普通文件、非链接、属主、权限和摘要门禁。路径不存在时才下载原官方 URL，两条归档路径共用同一摘要校验、私有临时解压和原子提升流程。运行手册另将 clean `main` 的三项 Runner 资产逐文件验签并原子提升到带完整 HEAD 的版本目录；每个 SSH 边界重复验证父路径，注册前重新推导 HEAD、重算本地摘要并复验远端版本目录。

### 5.2 依赖关系

- 前置依赖：已合并的 Rootless 资产、`toolchain-manifest.json`、Task 8 Rootless 运行面。
- 后续依赖：合并后 Task 9 本地官方下载、SCP 传输、服务器重验和 Runner 注册。

### 5.3 风险控制

| 风险 | 影响 | 应对措施 |
| --- | --- | --- |
| 缓存被替换或链接劫持 | 执行非审阅工具 | 类型、链接、UID、组/其他写权限和 SHA-256 任一不符立即失败 |
| 固定旧目录与合并代码漂移 | 调用未经本轮审阅的安装器 | clean `main` 三项资产进入唯一临时目录，逐文件验签后按 40 位 HEAD 原子提升；Token 阶段重新推导同一 HEAD |
| 父目录或跨 SSH 间隙被替换 | 末级文件校验被不安全路径绕过 | `/home/crmdeploy` 与每个既有父目录均校验 UID、类型、链接和 mode；每次 SSH 独立重验，不依赖前次结果或权限收敛 |
| 损坏缓存被网络绕过 | 问题被隐藏 | 只要确定性路径存在就禁止 fallback |
| 本地转运被误当镜像源 | 供应链漂移 | 只从清单原官方 URL 下载，传输前后同摘要复核 |
| 仓库自测被误当现场通过 | 越过发布门禁 | 报告明确 Task 9、Ubuntu 和 GitHub online 仍未执行 |

## 6. 实际变更

### 6.1 文件变更

| 文件路径 | 变更类型 | 变更说明 | 负责 Agent |
| --- | --- | --- | --- |
| `CRM智能聊天系统/deploy/staging/rootless/install-runner.sh` | 修改 | 增加 Home/全部既有目录及密封归档的类型、属主、权限和摘要检查 | 全栈开发工程师Agent |
| `CRM智能聊天系统/backend/tests/test_rootless_staging_assets.py` | 修改 | 增加目录行为、跨 SSH 重验、Token 前最终复验、权限、坏摘要、版本资产调用，以及版本资产/工具归档两个 Windows SCP `0664` 规范化顺序回归 | 全栈开发工程师Agent |
| `CRM智能聊天系统/deploy/staging/rootless/README.md` | 修改 | 补充每个 SSH 边界父路径重验、Token 前本地重哈希和远端最终复验；在两个唯一 `0700` incoming 目录内先拒绝链接/错属主，再逐文件精确收紧权限 | 全栈开发工程师Agent |
| `架构师/ADR-007-INFRA-Rootless-Staging部署边界-v1.0.md` | 修改 | 记录离线可信缓存供应链边界 | 架构师Agent/全栈开发工程师Agent |
| `共享记忆文档/实施记录/Phase4-P4-11-全栈开发工程师Agent-Runner离线可信缓存-001.md` | 新增 | 本实施记录 | 全栈开发工程师Agent |
| `测试工程师/Phase4-P4-11-全栈开发工程师Agent-M00-Runner离线可信缓存-综合测试-001.md` | 新增 | 独立测试工程师最终复测报告，显式保留 Task 9 现场门禁 | 测试工程师Agent/全栈开发工程师Agent |
| `共享记忆文档/实施记录索引.md`、`共享记忆文档/测试报告索引.md` | 修改 | 登记本次交付和结论 | 共享记忆文档Agent/全栈开发工程师Agent |

### 6.2 接口、数据和配置变更

- API：不适用，无请求/响应变更。
- 数据库：不适用，无迁移。
- 配置项：不新增环境变量；新增 checkout 外的确定性文件约定 `sealed-<manifest filename>`。
- AI：不适用，不变更 Prompt、模型、RAG、工具或阈值。

### 6.3 关键实现说明

安装器不从 URL 在 Bash 中再推导文件名，而是在已校验 JSON 边界输出文件名。`check_existing_directory` 统一检查 Home 与 `check_directory` 遍历到的每个既有目录；损坏、错属主、组/其他用户可写、非普通文件和符号链接都不能触发 `curl`。运行手册的 bootstrap prepare、verify/promote、cache prepare、verify/promote 及 Token 前最终复验均自包含路径门禁；Token 申请前重算三项本地 SHA 并核对远端版本目录，失败时不会申请 Token。携带 Token 的 SSH 使用 `$invokeVerifiedRunner`，在同一远端进程内再次执行完整 `$verifyRunnerBootstrap`，成功后才从 stdin 读取并规范化 Token；不使用旧嵌套 `bash -c` 引号。注册参数、幂等、systemd 用户服务和 Rootless socket 逻辑保持不变。

## 7. 验证记录

| 验证项 | 命令或方法 | 预期结果 | 实际结果 | 状态 |
| --- | --- | --- | --- | --- |
| TDD RED | `python -m pytest tests/test_rootless_staging_assets.py -q -k 'sealed_archive' --tb=short -p no:cacheprovider --basetemp=<repo-outside>` | 新行为因生产实现缺失而失败 | `4 failed, 1 skipped, 27 deselected`；失败点为无 `prepare_verified_archive` | 通过（RED 有效） |
| TDD GREEN | 同文件完整测试，使用新的仓库外 basetemp | 密封缓存正向/失败/fallback 与历史契约通过 | `31 passed, 1 skipped in 0.55s`；skip 为 Windows 无文件符号链接权限 | 通过 |
| 中间测试装置修复 | 实现后的两轮受控 Bash 测试 | 本地网络替身必须真正截获 `curl` | 先得 `1 failed, 3 passed, 1 skipped`，再得 `2 failed, 29 passed, 1 skipped`；原因是 Git Bash 未命中 Windows PATH 替身，改用 Bash 函数替身后关闭 | 通过 |
| 审阅修复 RED | 聚焦版本化资产、精确 chmod、权限与官方下载坏摘要 | 缺口必须由新测试捕获 | `6 failed, 1 passed, 32 deselected in 0.72s`；失败对应版本资产、通配符与四种可写权限，坏摘要旧行为已满足 | 通过（RED 有效） |
| 审阅修复 GREEN | 同一聚焦集合 | 最小实现关闭缺口 | `7 passed, 32 deselected in 0.41s` | 通过 |
| 父路径 UID 补充 RED/GREEN | 版本资产父路径 UID 1004 精确契约 | 缺失时失败，补充后通过 | `1 failed` → `1 passed` | 通过 |
| 2026-09-10 独立 QA（本轮 Important 修复前） | 测试工程师Agent 独立执行双文件回归与静态检查 | 仓库工程范围无失败，skip 不冒充通过 | `98 passed, 3 skipped in 26.08s`；仓库工程有条件通过，Task 9 仍阻塞 | 通过（历史独立证据） |
| 第二次复审 RED | 聚焦父目录与跨 SSH/Token 前重验 | 新 Important 必须被测试捕获 | `8 failed, 1 skipped, 39 deselected in 0.21s` | 通过（RED 有效） |
| 第二次复审 GREEN | 同一聚焦集合 | 最小实现关闭审阅缺口 | `8 passed, 1 skipped, 39 deselected in 0.35s` | 通过（开发自测） |
| SSH 错误传播补充 RED/GREEN | 每个远端门禁启用 `set -euo pipefail` | 任一 guard 失败立即阻止后续命令 | `1 failed` → `1 passed in 0.02s` | 通过（开发自测） |
| 第二次复审单文件/双文件回归 | `pytest test_rootless_staging_assets.py`；`pytest test_rootless_staging_assets.py test_production_gate_scripts.py` | 新增目录与跨 SSH 契约及历史回归无失败 | 单文件 `46 passed, 2 skipped in 1.30s`；双文件 `106 passed, 4 skipped in 27.79s` | 通过（开发自测） |
| 2026-09-10 独立 QA（最后变更前） | 测试工程师Agent 使用新仓库外 basetemp 独立执行双文件回归和静态检查 | 当时修订仓库工程无失败，Windows skip 不冒充通过 | session `85844` 完成至 `[100%]`、exit 0，精确 `106 passed, 4 skipped`；Ruff、Bash、PowerShell AST、路径权限与 Token 前重验检查通过 | 通过（历史独立证据） |
| 最终复审 RED/GREEN | Token-bearing SSH 同一进程复验契约 | 缺少 `$invokeVerifiedRunner` 时失败，最小实现后通过 | `1 failed in 0.10s` → `1 passed in 0.02s` | 通过（开发自测） |
| 最终复审双文件回归 | `pytest test_rootless_staging_assets.py test_production_gate_scripts.py` | 当前树相关回归无失败 | 首轮 `1 failed, 106 passed, 4 skipped` 暴露旧静态断言仍要求内联安装器；修正断言并单测 `1 passed` 后，以新 basetemp 重跑得到 `107 passed, 4 skipped in 32.40s`、exit 0 | 通过（开发自测） |
| 2026-09-10 最终独立 QA | 测试工程师Agent 使用新仓库外 basetemp 独立执行双文件回归与同进程复验静态检查 | 最终树无失败，Windows skip 不冒充通过 | session `74210` 完成至 `[100%]`、exit 0，精确 `107 passed, 4 skipped`；`$invokeVerifiedRunner` 同进程复验顺序、Ruff、Bash 和 PowerShell AST 均通过 | 通过（仓库工程范围） |
| PR #13 Linux CI | GitHub Actions run `34429552119` 后端/前端质量门禁 | Ubuntu 动态覆盖本地跳过案例，完整工程无回归 | 后端 `1552 passed, 12 skipped, 3 warnings`；Rootless 资产测试无 skip；前端门禁通过 | 通过 |
| Task 9 首次版本资产传输 | 目标 Ubuntu 26.04；合并 SHA `d5d45ef1d0a513b54d3cf4cffbf34dad72fd0393` | 不安全模式必须失败关闭，不得提升或申请 Token | Windows SCP 将三文件落为 `0664`，旧 strict check 在 chmod 前拒绝；三个 SHA 和 `bash -n` 正确，版本目标未生成，Token 未申请，Runner 未安装 | 失败关闭（缺陷已定位） |
| SCP 模式修复 TDD | 新增规范化顺序测试后执行单测、单文件和双文件回归 | 先 regular/non-link/UID 1004，再精确 chmod/strict check/SHA/原子提升 | RED `1 failed`；GREEN 单测 `1 passed`、单文件 `48 passed, 2 skipped`、双文件 `108 passed, 4 skipped in 34.95s` | 通过（开发自测） |
| SCP 模式修复独立 QA/审阅 | 独立测试与安全审阅只读复核 | 无 Critical/Important/Minor，跨平台流程可继续进入 CI | 双文件 `108 passed, 4 skipped`、Ruff/Bash/8 个 PowerShell AST/diff/凭据检查通过；两位审阅者均 READY | 通过（仓库工程范围） |
| PR #14 Linux CI/合并 | GitHub Actions run `34437014325` 与 squash merge | 修复在 Linux/前端全量门禁通过后进入 main | 后端/前端均通过；合并 SHA `415b138e7674c2c700808edad84c7f3698d9b64a` | 通过 |
| 版本资产重传 | 新 main 三项资产重新传入唯一目录并远端验证 | `0664` 安全规范化后完成摘要、Bash 与原子提升 | incoming 与版本目录各三项 SHA-256 全部 OK；目标为 `rootless-staging-bootstrap-415b138e...` | 通过 |
| 工具归档模式补充 TDD | 上传前静态复核发现 archive incoming 存在同样顺序缺口 | 泛化 helper，同时覆盖 bootstrap 与 archive | RED `1 failed`；GREEN 单文件 `49 passed, 2 skipped`、双文件 `109 passed, 4 skipped in 34.68s` | 通过（开发自测） |
| 工具归档模式独立 QA/审阅 | 最终树联合回归、Ruff/Bash/PowerShell AST、安全顺序、diff/凭据 | 仓库工程无阻断项 | 独立 `109 passed, 4 skipped`、Ruff/格式/Bash/8 个 AST/差异/凭据均通过；安全审阅 Critical/Important/Minor 为 0 | READY |
| Bash/Ruff/静态检查 | `bash -n install-runner.sh`；Ruff check/format；README PowerShell AST 解析；`git diff --check` | 语法、格式和手册代码块无错误 | Bash exit 0；Ruff 通过；8 个 PowerShell 块零解析错误；diff 通过 | 通过 |
| Task 9 现场 | 合并后服务器安装、GitHub online/标签及公司容器不变复核 | 全部现场门禁取证 | 本地官方下载/验签完成；版本资产首次 SCP 失败关闭；远端归档、安装、注册与事后复核未执行 | 部分执行 |

## 8. 实施结果

- 完成项：仓库代码、自动化行为测试、运维流程、架构边界和可追溯文档已实施。
- 未完成项：Task 9 工具归档上传、原生安装、注册和 online 现场仍待工具归档模式补丁合并后继续。
- 与原方案差异：无生产行为差异；Windows 动态符号链接案例跳过，保留静态契约并要求 Linux 复测。
- 当前状态：PR #14 已 squash merge 为 `415b138e7674c2c700808edad84c7f3698d9b64a`，版本资产重传和原子提升通过。归档上传前复核发现 archive incoming 同样需模式规范化，已以 TDD 泛化 helper；独立 QA/安全审阅均 READY，当前补丁待 GitHub Flow CI/合并。Task 9 未完成，不构成 G1～G6 或 production 放行。

## 9. 遗留问题与风险

| 编号 | 问题或风险 | 优先级 | 负责 Agent | 计划处理 Phase/任务 |
| --- | --- | --- | --- | --- |
| R-CACHE-002 | 本地官方归档、受保护传输、Ubuntu 原生解压和 GitHub Runner online 未执行 | P1 | 全栈开发工程师Agent/测试工程师Agent | Task 9 |
| R-CACHE-003 | 密封文件检查与解压之间仍存在同用户本地竞态窗口 | P2 | 架构师Agent/全栈开发工程师Agent | Task 9 现场风险复核 |

## 10. 交接事项

- 交接给：测试工程师Agent、代码审阅者、Task 9 执行者。
- 后续任务：合并工具归档模式补丁；随后上传两个密封归档并继续 Task 9 安装/注册。
- 必须注意：任何损坏密封归档都必须硬停；不得为绕过错误删除/改名缓存后让安装器自行联网。

## 11. 文档同步

- [x] 接口无变化，无需修改接口文档。
- [x] 已同步 ADR-007 离线可信缓存边界。
- [x] 已同步 P4-11 仓库工程状态。
- [x] 已保留最后变更前的独立复测证据，并将当前修订标为待测试工程师Agent 再次独立复测。
- [x] 已更新测试报告索引和实施记录索引。

## 12. Task 9 现场缺陷补充（2026-09-10）

- 现场前置核对：Rootless Docker `active/enabled`、数据根 `/home/crmdeploy/.local/share/docker`、Rootless 容器 0；系统 Docker 数据根 `/var/lib/docker`，公司容器 14 个/运行中 12 个，规范五字段 SHA-256 仍为 `d807427f814e97ffb27ed16a5c6409ab732def8b27841fe209a9b47880226cdb`。
- 本地官方材料：Runner 2.336.0（226035903 字节）与 PowerShell 7.6.5（73393424 字节）均从清单 GitHub 官方 URL 下载，并分别通过 `04cf0be1...05d5d`、`b34ab3b1...6844` 完整 SHA-256。
- 失败关闭：首次三文件 SCP 后实际模式为 `0664`；旧 `$verifyBootstrap` 在任何 chmod、摘要提升、Token 请求或安装动作前退出。目标版本目录、Runner、PowerShell、user unit 和 GitHub Runner 均保持不存在。
- 修复策略：唯一 incoming 目录继续为 `0700`；`normalize_bootstrap_file` 对三个精确路径先执行普通文件、非链接、UID 1004 检查，再分别收紧到 `0700/0600/0600`，随后复用 strict file guard，最后才做 SHA-256、`bash -n` 和 `mv -T`。
- 现场边界：失败后唯一 incoming 目录作为低敏故障证据暂留；未覆盖或删除。修复合并前不继续使用该目录，也不申请注册 Token。
- PR #14 合并后，三项资产已从 main SHA `415b138e...` 重传并成功提升；首次失败目录仍未覆盖或删除。
- 上传两个大归档前的命令复核发现 archive incoming 仍在 chmod 前执行 strict mode 检查。为避免可预见的第二次失败，尚未上传归档；helper 已泛化为 `normalize_transferred_file`，在 bootstrap 与 archive 两个唯一私有目录中复用相同类型/链接/UID/精确模式/strict 顺序。
