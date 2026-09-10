# Runner 离线可信缓存实施计划

> **执行方式：** 使用 `superpowers:test-driven-development` 先写失败测试，再做最小实现；完成后按 `superpowers:requesting-code-review` 和 `superpowers:verification-before-completion` 独立复核。

**目标：** 在不改变 Rootless Docker、公司系统 Docker 和 Runner 注册凭据边界的前提下，让 staging Runner 安装器优先使用经 SHA-256 复核的本地密封归档；密封归档不存在时保留官方 GitHub HTTPS 下载。

**范围：** `install-runner.sh`、Rootless 静态/受控 Bash 测试、唯一运行手册、ADR-007 补充说明、实施记录、正式测试报告及两个索引。API、数据库、产品功能、production 运行方案均不变。

**可信缓存契约：** 每个工具的密封归档固定为 `/home/crmdeploy/.cache/crm-toolchain/sealed-<manifest filename>`。若路径存在，必须是 UID 1004 拥有、非符号链接的普通文件，并通过清单 SHA-256；任一检查失败立即终止，禁止退回网络。路径不存在时才从清单中的官方 GitHub HTTPS URL 下载到私有随机临时文件并验签。无论来源，只有验签成功的归档才能解压和原子提升为工具目录。

## Task 1：以测试冻结可信缓存边界

**文件：**

- 修改：`CRM智能聊天系统/backend/tests/test_rootless_staging_assets.py`

1. 增加静态契约，要求确定性 `sealed-` 文件名、非链接/普通文件/UID 1004 检查、摘要错误失败关闭，以及仅在密封归档不存在时执行官方下载。
2. 增加受控 Bash 行为测试，用最小命令替身证明：合法缓存零网络并成功；摘要错误、符号链接、错误属主/类型均非零退出且零网络；缓存缺失才调用官方 URL。
3. 先运行聚焦测试并记录 RED，确认失败原因是实现尚不存在。

## Task 2：最小实现离线可信缓存

**文件：**

- 修改：`CRM智能聊天系统/deploy/staging/rootless/install-runner.sh`

1. 从已验证清单元数据中同时输出官方文件名，避免第二套文件名推导。
2. 对确定性密封归档执行类型、链接、UID 和 SHA-256 检查；存在但非法时失败关闭。
3. 仅在密封归档不存在时沿用现有 `curl` 官方下载流程。
4. 统一让下载归档与密封归档进入同一“先验签、再解压、再原子移动”的流程，不改变 Token、Runner 身份和 systemd 逻辑。
5. 运行聚焦测试至 GREEN，并执行 Bash 语法与 Ruff 检查。

## Task 3：同步架构、运维和可审计记录

**文件：**

- 修改：`CRM智能聊天系统/deploy/staging/rootless/README.md`
- 修改：`架构师/ADR-007-INFRA-Rootless-Staging部署边界-v1.0.md`
- 新增：`共享记忆文档/实施记录/Phase4-P4-11-全栈开发工程师Agent-Runner离线可信缓存-001.md`
- 修改：`共享记忆文档/实施记录索引.md`
- 新增：`测试工程师/Phase4-P4-11-全栈开发工程师Agent-M00-Runner离线可信缓存-综合测试-001.md`
- 修改：`共享记忆文档/测试报告索引.md`

1. 在 runbook 写明本机仅从清单官方 URL 下载、按清单 SHA-256 校验、经受保护 SSH/SCP 传输、远端再次校验后再运行安装器；不记录 Token 或私钥。
2. ADR 增补离线可信缓存的供应链边界：不是镜像站，不削弱清单验签，也不授权缓存损坏时联网绕过。
3. 记录 RED/GREEN、回归、未执行的真实服务器项和遗留风险；代码自测报告不能冒充 Task 9 真实运行通过。

## Task 4：全量验证、审阅与 GitHub Flow

1. 运行 Rootless 资产测试和相关生产门禁脚本测试，使用仓库外 `basetemp`。
2. 运行 Ruff、Bash `-n`、`git diff --check`、凭据模式和大文件扫描。
3. 独立代码审阅；修复所有 Critical/Important 问题并复测。
4. 小步提交，推送 `fix/runner-offline-cache`，创建 PR；等待 CI 和人工审阅后 squash merge，删除短期分支。

## Task 5：合并后执行 Task 9 现场验收

1. 从合并后的 `main` 读取清单，在本机从两个官方 GitHub Release URL 下载并校验 SHA-256；文件保存在 Git 忽略目录。
2. 通过受保护的 SSH 私钥将两个密封归档传到 `/home/crmdeploy/.cache/crm-toolchain/`，以 `crmdeploy` 身份核对路径、UID、类型、权限和 SHA-256。
3. 传输合并后的安装资产，申请一次新的一小时注册 Token，仅通过 stdin 调用安装器。
4. 验证 PowerShell/Runner 版本、用户服务 active/enabled、GitHub Runner online 和四个标签；验证 Rootless 容器仍为 0、公司容器五字段完全不变。
5. 由独立复核者核对低敏证据。只有全部通过才把 Task 9 结论改为通过；否则保留真实失败状态并停止进入 Task 10。
