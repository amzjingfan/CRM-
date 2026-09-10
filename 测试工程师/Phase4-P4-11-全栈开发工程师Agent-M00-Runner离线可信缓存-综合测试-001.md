# Runner 离线可信缓存综合测试报告

## 1. 测试基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase4 |
| 任务编号 | P4-11；关联 Rootless 部署计划 Task 9 |
| 模块编号 | M00 |
| 模块名称 | Runner 离线可信缓存 |
| 被测主责 Agent | 全栈开发工程师Agent |
| 被测协作 Agent | 架构师Agent、共享记忆文档Agent |
| 测试执行 Agent | 测试工程师Agent |
| 关联实施记录 | `共享记忆文档/实施记录/Phase4-P4-11-全栈开发工程师Agent-Runner离线可信缓存-001.md` |
| 测试类型 | 综合测试、静态契约、受控 Bash 行为测试、回归测试、Ubuntu 现场验收 |
| 执行日期 | 2026-09-10 |
| 测试结论 | Task 9 通过；Runner 基础设施已就绪，后续 staging 应用部署和 production 放行不在本结论内 |

## 2. 测试范围与非范围

测试覆盖 `install-runner.sh` 对确定性密封归档的普通文件、符号链接、UID 1004、SHA-256 和网络 fallback 边界，同时回归原有身份、Token、Runner 重跑和 systemd 契约。

2026-09-10 已在目标 Ubuntu 主机完成两份 GitHub 官方 Release 归档的本地验签、受保护传输、远端再次验签、原生安装、一次性注册、systemd user service 与 GitHub online/标签验收，并在操作前后复核 Rootless 与系统 Docker 隔离状态。注册 Token 未输出、未写文件、未进入环境变量或命令行参数。本报告只关闭 Rootless 部署计划 Task 9，不构成 Task 10～12、G1～G6、staging 应用可用性或 production 放行。

## 3. 测试环境与依据

- 工作树：`.worktrees/runner-offline-cache`，分支 `fix/runner-offline-cache`，基础 `77d9f8f78844f08e5840e505af53ef87e9484c0b`。
- 执行环境：Windows PowerShell + Git for Windows Bash；Python 使用既有 backend venv。
- 架构依据：`架构师/ADR-007-INFRA-Rootless-Staging部署边界-v1.0.md`。
- 历史证据：`测试工程师/Phase4-P4-00-全栈开发工程师Agent-M00-Rootless-Staging运行面-综合测试-007.md`；不移植其历史通过数为本轮证据。

## 4. 最终独立测试场景与结果

| 编号 | 场景 | 期望 | 结果 |
| --- | --- | --- | --- |
| CACHE-01 | UID 1004 拥有的普通文件且 SHA-256 正确 | 选择 `sealed-<filename>`，不调用网络 | 独立复测通过 |
| CACHE-02 | 密封普通文件摘要错误 | 非零退出，网络调用为 0 | 独立复测通过 |
| CACHE-03 | 密封普通文件属主非 UID 1004 | 非零退出，网络调用为 0 | 独立复测通过 |
| CACHE-04 | 密封路径为目录 | 非零退出，网络调用为 0 | 独立复测通过 |
| CACHE-05 | 密封路径为符号链接 | 非零退出，网络调用为 0 | 静态契约通过；Windows 动态案例因符号链接权限跳过，PR #13 Linux CI 已取得动态通过证据，现场目标文件均为非链接普通文件 |
| CACHE-06 | 密封路径不存在 | 只请求清单官方 URL，下载后同样校验摘要 | 独立复测通过 |
| CACHE-07 | 官方下载内容摘要错误 | 非零退出，只记录一次官方 URL，不进入解压 | 独立复测通过 |
| CACHE-08 | cache 或 sealed 文件允许组/其他用户写入 | 非零退出，网络调用为 0 | 独立复测通过 |
| CACHE-09 | 合并后 Runner 三项资产同步与版本化调用 | 逐文件验签并原子提升后才调用同一 HEAD 安装器 | 独立静态复测通过 |
| CACHE-10 | 原有身份、Token 不导出、已注册重跑和 systemd 契约 | 不回归 | 独立回归通过 |
| CACHE-11 | `/home/crmdeploy` 及安装器遍历到的全部既有目录 | UID 1004、真实目录、非链接且组/其他用户不可写 | 独立复测通过；Windows 目录链接动态案例跳过，静态失败关闭契约通过 |
| CACHE-12 | 每个 SSH 边界及 Token 申请前最终复验 | 重验父路径/临时/版本目录；重算三项本地 SHA 并复核远端文件后才申请 Token | 独立静态复测通过；远端复验调用严格先于注册 Token 请求 |
| CACHE-13 | Token-bearing SSH 同一远端进程复验 | 同一命令先执行完整 `$verifyRunnerBootstrap`，成功后才读取 stdin 并调用版本安装器 | 独立静态复测通过；Token 管道直接执行 `$invokeVerifiedRunner`，无嵌套 `bash -c` |

## 5. 开发自测 RED/GREEN 与回归证据

本节命令均由实现主责 Agent 执行，只作为交给测试工程师Agent 的可复现开发证据；当前正式结论以第 6.2 节的最终独立复测为准。

| 阶段 | 命令 | 实际结果 |
| --- | --- | --- |
| RED | `python -m pytest tests/test_rootless_staging_assets.py -q -k 'sealed_archive' --tb=short -p no:cacheprovider --basetemp=C:/Users/Administrator/AppData/Local/Temp/crm-runner-cache-red-20260909` | `4 failed, 1 skipped, 27 deselected in 0.16s`，exit 1；对应函数不存在，不是拼写/环境错误 |
| 中间装置修正 | 实现后的受控 Bash 测试 | 两轮分别为 `1 failed, 3 passed, 1 skipped`和 `2 failed, 29 passed, 1 skipped`；Windows Git Bash 未命中 PATH 命令替身，改为 Bash 函数替身后关闭 |
| GREEN | `python -m pytest tests/test_rootless_staging_assets.py -q --tb=short -p no:cacheprovider --basetemp=C:/Users/Administrator/AppData/Local/Temp/crm-runner-cache-green5-20260909` | `31 passed, 1 skipped in 0.55s`，exit 0 |
| 审阅修复 RED | 聚焦版本化资产、精确 chmod、权限与官方下载坏摘要案例 | `6 failed, 1 passed, 32 deselected in 0.72s`，exit 1；失败对应三项实现缺口，坏摘要案例已由旧实现满足 |
| 审阅修复 GREEN | 同一聚焦集合 | `7 passed, 32 deselected in 0.41s`，exit 0 |
| 审阅补充 RED/GREEN | 版本目录父路径 UID 1004 精确契约 | 先 `1 failed`，补最小文档实现后 `1 passed` |
| 第二次复审 RED | 聚焦既有父目录、各 SSH 边界及 Token 前最终复验 | `8 failed, 1 skipped, 39 deselected in 0.21s`，exit 1；失败点为本轮 Important 缺失 |
| 第二次复审 GREEN | 同一聚焦集合 | `8 passed, 1 skipped, 39 deselected in 0.35s`，exit 0；为开发自测证据，待独立复测 |
| SSH 错误传播补充 RED/GREEN | 各远端门禁必须启用 `set -euo pipefail` | 先 `1 failed`，补充后 `1 passed in 0.02s`；确保 guard 失败不会继续执行，为开发自测证据 |
| 最终复审 RED/GREEN | Token-bearing SSH 必须使用由完整复验组成的 `$invokeVerifiedRunner` | `1 failed in 0.10s` → `1 passed in 0.02s`；不再调用旧嵌套 `bash -c`，为开发自测证据 |
| 最终复审双文件回归 | `python -m pytest tests/test_rootless_staging_assets.py tests/test_production_gate_scripts.py -q --tb=short -p no:cacheprovider --basetemp=C:/Users/Administrator/AppData/Local/Temp/crm-runner-token-same-process-final2-20260910` | 初次回归 `1 failed, 106 passed, 4 skipped` 暴露旧静态断言；最小更新并单测通过后，当前树重跑为 `107 passed, 4 skipped in 32.40s`、exit 0；均为开发自测证据 |
| 第二次复审 Rootless 单文件回归 | `python -m pytest tests/test_rootless_staging_assets.py -q --tb=short -p no:cacheprovider --basetemp=C:/Users/Administrator/AppData/Local/Temp/crm-runner-second-review-rootless-20260910` | `46 passed, 2 skipped in 1.30s`，exit 0；为开发自测证据 |
| 第二次复审 Rootless 相关回归 | `python -m pytest tests/test_rootless_staging_assets.py tests/test_production_gate_scripts.py -q --tb=short -p no:cacheprovider --basetemp=C:/Users/Administrator/AppData/Local/Temp/crm-runner-second-review-final-20260910` | `106 passed, 4 skipped in 27.79s`，exit 0；为开发自测证据 |
| 审阅后 Rootless 单文件回归 | `python -m pytest tests/test_rootless_staging_assets.py -q --tb=short -p no:cacheprovider --basetemp=C:/Users/Administrator/AppData/Local/Temp/crm-runner-review-rootless-20260909` | `38 passed, 1 skipped in 0.95s`，exit 0 |
| 最终 Rootless 相关回归 | `python -m pytest tests/test_rootless_staging_assets.py tests/test_production_gate_scripts.py -q --tb=short -p no:cacheprovider --basetemp=C:/Users/Administrator/AppData/Local/Temp/crm-runner-review-final-regression-20260909` | `98 passed, 3 skipped in 25.29s`，exit 0 |
| 静态质量 | `python -m ruff check tests/test_rootless_staging_assets.py`；`python -m ruff format --check tests/test_rootless_staging_assets.py`；`bash -n install-runner.sh`；`git diff --check` | Ruff `All checks passed` / `1 file already formatted`；Bash 与 diff exit 0 |
| 运行手册可解析性 | PowerShell AST 解析 README 全部 `powershell` 代码块 | 8 个代码块、0 个解析错误 |
| 低敏与索引一致性 | 修改文件高置信凭据模式扫描；新索引路径计数与存在性 | 凭据特征 0 命中；两个新路径各 1 次且文件存在 |

本轮开发双文件回归的 `4 skipped` 中，2 项是 Rootless 文件/目录符号链接动态案例，其余 2 项是既有生产门禁 Windows symlink/目录联接案例；均不计为通过。代码的 `-L` 失败关闭分支由静态契约保护，合并前应尽可能由 Linux CI 动态复测，Task 9 现场必须保留该失败验证。

## 6. 测试工程师独立复测证据

### 6.1 Important 修复前版本历史证据

下列命令均由测试工程师Agent 于 2026-09-10 在 `.worktrees/runner-offline-cache` 独立执行；Python 使用主工作区既有 backend venv，pytest 的 `basetemp` 位于仓库外。未访问网络、GitHub 或服务器，未下载归档，也未申请或传递 Runner Token。该证据只证明上一修订仓库工程范围有条件通过，不覆盖随后新增的父目录与 Token 前复验修复。

| 验证项 | 独立命令/方法 | 准确结果 |
| --- | --- | --- |
| Rootless 与生产门禁双文件回归 | `E:\develop\CRM智能聊天系统\CRM智能聊天系统\backend\.venv\Scripts\python.exe -m pytest tests/test_rootless_staging_assets.py tests/test_production_gate_scripts.py -q --tb=short -p no:cacheprovider --basetemp=C:/Users/Administrator/AppData/Local/Temp/crm-runner-cache-independent-qa-20260909` | `98 passed, 3 skipped in 26.08s`，exit 0 |
| 测试文件 Ruff | `python -m ruff check tests/test_rootless_staging_assets.py`；`python -m ruff format --check tests/test_rootless_staging_assets.py` | `All checks passed!`；`1 file already formatted`，均 exit 0 |
| 安装器 Bash 语法 | `D:\Program Files\Git\bin\bash.exe -n ../deploy/staging/rootless/install-runner.sh`（从 backend 执行） | 无输出，exit 0 |
| README PowerShell AST | 正则提取 `README.md` 全部 `powershell` fenced blocks，逐块调用 `System.Management.Automation.Language.Parser.ParseInput` | 8 个块，0 个解析错误 |
| 版本资产调用顺序 | 独立比较 `mv -T` 原子提升、带 40 位 HEAD 的版本化安装器和 `$runnerToken \| ssh` 首次调用位置 | 原子提升先于版本化路径解析，版本化路径先于注册调用；注册段不再引用旧固定安装器 |
| 精确权限收敛 | 检查三项版本资产和两个密封归档的精确 `chmod`，并拒绝 `sealed-*.tar.gz` 通配符 | 5 个精确标记均存在，通配 chmod 不存在 |
| 索引与低敏检查 | 检查正式测试报告/实施记录路径各出现一次且目标存在；扫描 9 个本轮文件中的私钥头、GitHub Token、常见 Provider 密钥和 URL 内嵌凭据；执行 `git diff --check` | 两个索引路径计数均为 1；高置信凭据命中 0；diff 检查通过 |

三个跳过项不计作通过。依据测试代码中的平台门禁，它们是 Windows 当前权限下的文件符号链接或目录联接动态案例；`install-runner.sh` 的 `-L` 失败关闭分支和 README 静态契约已独立覆盖，但仍须由 Linux CI 或 Task 9 Ubuntu 现场补动态证据。

### 6.2 Token-bearing SSH 最后变更前的独立复测

本轮仍未访问网络、GitHub 或服务器，未下载真实归档、申请 Token 或执行 SSH。首次测试调用在 30 秒边界返回后台 session，但调用方未保留 session ID，只取得不完整进度，故不作为通过证据；确认该组进程不再推进后，精确结束该次测试创建的残留进程并验证数量为 0。随后按控制器允许的证据重取方式使用新的仓库外 `basetemp` 和 `-qq` 重新执行一次，保留 session ID，仅轮询同一 session 至退出；没有第三次 pytest，也没有与旧进程并行。该证据完成于 Token-bearing SSH 同进程复验修复之前，不能替代当前修订的再次独立复测。

| 验证项 | 独立命令/方法 | 准确结果 |
| --- | --- | --- |
| 最终双文件回归 | `E:\develop\CRM智能聊天系统\CRM智能聊天系统\backend\.venv\Scripts\python.exe -m pytest tests/test_rootless_staging_assets.py tests/test_production_gate_scripts.py -qq --tb=short -p no:cacheprovider --basetemp=C:/Users/Administrator/AppData/Local/Temp/crm-runner-cache-independent-qa2-evidence-20260910` | session `85844` 完成至 `[100%]`，exit 0；进度标记精确计数为 `106 passed、4 skipped`，共 110 项 |
| 残留进程 | 最终 session 退出后查询 `Get-Process -Name python` | 无输出，测试 Python 残留进程 0 |
| 测试文件 Ruff | `python -m ruff check tests/test_rootless_staging_assets.py`；`python -m ruff format --check tests/test_rootless_staging_assets.py` | `All checks passed!`；`1 file already formatted`，均 exit 0 |
| 安装器 Bash 语法 | `D:\Program Files\Git\bin\bash.exe -n ../deploy/staging/rootless/install-runner.sh`（从 backend 执行） | 无输出，exit 0 |
| README PowerShell AST | 提取 `README.md` 全部 `powershell` fenced blocks，逐块调用 PowerShell Parser | 8 个块，0 个解析错误 |
| 远端路径门禁 | 独立核对目录/文件函数、UID 1004、链接、组/其他写权限及 prepare/verify/promote 各命令 | 13 个关键远端 guard 标记全部存在；安装器 6 个父目录门禁标记存在且 home 检查先于 cache 遍历 |
| Token 前最终复验顺序 | 在注册块依次定位 clean worktree、40 位 HEAD、三项本地重算、远端复验定义/调用、registration-token 请求及安装器调用 | 8 个顺序标记严格递增；远端三文件 SHA-256 与 Bash 语法复验在 Token 请求之前 |
| 精确权限收敛 | 核对三项版本资产及两个密封归档的精确 chmod | 5 个精确 chmod 均存在，`sealed-*.tar.gz` 通配 chmod 不存在 |
| 索引、凭据与差异卫生 | 检查测试/实施记录索引路径与目标；扫描 9 个本轮文件中的高置信凭据模式；执行 `git diff --check` | 两个路径各出现 1 次且目标存在；凭据命中 0；diff 检查通过 |

四个跳过项不计作通过：其中 2 项为 Rootless 文件/目录符号链接动态案例，另外 2 项为既有生产门禁 Windows 符号链接/目录联接案例。Windows 当前权限无法提供动态证据；静态 `-L`/真实目录失败关闭契约已通过，仍须 Linux CI 或 Task 9 Ubuntu 现场补证。

### 6.3 Token-bearing SSH 同进程复验后的最终独立复测

本轮只针对 `$invokeVerifiedRunner` 最后变更后的当前树执行，未访问网络、GitHub 或服务器，未下载真实归档、申请 Token 或执行 SSH。执行前确认无 Python 测试进程；pytest 使用新的仓库外 `basetemp`，首次调用返回 session `74210` 后只轮询同一 session 至退出，未重复或并行运行。

| 验证项 | 独立命令/方法 | 准确结果 |
| --- | --- | --- |
| 最终双文件回归 | `E:\develop\CRM智能聊天系统\CRM智能聊天系统\backend\.venv\Scripts\python.exe -m pytest tests/test_rootless_staging_assets.py tests/test_production_gate_scripts.py -qq --tb=short -p no:cacheprovider --basetemp=C:/Users/Administrator/AppData/Local/Temp/crm-runner-cache-independent-qa3-evidence-20260910` | session `74210` 完成至 `[100%]`，exit 0；进度标记精确计数为 `107 passed、4 skipped`，共 111 项 |
| 测试进程隔离 | 执行前后查询 `Get-Process -Name python` | 均无输出，未与其他 pytest 并行，最终残留进程 0 |
| 测试文件 Ruff | `python -m ruff check tests/test_rootless_staging_assets.py`；`python -m ruff format --check tests/test_rootless_staging_assets.py` | `All checks passed!`；`1 file already formatted`，均 exit 0 |
| 安装器 Bash 语法 | `D:\Program Files\Git\bin\bash.exe -n ../deploy/staging/rootless/install-runner.sh`（从 backend 执行） | 无输出，exit 0 |
| README PowerShell AST | 提取 `README.md` 全部 `powershell` fenced blocks并逐块调用 PowerShell Parser | 8 个块，0 个解析错误 |
| 同进程复验定义 | 定位 `$invokeVerifiedRunner` 定义及 Token-bearing SSH 行 | 定义和 Token SSH 各 1 处；定义包含 `$verifyRunnerBootstrap;`、CRLF 规范化和版本化安装器；Token SSH 直接执行 `$invokeVerifiedRunner`，嵌套 `bash -o pipefail -c` 为 0 |
| Token 前顺序 | 定位 `set -euo pipefail`、`$verifyRunnerBootstrap`、`$invokeVerifiedRunner`、独立远端预检、registration-token 和 Token SSH | 6 个顺序标记严格递增；完整复验定义与预检均在 Token 请求前，同一 Token 进程再次执行完整复验 |
| 索引、凭据与差异卫生 | 检查正式测试/实施记录路径与目标；扫描 9 个本轮文件中的高置信凭据模式；执行 `git diff --check` | 两个索引路径各出现 1 次且目标存在；凭据命中 0；diff 检查通过 |

本轮 4 个跳过项与第 6.2 节相同，不计作 Windows 通过：2 项为 Rootless 文件/目录符号链接动态案例，另外 2 项为既有生产门禁 Windows 符号链接/目录联接案例。静态失败关闭契约通过，后续由 PR #13 的 Linux CI 补齐动态证据。

### 6.4 PR #13 Linux CI 证据

GitHub Actions run `34429552119` 在 Ubuntu / Python 3.11.16 上完成 PR #13 的后端与前端两个质量门禁。后端收集 1564 项，最终 `1552 passed, 12 skipped, 3 warnings in 70.72s`；日志中的 `tests/test_rootless_staging_assets.py` 全部为通过标记，没有该文件的 skip，因而本地受 Windows 权限限制的文件/目录符号链接案例已取得 Linux 动态通过证据。12 个 skip 均位于既有 PostgreSQL 集成测试文件，不属于本增量。前端质量门禁同时通过。PR #13 随后更新后的最终 head `d6daa095bd4bec7f2e01bec28cf14d781aaa21bf` 对应 run `34432014630`，后端与前端同样为 success；前一个 run 保留为明确的 Linux 动态案例证据，后一个 run 是合并前最终 head 证据。

CI 运行页：`https://github.com/CP11-gh/CRM/actions/runs/34429552119`、`https://github.com/CP11-gh/CRM/actions/runs/34432014630`。该证据验证的是 PR 工程树，不替代目标 Ubuntu 主机、真实归档或 Runner 注册现场。

### 6.5 Task 9 首次现场与 Windows SCP 模式修复

PR #13 squash merge 后以 clean `main` 完整 SHA `d5d45ef1d0a513b54d3cf4cffbf34dad72fd0393` 启动 Task 9。服务器只读预检确认 Ubuntu 26.04 x86_64、`crmdeploy` UID/GID 1004、Rootless Docker active/enabled、Rootless 容器 0；系统 Docker 数据根仍为 `/var/lib/docker`，公司容器 14 个/运行中 12 个，规范五字段 SHA-256 与历史证据同为 `d807427f814e97ffb27ed16a5c6409ab732def8b27841fe209a9b47880226cdb`。

三项版本资产经 SCP 进入唯一 `0700` incoming 目录后，目标 Ubuntu 上的文件模式实际为 `0664`。旧流程在逐文件 chmod 之前调用 strict file guard，因此按失败关闭原则退出；三个文件的本地/远端 SHA-256 一致且 `bash -n` 通过，但没有原子提升版本目标，没有申请 Token，也没有安装 Runner、PowerShell 或 user unit。该现场结果证明旧手册无法直接兼容 Windows OpenSSH/SCP 的权限映射，不能通过人工绕过门禁继续。

修复以 TDD 实施：新增测试先得到 `1 failed`，随后引入文件规范化 helper，在唯一私有目录内按普通文件、非链接、UID 1004、精确 chmod、strict file check 的顺序处理三个固定路径，再执行摘要、Bash 语法和原子提升。开发单文件回归 `48 passed, 2 skipped`，与生产门禁联合回归 `108 passed, 4 skipped in 34.95s`。独立 QA 复跑联合回归得到 `108 passed, 4 skipped`、exit 0；Ruff、Bash、8 个 PowerShell 代码块 AST、差异与高置信凭据检查均通过。独立安全审阅 Critical/Important/Minor 均为 0，结论 READY。PR #14 的后端/前端 CI 均通过，随后 squash merge 为 `415b138e7674c2c700808edad84c7f3698d9b64a`；从该 main SHA 重传的三项版本资产在 incoming/版本目录共六次摘要检查全部 OK，并成功原子提升。

在上传两个大归档之前，静态复核发现 archive incoming 使用相同 Windows SCP 通道，却仍在 chmod 前执行 strict mode 检查。归档尚未上传，因此未产生第二次现场失败或不完整远端大文件。新增归档顺序用例先得到 `1 failed`；helper 泛化为 `normalize_transferred_file` 并同时用于 bootstrap/archive 后，单文件 `49 passed, 2 skipped`，联合回归 `109 passed, 4 skipped in 34.68s`。最终独立 QA 使用唯一 session 得到 `109 passed, 4 skipped`、exit 0，Ruff/格式、Bash、8 个 PowerShell AST、差异和高置信凭据均通过；安全审阅 Critical/Important/Minor 为 0，结论 READY。4 个 skip 仍是 Windows 权限限制的既有动态链接案例。

PR #15 的 GitHub Actions run `34439346391` 后端和前端质量门禁均通过，随后 squash merge 为 `bf5640acc0c9f2918de9831f30097951a985bd3b`。最终 main 的安装器、清单和 user unit 分别以 `a3c617dd3295abdc99013668f0373b378a7ad253d9ee862e1f9236ac38da1bc3`、`decdd9666720e1d24daca210ff874ac7372cf4e08e7a4bafc4783936d1277742`、`4a2ed0d68218ea49460efb2c356a5bd6bed6f1137c20b85c015c4215ede4199a` 在本地、incoming 和最终版本目录复验；最终目录为 `/home/crmdeploy/src/rootless-staging-bootstrap-bf5640acc0c9f2918de9831f30097951a985bd3b`。

两份归档从清单中的 GitHub 官方 URL 获取；初始 `curl` 传输过慢并重置后改用 Windows BITS/WinHTTP 访问相同 URL，不使用镜像。Runner `2.336.0` 文件为 226035903 字节、SHA-256 `04cf0be1aff4c3ec3554466c39124ca250e3effd8873bb7e8d68535aa9505d5d`；PowerShell `7.6.5` 文件为 73393424 字节、SHA-256 `b34ab3b19acac1d3d4d0d3cfdb02acf62f457b0b6a962ff008132033f7566844`。两文件经唯一私有 incoming 目录规范化为 UID 1004、mode `0600` 后验签并以 `mv -T` 提升至 `/home/crmdeploy/.cache/crm-toolchain/sealed-<filename>`，提升后再次通过类型、链接、属主、权限和摘要门禁。

最终安装输出确认 PowerShell `7.6.5`、Runner.Listener `2.336.0`；`crm-staging-runner.service` 为 active/enabled、SubState `running`、ExecMainStatus `0`。`.runner`、`.credentials`、`.credentials_rsaparams` 和用户 unit 均为 UID 1004 拥有、mode `0600` 的非链接普通文件。GitHub 仓库仅有一个 runner：`crm-staging-192-168-110-210`，状态 online、busy=false，标签为 `self-hosted`、`Linux`、`X64`、`crm-staging`。

测试工程师Agent 随后以独立 SSH 会话只读复核，结论 READY，Critical/Important/Minor 均为 0。复核重新从 final main 安装器解析准确安装路径，逐项确认上述版本、四个敏感元数据文件、三项版本资产、两份密封归档、Rootless Docker、系统 Docker 五字段摘要及 GitHub runner 状态；两次读取历史 partial 与首次失败 incoming 的 type/UID/GID/mode/size/mtime/ctime/inode 完全一致，证明未覆盖或删除。首次使用错误假设的 PowerShell 路径时命令按 `set -e` 中止，空输出未被采信；纠正路径后的完整结果才作为本段证据。独立复核没有读取凭据内容、申请 Token 或修改本地、服务器及 GitHub 状态。

## 7. 失败项、缺陷与回归

| 项目 | 优先级/状态 | 复现与处理 |
| --- | --- | --- |
| 旧安装器无密封缓存入口 | P1，开发修复已验证 | RED 四个案例均因函数缺失失败；最小实现后 GREEN |
| Windows PATH 命令替身未截获 curl/stat | 测试装置，已关闭 | 本机受限联网使案例显式失败；改为局部 Bash 函数替身，不改生产行为 |
| 动态符号链接/目录联接案例 | 已关闭（Linux 工程环境） | Windows 最终独立回归的 4 项 skip 不计通过；PR #13 Linux CI 已执行相关测试且 `test_rootless_staging_assets.py` 无 skip |
| Windows SCP 产生 `0664`，旧流程在精确 chmod 前失败 | P1 运维缺陷，已关闭 | 现场严格失败关闭且未提升/未取 Token；PR #14 先拒绝链接/错属主，再逐个精确 chmod 和 strict check，CI/合并及真实重传通过 |
| 工具归档 SCP 路径仍在 chmod 前 strict check | P1 运维缺陷，上传前发现并关闭 | PR #15 泛化 helper 后同样先拒绝链接/错属主，再精确 `0600`、strict check、SHA 和原子提升；CI/合并及真实传输通过 |

最终仓库工程独立复测未发现新的产品 P0/P1/P2 缺陷；两项 SCP 模式缺陷均通过 GitHub Flow 与现场复验关闭。Task 10～12、G1～G6 和 production 仍是独立门禁，不得由 Task 9 结论代替。

## 8. 现场验收结果

| 门禁 | 当前状态 |
| --- | --- |
| 从清单官方 URL 下载两个真实归档并本地验签 | 已通过；Runner 226035903 字节、PowerShell 73393424 字节，两个完整 SHA-256 均与清单一致 |
| 受保护 SSH/SCP 传输、UID/类型/链接/远端 SHA-256 | 已通过；final main 三项资产及两个密封归档均在目标机通过完整门禁，归档 mode `0600`、UID 1004、非链接 |
| Ubuntu 原生解压、PowerShell/Runner 版本和 systemd user service | 已通过；PowerShell `7.6.5`、Runner.Listener `2.336.0`，服务 active/enabled/running、ExecMainStatus `0` |
| GitHub Runner online 与 `self-hosted,linux,x64,crm-staging` 标签 | 已通过；runner `crm-staging-192-168-110-210` online、busy=false，实际内建标签大小写为 `Linux`/`X64` |
| Rootless 容器仍为 0、公司容器五字段不变 | 已通过；Rootless 容器 0；系统 Docker 保持 `/var/lib/docker`、14 个/运行中 12 个，规范五字段 SHA-256 保持 `d807427f814e97ffb27ed16a5c6409ab732def8b27841fe209a9b47880226cdb` |

## 9. 验收建议

Task 9 通过：版本资产与工具归档的 SCP 模式修复分别经 PR #14/#15 CI、独立 QA/安全审阅和 squash merge，最终 main 资产与官方归档均完成双端验签；目标 Ubuntu 已安装指定版本并注册唯一在线 Runner，Rootless 与公司系统 Docker 操作前后隔离不变。可以进入 Task 10 外部材料和 Task 11 staging 应用部署；这不等于 staging 业务功能、G1～G6 或 production 放行。
