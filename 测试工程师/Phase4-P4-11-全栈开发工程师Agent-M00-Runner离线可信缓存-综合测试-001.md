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
| 测试类型 | 综合测试、静态契约、受控 Bash 行为测试、回归测试 |
| 执行日期 | 2026-09-10 |
| 测试结论 | 有条件通过最终仓库工程范围；Task 9 真实现场验收仍阻塞 |

## 2. 测试范围与非范围

测试覆盖 `install-runner.sh` 对确定性密封归档的普通文件、符号链接、UID 1004、SHA-256 和网络 fallback 边界，同时回归原有身份、Token、Runner 重跑和 systemd 契约。

未连接 `192.168.110.210`，未下载真实 GitHub Release 大归档，未传输缓存、申请 Token、注册 Runner、验证 GitHub online/标签、Ubuntu 原生依赖或公司容器不变。本报告不构成 Task 9、G1～G6 或 production 放行。

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
| CACHE-05 | 密封路径为符号链接 | 非零退出，网络调用为 0 | 静态契约通过；Windows 动态案例因符号链接权限跳过，Linux CI/现场待验证 |
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

本轮 4 个跳过项与第 6.2 节相同，不计作通过：2 项为 Rootless 文件/目录符号链接动态案例，另外 2 项为既有生产门禁 Windows 符号链接/目录联接案例。静态失败关闭契约通过，Linux CI/Task 9 Ubuntu 现场动态证据仍未取得。

## 7. 失败项、缺陷与回归

| 项目 | 优先级/状态 | 复现与处理 |
| --- | --- | --- |
| 旧安装器无密封缓存入口 | P1，开发修复已验证 | RED 四个案例均因函数缺失失败；最小实现后 GREEN |
| Windows PATH 命令替身未截获 curl/stat | 测试装置，已关闭 | 本机受限联网使案例显式失败；改为局部 Bash 函数替身，不改生产行为 |
| 动态符号链接/目录联接案例 | 遗留验证风险，未执行 | 最终独立回归有 4 项因 Windows 权限跳过；Linux CI/Task 9 现场须补动态复测，不计为通过 |

最终独立复测未发现新的产品 P0/P1/P2 缺陷。现场未执行项属于发布门禁缺口，不得记为关闭。

## 8. 现场验收待执行

| 门禁 | 当前状态 |
| --- | --- |
| 从清单官方 URL 下载两个真实归档并本地验签 | 未执行 |
| 受保护 SSH/SCP 传输、UID/类型/链接/远端 SHA-256 | 未执行 |
| Ubuntu 原生解压、PowerShell/Runner 版本和 systemd user service | 未执行 |
| GitHub Runner online 与 `self-hosted,linux,x64,crm-staging` 标签 | 未执行 |
| Rootless 容器仍为 0、公司容器五字段不变 | 未执行 |

## 9. 验收建议

最终仓库工程范围有条件通过，建议进入 GitHub Flow CI 和人工审阅，并优先使用 Linux CI 补动态符号链接案例。即使 CI 通过，Task 9 仍须完成两份真实归档的本地/远端 SHA-256、受保护传输、Ubuntu 原生安装、GitHub Runner online/标签以及公司容器不变取证。Task 9 现场完成前，不得宣称 Runner 已安装、基础运行面已完成或 staging/production 已放行。
