# Rootless Staging 运行面综合测试记录

## 1. 测试基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase4 |
| 任务编号 | P4-00；关联 P4-11、REAL-FS-01/G0；Rootless 实施计划 Tasks 1～9 |
| 模块编号 | M00 |
| 模块名称 | Rootless Staging 运行面 |
| 被测主责 Agent | 全栈开发工程师Agent |
| 被测协作 Agent | 架构师Agent、共享记忆文档Agent |
| 测试执行 Agent | 测试工程师Agent（Task 9 已独立现场只读复核） |
| 关联实施记录 | `共享记忆文档/实施记录/PhaseX-PX-00-全栈开发工程师Agent-Rootless-Staging部署-001.md` |
| 测试类型 | 综合测试、静态契约、无网络脚本回归、文档一致性、Ubuntu 基础设施现场验收 |
| 执行日期 | 2026-09-09～2026-09-10 |
| 测试结论 | Tasks 8/9 基础设施运行面已就绪；Task 10/11、G1～G6 和 production 仍阻塞 |

独立测试结论：Task 9 READY；Critical/Important/Minor 均为 0

本文是该运行面的单一工程/现场证据记录。Task 12 在本文件继续追加带日期、SHA 与 run ID 的现场证据，保留各工程阶段记录，不覆盖历史测试结果，不另建第二份竞争结论。当前已有服务器、Rootless Docker 与 runner 的真实证据；尚无 DNS/TLS、六文件模型、应用部署、公开健康、恢复/回滚或 G1～G6 成功声明，`production_release=false`。

## 2. 范围、环境与证据来源

范围为精确 staging OAuth 回调、Rootless Compose、Docker 客户端隔离、主机与入口资产、runner 供应链及文档。业务范围仍按 ADR-006 的 TikTok 人工辅助首版；不验证 Shopee/Amazon 真实接入，也不打开真实能力。

本地工作树：`.worktrees/rootless-staging`，分支 `feature/rootless-staging`。Tasks 1～5 最终源代码提交为 `205a6caf55006e5100d6c19096a236ea63dbc896`，基础 main 为 `433b3e5`。Windows PowerShell、已有 backend Python venv、Docker Compose standalone 5.3.1 以及局部 Git for Windows Bash；未使用目标 Ubuntu/systemd/runtime。受控 fake Docker 回归不会部署容器。

开发自测来源为调度交接的 `task-1-report.md` 至 `task-5-report.md`（本地 SDD scratch），提交通过 `git log` 交叉核对：

| 任务 | 实现及修复提交 | 内容 |
| --- | --- | --- |
| 1 | `a6ef811` | 按环境精确匹配回调 |
| 2 | `9853ff4` | staging 四服务失败关闭、回环端口 |
| 3 | `a23d070`、`2a9e749` | 固定 UID socket/项目/overlay，清除并恢复 DOCKER_CONTEXT |
| 4 | `2c38c92`、`8436cbd` | bootstrap/入口资产，socket running 幂等和 unit LF 属性修复 |
| 5 | `42e06a6`、`205a6ca` | runner 工具链/工作流，Bash allexport 凭据隔离修复 |

## 3. 已运行命令与准确结果

除特别标注，以下为 Tasks 1～5 执行者留存的原命令和结果，Task 6 不冒充重新执行这些测试。运行目录为 `CRM智能聊天系统/backend`；`python`/`python.exe` 指向 `E:\develop\CRM智能聊天系统\CRM智能聊天系统\backend\.venv\Scripts\python.exe`。短写只省略该可执行文件路径，不改变测试选项。

| 任务/场景 | 已执行命令 | 留存结果 |
| --- | --- | --- |
| 1 回调/OAuth | `python -m pytest tests/test_real_runtime_config.py tests/test_tiktok_oauth.py -q` | 106 passed |
| 1 静态质量 | `python -m ruff check app/shared/config/settings.py tests/test_real_runtime_config.py` | All checks passed |
| 2 overlay 聚焦 | `python -m pytest tests/test_real_runtime_config.py::test_rootless_staging_overlay_is_loopback_only_and_fail_closed -q` | 缺少文件时 FileNotFoundError；实现后 1 passed |
| 2 配置回归 | `python -m pytest tests/test_real_runtime_config.py -q` | 80 passed |
| 3 首次完整 | `python -m pytest tests/test_production_gate_scripts.py -q --basetemp 'E:\develop\CRM智能聊天系统\.worktrees\.pytest-task3'` | 46 passed, 2 skipped in 18.82s |
| 3 context 修复 | `python -m pytest tests/test_production_gate_scripts.py::test_gate_scripts_clear_and_restore_inherited_docker_context -q --basetemp 'E:\develop\CRM智能聊天系统\.worktrees\.pytest-task3'` | 6 passed in 3.78s |
| 3 修复后完整 | `python -m pytest tests/test_production_gate_scripts.py -q --basetemp 'E:\develop\CRM智能聊天系统\.worktrees\.pytest-task3'` | 52 passed, 2 skipped in 24.02s |
| 4 资产缺失 RED | `python.exe -m pytest tests/test_rootless_staging_assets.py -q` | 8 failed（文件缺失） |
| 4 首次 GREEN | 同上 | 8 passed |
| 4 端口归属 RED/GREEN | 上述命令加 `--tb=short`；修复后原命令 | 1 failed, 8 passed → 9 passed |
| 4 证据权限 RED/GREEN | 上述命令加 `--tb=short`；修复后原命令 | 2 failed, 9 passed → 11 passed in 0.03s |
| 4 running/LF 修复 RED/GREEN | `python.exe -m pytest tests/test_rootless_staging_assets.py -q` | 8 failed, 11 passed → 19 passed in 0.03s |
| 4 静态质量 | `python.exe -m ruff check tests/test_rootless_staging_assets.py`；`python.exe -m ruff format --check tests/test_rootless_staging_assets.py` | All checks passed；1 file already formatted |
| 5 runner/workflow RED | `python -m pytest tests/test_rootless_staging_assets.py tests/test_production_gate_scripts.py -q -k 'runner or workflow' --basetemp=../../.pytest-task5-red --tb=short` | 11 failed, 73 deselected |
| 5 初始 Token export RED | `test_runner_token_cannot_inherit_export_attribute` 聚焦案例（交接仅保留案例名） | 1 failed, 23 deselected |
| 5 两套 GREEN | `python -m pytest tests/test_rootless_staging_assets.py tests/test_production_gate_scripts.py -q --basetemp=<fresh-external-temp> --tb=short` | 84 passed, 2 skipped in 25.33s |
| 5 首次四套回归 | `python -m pytest tests/test_real_runtime_config.py tests/test_tiktok_oauth.py tests/test_rootless_staging_assets.py tests/test_production_gate_scripts.py -q --basetemp=<fresh-external-temp> --tb=short` | 191 passed, 2 skipped in 29.13s |
| 5 allexport RED/GREEN | `pytest tests/test_rootless_staging_assets.py -q -k allexport --tb=short` | 2 failed, 24 deselected → 2 passed, 24 deselected |
| 5 修复后四套回归 | 同上述四套回归，新的外部临时目录 | 193 passed, 2 skipped in 25.85s |
| 5 局部 Bash 语法 | `D:/Program Files/Git/bin/bash.exe --noprofile --norc -n install-runner.sh`（目标为 deploy/staging/rootless 下脚本） | exit 0；仅本地 Bash 语法 |
| 5 静态质量 | 修改测试文件的 Ruff check/format check；`git diff --check`；`git diff --cached --check` | check 通过；初版 2 files already formatted，修复轮 1 file already formatted；diff 无空白错误 |

`<fresh-external-temp>` 是原交接报告的占位记法，执行时实际是 Windows TEMP 下新建绝对目录；原临时目录名未归档，不补造路径。2 skips 为既有平台相关 symlink 案例，不能计为通过。Task 5 中途将临时目录放在 checkout 内得到 29 failed, 53 passed, 2 skipped，原因是外部模型目录门禁正确拒绝；换用仓库外临时目录后得到上表 GREEN。另有既有 Windows pytest-current ACL 清理噪声，隔离临时目录规避；这不是 Ubuntu 验证。

Task 2 使用 standalone `docker-compose.exe v5.3.1` 的 `--profile ai ... config --format json` 检查四服务合并值和回环端口，并以 `config --services` 得到 10 个服务；未启动容器。原报告省略了完整参数和脱敏临时环境值，因此仅作为开发观察，不冒充完整可重放命令记录。Task 7 可补留完整低敏 Compose 命令；不得输出真实展开配置。当前本机 `docker.exe compose` 不可用，不代表服务器插件可用。

## 4. 通过场景与限制

- Settings 接受 staging 专用回调，integration/production 保留 www；互换、非法 scheme/host/path/query/fragment 失败关闭。
- 四服务合并环境为 staging，十项受控能力 false，proxy 仅回环两个端口；无目标主机容器健康证据。
- 两个 PowerShell 脚本的 ValidateOnly/WhatIf/失败路径经 fake Docker 验证；继承 context 清空且退出恢复。不能推导真实 daemon、GHCR、网络和回滚成功。
- 主机脚本/systemd 的路径、身份、包、容器快照、归属与回退均为静态合同。socket `listening/running` 修复的测试是静态解析白名单，不是 systemd 状态演练。
- runner manifest 校验、用户 unit 与 workflow 精确 URL/UID 配线经契约验证。只有 allexport 的两个案例通过真实本地 Bash 子进程环境检查，且使用假 Token；没有下载、注册或安装服务。
- `.gitattributes` 的 .service/.socket LF 属性实测通过，避免 Windows 检出破坏单元文件。

## 5. 失败项、复现与缺陷状态

| 问题 | 优先级/状态 | 复现方式与回归 |
| --- | --- | --- |
| 继承 DOCKER_CONTEXT 可覆盖 DOCKER_HOST | 工程审阅 P1，已修复 | 非空 context 调用两个门禁的 validate/WhatIf/config 失败路径；6 案例通过，提交 `2a9e749` |
| Accept=no socket 激活后 running 被拒绝 | 工程审阅 P1，已修复 | 静态输入 running 命中旧失败条件；改白名单并保留端口/归属验证，19 项通过，真实状态待 Ubuntu |
| Bash -a/SHELLOPTS 自动导出 runner Token | 工程审阅问题，已修复 | 本地 Git Bash 两种启动模式令假 Token 进入子进程；`set +a` 修复后 2/2 通过 |
| 上一版镜像与 staging callback 不兼容 | 待架构确认/现场回滚阻断 | 历史 `f7c0f9f9` 仅接受 www；本次配置用 staging。不得直接执行并预判成功 |
| 模型四个辅助文件缺少清单 SHA-256 | 待 Task 10 补齐 | 清单只登记两个 weight_sha256；不能宣称六文件摘要已核验 |

本报告不关闭 `DEF-REAL-FS01-006` 或其他既有正式缺陷，不替代前端漏洞独立复测 006 号报告。

## 6. Tasks 8～11 现场状态

| 任务 | 现场检查与状态 | 停止条件 |
| --- | --- | --- |
| 8 主机 | 基础设施已建立；Task 9 前后复核 `crmdeploy` UID/GID 1004、Rootless active/enabled、数据根 `/home/crmdeploy/.local/share/docker`、容器 0，系统 Docker `/var/lib/docker` 与公司容器五字段摘要不变 | 未知配置、权限/路径不符、取证失败或公司容器任何变化 |
| 8 失败/幂等 | 既有工程失败关闭/幂等证据保留；本轮未对公司容器做故障注入 | 禁止拿公司容器做故障注入；安装/重跑不一致 |
| 9 runner | 已通过；官方归档双端验签、Ubuntu 原生安装、用户服务、GitHub online/标签和 Docker 隔离均有主责及独立只读证据 | 后续若归档/身份/目录漂移、runner 离线则重新阻塞 |
| 10 外部材料 | DNS A/NAT/公网 TCP、公信 TLS/匹配私钥/权限、六模型文件与可信摘要、外部配置权限/轮换、Environment main 限制、合并 main 三摘要 | 任一缺失，不进入 deploy |
| 10 validate | 真实 checkout/仓库外路径、完整三层 Compose、固定 socket、无敏感输出、validated 制品 | validate 非零或无合格证据 |
| 11 部署 | 入口 socket 归属、高端口回环、不可变 pull/up/健康等待、首页和三个健康端点、四服务十开关 false、迁移 023 | 健康失败、外部暴露、能力偏离或系统容器改变 |
| 11 恢复/回滚 | PostgreSQL/MinIO 隔离恢复、对象与审计、兼容上一版三摘要、回滚再切回候选、容量和公司快照复核 | 未确定恢复目标/兼容上一版或任何实际恢复失败 |

G1 OAuth/只读、G2 Webhook、G3 人工消息、G4 AI/RAG、G5 真实 SSE、G6 连续五日均待本次 staging 实测；历史固定质量证据按检查表原范围保留，不移植为本环境通过。

## 7. Task 6 文档检查与验收建议

文档检查命令：`git grep -n 'www.hophorsefit.com/v1/integrations/tiktok/oauth/callback'`、`git grep -n 'staging.hophorsefit.com/v1/integrations/tiktok/oauth/callback'`、`git diff --check`，结果分别为 27 行、15 行、无输出 exit 0；另执行 `git diff --cached --check` 无空白错误。语义复核确认生产引用保留、staging 引用属于环境配置/测试语境，三处历史跨环境说明已获架构批准追加勘误，旧测试报告保持原样。两个索引去重后分别 92/122 个非模板文件路径全部存在，三条示例镜像与机器清单逐字匹配且均为不可变摘要。新增行高置信凭据模式扫描零命中，人工复核未新增真实密钥/Token/私钥/模型/虚构现场摘要；详细交接证据登记到 Task 6 报告。

建议：可进入 Task 7 分支全量工程复核；不建议真实运行验收或 production 放行。`基础运行面就绪`、`失败关闭部署通过`、`G1～G6 真实门禁通过`、`production 放行` 必须分别取证和签署。

2026-09-09 Task 6 审阅修复：原 runner 传递命令在 Windows PowerShell 5.1 的原生管道产生 CRLF，本地 Bash `read -r -s` 与安装器相同的严格正则返回 24（RED）。仅修正 runbook 的 SSH 命令，远端 `tr -d '\r'` 规范化并用 `bash -o pipefail` 保留失败。执行 `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .superpowers/sdd/2026-09-09-rootless-staging-deployment/task-6-crlf-check.ps1`，并在 PowerShell 7.6.5 执行同一脚本：两环境各验证正常读取 exit 0 与安装替身失败 exit 37，共 4 个聚焦断言通过，本地 Token 引用两路径均清空。命令从 runbook 提取，仅替换 SSH 网络与注册副作用为本地 Git Bash/严格读取替身；未执行真实 SSH、注册或 Ubuntu 验证，未打印 Token 值，安装器未修改。

### 7.1 Task 7 全量复核发现的测试输入修复（2026-09-09）

控制器在 `d6c72ce73441cc28ab5c5b647d84c29bc8d611a2` 的首次后端全量复核得到 `2 failed, 1420 passed, 14 skipped`（RED）。失败均位于 `tests/test_real_fs05_sse_runtime.py`：`test_sse_load_profile_requires_fifty_request_ip_capacity` 和 `test_real_environment_deepseek_rejects_insecure_base_url` 的 staging 输入仍使用 www 回调，导致 Settings 在 SSE 容量或 DeepSeek HTTPS 断言之前按预期拒绝错误配置。

修复只将上述两处输入改为 staging 专用回调；保留测试名、原断言和 integration/production 地址，不修改生产代码或放宽校验。修复提交主题为 `test: align staging runtime fixtures`，可通过 `git log --all --format='%H %s' --grep='^test: align staging runtime fixtures$'` 解析完整提交，避免记录自身摘要。

以下为修复执行者新运行的 GREEN；运行目录为 `CRM智能聊天系统/backend`，`python` 对应第 3 节的既有 venv：

| 验证项 | 命令 | 准确结果 |
| --- | --- | --- |
| 两个原失败案例 | `python -m pytest tests/test_real_fs05_sse_runtime.py::test_sse_load_profile_requires_fifty_request_ip_capacity tests/test_real_fs05_sse_runtime.py::test_real_environment_deepseek_rejects_insecure_base_url -q -p no:cacheprovider --basetemp='C:\Users\Administrator\AppData\Local\Temp\crm-rootless-task7-fix1-focused-20260909'` | 2 passed in 1.71s |
| 环境映射及完整 SSE 模块 | `python -m pytest tests/test_real_runtime_config.py tests/test_real_fs05_sse_runtime.py -q -p no:cacheprovider --basetemp='C:\Users\Administrator\AppData\Local\Temp\crm-rootless-task7-fix1-regression-20260909'` | 106 passed in 2.40s |
| 修改文件静态质量 | `python -m ruff check tests/test_real_fs05_sse_runtime.py`；`python -m ruff format --check tests/test_real_fs05_sse_runtime.py`；`git diff --check` | All checks passed；1 file already formatted；无空白错误 |

两个 basetemp 均位于仓库外。控制器随后在修复提交 `6323316f35560b6f9c755c5e46966f3ac5da27cb` 完成仓库外 basetemp 的后端全量复核，准确结果为 `1422 passed, 14 skipped, 2 warnings in 30.00s`，exit 0；两条 warning 为依赖弃用警告，不计作测试失败。控制器较早的新一轮聚焦回归结果为 `193 passed, 2 skipped in 25.61s`，exit 0。以上两项为控制器运行结果，本次文档更新未重复执行；跳过项不计为通过。现场部署、G1～G6、独立验收及 production 状态不变。

Task 7 仓库卫生检查发现唯一误跟踪的 SDD 临时证据 `.superpowers/sdd/2026-09-09-rootless-staging-deployment/task-1-report.md`，本次仅从 Git 索引移除，保留本地原文件并由既有 `.superpowers/sdd/.gitignore` 忽略。正式证据继续保留于本报告，不将临时调度记录作为版本化交付物。

### 7.2 Task 7 staging 应用安全边界修复（2026-09-09）

分支审阅在 `a6457e8488858c7631a5ff58472ae33929b163df` 确认两个 P1 合并阻断：基础安全仅对 production 生效；Shopee/Amazon resolver 及 Mock defensive send 在非 production 忽略 `ALLOW_MOCK_PLATFORM_ADAPTERS=false`。本轮先增加真实 Settings/adapter 行为测试并运行 RED，再最小修复；不依赖源码文本断言、不调用网络/数据库/真实平台。

修复将 staging 纳入既有基础校验，保留 development/test/integration 夹具行为以及独立的 SSE/真实 LLM 门禁。三个 Mock guard 直接以显式开关为准，所有环境关闭时均失败关闭。TikTok 真实能力 resolver 条件和三平台 UI 不变。原 staging SSE 正常路径测试补齐虚构安全配置，原压测容量断言保留。

修复提交主题为 `fix: enforce staging application security`；完整 SHA 使用 `git log --all --format='%H %s' --grep='^fix: enforce staging application security$'` 解析，避免提交自身摘要的循环。以下命令均在 `CRM智能聊天系统/backend` 执行，`python` 对应第 3 节的既有 venv：

| 验证项 | 命令 | 准确结果 |
| --- | --- | --- |
| 新行为 RED（产品代码未修改） | `python -m pytest tests/test_real_runtime_config.py tests/test_platform_adapters.py -k 'deployed_security_baseline or disabled_mock or enabled_mock_contract' -q --tb=short -p no:cacheprovider --basetemp='C:/Users/Administrator/AppData/Local/Temp/crm-rootless-task7-fix2-red-20260909'` | 52 failed, 50 passed, 85 deselected in 0.88s，exit 1 |
| 同一选择集 GREEN | 同上，basetemp 改为 `C:/Users/Administrator/AppData/Local/Temp/crm-rootless-task7-fix2-green-20260909` | 102 passed, 85 deselected in 0.54s，exit 0 |
| 首次完整模块检查 | `python -m pytest tests/test_real_runtime_config.py tests/test_real_fs05_sse_runtime.py tests/test_platform_adapters.py -q --tb=short -p no:cacheprovider --basetemp='C:/Users/Administrator/AppData/Local/Temp/crm-rootless-task7-fix2-modules-20260909'` | 1 failed, 212 passed in 2.96s；旧 SSE staging 夹具因未启用 Secure Cookie 被正确拒绝 |
| 完整模块 GREEN | 同上，basetemp 改为 `C:/Users/Administrator/AppData/Local/Temp/crm-rootless-task7-fix2-modules-green-20260909` | 213 passed in 2.63s，exit 0 |
| TikTok 邻接回归 | `python -m pytest tests/test_tiktok_oauth.py tests/test_tiktok_read.py tests/test_tiktok_write.py -q --tb=short -p no:cacheprovider --basetemp='C:/Users/Administrator/AppData/Local/Temp/crm-rootless-task7-fix2-tiktok-20260909'` | 64 passed in 1.70s，exit 0 |
| 静态质量 | `python -m ruff check app/shared/config/settings.py app/integrations/adapters.py tests/test_real_runtime_config.py tests/test_real_fs05_sse_runtime.py tests/test_platform_adapters.py`；相同路径的 `python -m ruff format --check`；`git diff --check` | All checks passed；5 files already formatted；无空白错误 |

RED 的 52 个失败均为目标行为缺失：24 个 staging 不安全配置未抛 ValidationError，16 个 Shopee/Amazon resolver 未抛 AppError，12 个直接 Mock 发送返回 sent 而非 failed。生产拒绝、TikTok resolver 拒绝及显式开启开发/测试 Mock 的对照组均通过。修改 guard 回 production-only 会重新触发这些失败。

上述为开发修复自测。§7.1 的全量结果早于本次产品修复，不能作为本次最终全量通过证据；控制器必须重新运行后端全套并完成独立审阅。该段记录的是 2026-09-09 当时状态；Tasks 8/9 的后续现场结论见 §8.1，Task 10～12、G1～G6 和 production 仍待执行。

### 7.3 Task 7 审阅覆盖补充（2026-09-09）

在 `fc1d0d269b2fab1c353f7eafd945ca974739442f` 后补充三个 Minor 覆盖建议，未修改生产代码：integration 明确拒绝 staging 回调（既有 exact www 正向继续保留）；Mock=false 的 TikTok Webhook/普通消息两个开关交叉隔离；fake Docker 命令日志逐次断言 `--project-name crm-staging`、`--profile ai` 以及按顺序的 base/prod/rootless-staging 三个 `-f`。该三层契约经控制器核对，不额外加入 `docker-compose.ai.yml`。

命令参数断言覆盖两个脚本的 ValidateOnly、WhatIf、config 失败和健康等待失败路径中实际可达的全部 config/pull/up 调用；只排除不接受项目参数的 `compose version` 探测。它检查 CLI 实参而非源码片段；fake Docker 不启动容器。

提交主题 `test: harden staging boundary regressions`；完整 SHA 可通过 `git log --all --format='%H %s' --grep='^test: harden staging boundary regressions$'` 解析。以下均在 backend 执行，使用第 3 节 Python：

| 验证项 | 命令 | 准确结果 |
| --- | --- | --- |
| 最终聚焦 | `python -m pytest tests/test_real_runtime_config.py tests/test_platform_adapters.py tests/test_production_gate_scripts.py -k 'another_environments or real_capabilities_resolve or clear_and_restore_inherited or live_gate_waits' -q --tb=short -p no:cacheprovider --basetemp='C:/Users/Administrator/AppData/Local/Temp/crm-rootless-task7-coverage-focused-final-20260909'` | 13 passed, 239 deselected in 5.63s，exit 0 |
| 三个完整模块 | `python -m pytest tests/test_real_runtime_config.py tests/test_platform_adapters.py tests/test_production_gate_scripts.py -q --tb=short -p no:cacheprovider --basetemp='C:/Users/Administrator/AppData/Local/Temp/crm-rootless-task7-coverage-modules-20260909'` | 250 passed, 2 skipped in 25.75s，exit 0 |
| 静态质量 | `python -m ruff check tests/test_real_runtime_config.py tests/test_platform_adapters.py tests/test_production_gate_scripts.py`；同路径 `python -m ruff format --check`；`git diff --check` | All checks passed；3 files already formatted；无空白错误 |

两个跳过项仍为既有 Windows 文件 symlink 案例，不计通过。本次为现有行为的补充回归，首次执行即通过，不声明 RED 或新功能实现。该段记录的是 2026-09-09 当时状态；控制器后续全量结果见 §7.4，Tasks 8/9 现场见 §8.1，Task 10～12 和 G1～G6 仍待执行。

### 7.4 Task 7 最终控制器复核（2026-09-09）

控制器在最终待记录提交 `0eb399c763928586276f8c7aa6746f95f663608d` 上重新执行计划要求的四文件聚焦回归及后端全量测试，报告如下准确结果。本次文档记录者引用控制器新运行结果，没有重复执行或将先前结果冒充本轮结果。

| 验证范围 | 控制器准确结果 | 退出状态 |
| --- | --- | --- |
| 计划要求的四文件聚焦回归 | 245 passed, 2 skipped in 26.69s | exit 0 |
| 后端全量 | 1527 passed, 14 skipped, 2 warnings in 35.18s | exit 0 |

两条 warning 为既有 Starlette/httpx 与 passlib/argon2 依赖弃用警告，不是测试失败；跳过项不计为通过。本轮结果完成 §7.2～7.3 所要求的修复后控制器全量复核，本地仓库实现验证通过。该段记录的是 Task 7 结束时状态；Tasks 8/9 的后续现场结论见 §8.1，Task 10～12、G1～G6 和 production 门禁仍待执行，`production_release=false`。

## 8. 后续现场证据（Task 12）

2026-09-09 Task 6 最终审阅计划勘误：Task 10 明确模型清单仅登记两个权重摘要，四个辅助文件需可信摘要和审阅后的机器可读权威（或架构明确降低要求），缺失时禁止启动；Task 11 明确先安装/核对 socket 监听与配置，deploy 后真实连接/健康并重跑安装器验证激活幂等；上一版必须是与候选不同且兼容 staging 回调、迁移 023 和配置的已审阅三摘要，历史 `f7c0f9f9` 不可直接作为成功回滚目标。仅校正计划并检查文档差异，未运行模型、主机、健康或回滚验证，live 与 G1～G6 仍待执行。

### 8.1 Task 9 Runner 现场证据（2026-09-10）

- 执行基线：clean main `bf5640acc0c9f2918de9831f30097951a985bd3b`。相关供应链修复经 PR #13/#14/#15 squash merge；PR #13 的初始 Linux 动态证据 run `34429552119` 和最终 head run `34432014630`、PR #14 run `34437014325`、PR #15 run `34439346391` 的后端/前端门禁均通过。
- 版本资产：安装器、清单、user unit 摘要分别为 `a3c617dd3295abdc99013668f0373b378a7ad253d9ee862e1f9236ac38da1bc3`、`decdd9666720e1d24daca210ff874ac7372cf4e08e7a4bafc4783936d1277742`、`4a2ed0d68218ea49460efb2c356a5bd6bed6f1137c20b85c015c4215ede4199a`；本地、incoming 和最终版本目录复验一致。
- 工具归档：Runner `2.336.0` 为 226035903 字节、SHA-256 `04cf0be1aff4c3ec3554466c39124ca250e3effd8873bb7e8d68535aa9505d5d`；PowerShell `7.6.5` 为 73393424 字节、SHA-256 `b34ab3b19acac1d3d4d0d3cfdb02acf62f457b0b6a962ff008132033f7566844`。二者均从清单官方 URL 获取，经本地和远端完整验签后成为 UID 1004、mode `0600` 的非链接密封文件。
- 安装与注册：PowerShell `7.6.5`、Runner.Listener `2.336.0`；`crm-staging-runner.service` active/enabled/running、ExecMainStatus `0`。GitHub 唯一 runner `crm-staging-192-168-110-210` online、busy=false，标签为 `self-hosted`、`Linux`、`X64`、`crm-staging`。
- 凭据边界：`.runner`、`.credentials`、`.credentials_rsaparams` 和用户 unit 仅检查元数据，均为 UID/GID 1004、mode `0600` 的普通非链接文件；注册 Token 仅在同一远端进程中经 stdin 使用，未输出、落盘、导出或进入 argv。
- 隔离结果：Rootless Docker active/enabled、数据根 `/home/crmdeploy/.local/share/docker`、容器 0；系统 Docker 数据根 `/var/lib/docker`、容器 14 个/运行中 12 个，按 `Id|Name|Image|StartedAt|Running` 排序的 SHA-256 为 `d807427f814e97ffb27ed16a5c6409ab732def8b27841fe209a9b47880226cdb`，与基线一致。
- 失败关闭：首次 Windows SCP 产生 `0664` 时流程在权限门禁退出，未提升、未取 Token、未安装。两项顺序缺陷通过 PR #14/#15 修复；首次失败 incoming 与两个历史 partial 的两次独立元数据快照完全一致，均未覆盖或删除。
- 独立复核：测试工程师Agent 以只读 SSH/GitHub 查询逐项重验，结论 READY，Critical/Important/Minor 均为 0；未读取凭据内容或改变本地、服务器及 GitHub 状态。

Task 9 已关闭。Task 10 仍需 DNS/TLS、六文件模型可信摘要、外部配置与候选镜像 RepoDigest；Task 11 仍需应用部署、健康、迁移 023、恢复和兼容回滚；Task 12 还需汇总候选/上一版摘要及 G1～G6。不得把本节解释为 staging 应用或 production 放行。
