# 最新测试状态

本文件只汇总当前仍有效的正式结论。历史报告用于追溯，不代表本分支重新运行。生产是否可放行以 `../operations/RELEASE-GATES.md` 为准。

## 模块状态

2026-10-17 G5 R37：已授权的手动窗口完成六摘要预取和 G5 validate，迁移容器因 backend 未收到仓库外已有的内部检索令牌而失败；没有签发第四份凭证或发起合成 SSE/DeepSeek。旧后端、TikTok Webhook 只读和工作台翻译按门禁恢复，三健康 200。修复仅在 G5 backend 注入令牌并于部署前要求与检索服务一致且长度至少 32；本地完整后端 `1973 passed, 27 skipped`，subject 后 staging 门禁 `145 passed`，Ruff 和 PowerShell AST 通过。修复后的现场部署及单会话尚未执行，G5/production 继续未通过。见 [R37 TR](../reports/tests/TR-MVP-006-20261017-R37.md)。

2026-10-17 G5 R34：续期工具改为原 R05 批次连续编号文件、逐份验签与 50 用户/会话映射校验；红灯后修复，定向 `26 passed`，后端全量 `1962 passed, 27 skipped`，全量 Ruff、183 文件 mypy 及两份 PowerShell AST 通过。仅是本地源码门禁，[R34 TR](../reports/tests/TR-MVP-006-20261017-R34.md) 未签发新令牌、发布镜像或在 staging 复测；G5/production 继续未通过。

2026-10-17 G5 R33：[staging 空闲采样](../reports/tests/TR-MVP-006-20261017-R33.md)在 Linux/Rootless 下读取 3 组 backend/worker/agent-worker 资源与 backend TCP 白名单指标，服务器与入库副本哈希一致。未施加 SSE 负载，不能作为 50 并发容量证据；第三份凭证的 50/50 枚令牌已过期。G5/production 继续未通过。

2026-10-17 G5 R32：获批的手动单会话 SSE 在 `accepted` 后返回 `50003`，没有安全 `delta`，随后原 TikTok 只读加工作台翻译模式已通过 validate/deploy 与三个公网健康检查恢复。G5 backend 缺少 Agent 必需的本地检索开关；修复 subject `4eee102` 的定向 14 项、完整 staging 门禁文件 142 项及全量后端 `1959 passed, 27 skipped`，Ruff/PowerShell AST 均通过。修复尚未在 staging 复测；G5/production 未通过。见 [R32 TR](../reports/tests/TR-MVP-006-20261017-R32.md)。

2026-10-17 G5 R31：只读资源/TCP 队列采样器与格式修复主线整合后的 `9712c5a8` 本地全量后端 pytest `1955 passed, 27 skipped`、Ruff lint/format 与 mypy 通过；前端 47 项契约、lint/typecheck/build 通过。PR #281 的 GitHub Actions 作业均在首步前失败，不能作为代码测试结论；用户决定 G5 改用 GitHub 凭据和 staging 手动路径。格式基线已由 PR #283 修复，采样器仍待合并，尚未在 Linux staging 运行；单会话安全 `delta`、真实 50 并发、资源峰值与恢复仍无现场结论，G5/production 未通过。见 [R31 TR](../reports/tests/TR-MVP-006-20261017-R31.md)。

2026-10-17 `TEST-CI-FORMAT-001`：锁定 Ruff 0.16.3 对三个既有 G5 测试文件作纯排版修复；全量 Ruff lint/format 通过，三文件 AST 一致、定向 43 passed，见 [TR](../reports/tests/TR-TEST-CI-FORMAT-001-20261017-R01.md)。PR #283 已经按手动等价验证 squash 合入 main `2da8e172`；GitHub Actions 作业因账户计费在首步前失败，未被记为通过。

2026-10-17 G5 R29：用户精确授权的单次凭证续期返回 50 枚短期令牌、数据库写入和 Provider 调用均为 0；独立只读 `ContentCheck` 为 50/50 会话、凭证 renewed、知识 ready，第三份私有文件权限 `600`。见 [R29 TR](../reports/tests/TR-MVP-006-20261017-R29.md)。未运行 `/auth/me` 端到端预检、单会话 SSE 或真实 50 并发，G5/production 未通过。

2026-10-17 G5 R28：获批的第二次、也是修复后唯一一次本地 BGE 向量化成功；独立 `ContentCheck` 为 `knowledge_ready=true`、50/50 会话、原凭证，SQL 检索门禁为 1 个合格片段，DeepSeek 0，三健康 200，常驻 Embedding/LLM/TikTok 写入仍关闭。见 [R28 TR](../reports/tests/TR-MVP-006-20261017-R28.md)。短期凭证、单会话及 50 并发仍未验收，G5/production 未通过。

2026-10-17 G5 R26–R27：获批单次向量化因单文件挂载不满足旧源码挂载安全门禁而失败；只读对账 50/50、FAQ pending、chunk 0、原凭证。修复恢复完整受审源码只读挂载，相关测试 51 passed，未二次运行。见 [R26 TR](../reports/tests/TR-MVP-006-20261017-R26.md)与[R27 TR](../reports/tests/TR-MVP-006-20261017-R27.md)。G5/production 未通过。

2026-10-17 G5 R24 现场内容准备：一次获批 `ContentPrepare` 写入原隔离店铺 50 条合成提问和 1 条内部审阅级 FAQ；写前/写后只读对账均为 50/50 会话，写后 `fixture_state=prepared`、凭证仍为原状态，Provider 调用 0。三项公网健康仍为 200。`EMBEDDING_ENABLED=false` 使 FAQ 尚未向量化，`knowledge_ready=false`；见 [R24 TR](../reports/tests/TR-MVP-006-20261017-R24.md)。凭证续期、SSE、DeepSeek 和 50 并发未执行，G5/production 仍未通过。

2026-10-17 G5 R23 手动 staging：从 main `7b7acc35` 发布的后端 `sha256:477d571d…cb293` 经六角色预取、validate/deploy 和独立核对运行；前端/检索不变，迁移头、三个公网健康 200、固定出口、TikTok 只读与工作台翻译通过，G5 SSE 关闭且限流 10。零调用内容检查仍为原 50/50 会话、知识未准备、凭证原状态，Provider/数据库写入 0。首次 tar 解包路径因下层门禁要求 Git checkout 而在切换前失败，改用同一 SHA 的干净浅克隆后通过。见 [R23 TR](../reports/tests/TR-MVP-006-20261017-R23.md)。未写入合成数据、续期、调用 DeepSeek 或运行 50 并发；G5/production 未通过。

2026-10-17 G5 R22 手动夹具源码：从受审源码与运行镜像精确核对后，手动内容入口可分别只读检查、准备 50 条合成问题和内部审阅 FAQ、续期私有凭证；续期后只读对账与异常文件名拒绝经回归覆盖。完整后端 `1929 passed, 27 skipped`，定向 `36 passed`，Ruff、格式、mypy、PowerShell AST 与独立审查通过。见 [R22 TR](../reports/tests/TR-MVP-006-20261017-R22.md)。未发布新镜像或在 staging 执行本入口，G5/production 未通过。

2026-10-16 G5 R21 手动恢复源码：新增 `RestoreReadAndTranslation`，在结束 SSE 窗口后通过原 Rootless 门禁同时恢复 TikTok 只读与工作台翻译，并核对通用模型/SSE 关闭及限流 10。本地相关门禁完整回归 `151 passed`、格式后定向 `22 passed`、Ruff/格式及 PowerShell AST 通过，独立代码审查无严重或重要问题。见 [R21 TR](../reports/tests/TR-MVP-006-20261016-R21.md)。未执行 staging G5 窗口或恢复演练，G5/production 仍未通过。

2026-10-16 G5 R20 手动只读现场：新版界面配套后端 `sha256:deef65ee…babbe8` 运行时，受审源码 `f56b998` 的归档校验和手动 `CheckOnly` 通过；原批次 50/50 会话匹配，`fixture_state=original`、`knowledge_ready=false`，Provider 调用与数据库写入均为 0。容器默认工作目录导致第一次安全路径校验拒绝；显式设置受审目录后只读检查通过，持久入口待修。见 [R20 TR](../reports/tests/TR-MVP-006-20261016-R20.md) 与 [低敏证据](../../release/evidence/staging/crm-staging-g5-manual-content-check-20261016.json)。未准备内容、续期凭证、执行 SSE 或恢复演练；G5 与 production 仍未通过。

2026-10-16 `MVP-CONV-UI-001` R04 现场 `f56b998`：staging 后端新摘要、前端已验证摘要运行健康，门禁迁移及三项公开健康 200；已登录工作台显示 179 个真实 TikTok 会话，买家左侧白色、客服右侧蓝色。分别对一条英文买家和客服消息按需调用 DeepSeek 后，原文下方显示中文；回复输入与发送按钮禁用。真实译质需坐席核对，真实发信和 production 仍关闭。见 [R04 TR](../reports/tests/TR-MVP-CONV-UI-001-20261016-R04.md) 与 [低敏门禁证据](../../release/evidence/staging/crm-staging-conv-ui-translation-20261016.json)。

2026-10-16 `MVP-CONV-UI-001` R03 翻译 Prompt 候选 `81f9963`：staging 的 `14ec836` 已显示 179 个真实 TikTok 会话、双侧气泡、原文与按需翻译入口，三项公开健康为 200；真实消息首次两次 DeepSeek 翻译因 `LLM_OUTPUT_INVALID` 失败。合成探针定位旧提示词未说明输出字段；R03 明确四字段后同模型合成句返回可校验中文，受影响后端 602 passed、Ruff 与格式通过。R03 镜像尚未部署，真实译文待现场复测，见 [R03 TR](../reports/tests/TR-MVP-CONV-UI-001-20261016-R03.md)。真实发信与 production 关闭。

2026-10-16 `MVP-CONV-UI-001` R02 前端依赖候选 `7ec8062`：官方 npm 生产依赖审计 0 vulnerabilities，Next.js `16.3.8`、`sharp` `0.35.5`、`source-map-js` `1.2.2`；前端契约 45 passed、本地生产构建浏览器 26 passed，lint 0 错误/2 条原有警告、typecheck/build 通过。R01 的双语 UI/后端测试证据仍有效；新镜像及真实 staging 页面尚未验收，见 [R02 TR](../reports/tests/TR-MVP-CONV-UI-001-20261016-R02.md)。

2026-10-16 `MVP-CONV-UI-001` 候选 `93b8476`：后端翻译/门禁相关 150 passed，前端契约 45 passed，本地生产构建合成浏览器 26 passed；Ruff、格式、mypy、lint、typecheck、build 通过。合成浏览器确认买家左侧、卖家右侧、按需中文译文与平台发信 0 次。尚未发布后端/前端镜像、部署 staging 或对真实消息调用 DeepSeek；现场 UI/译文待验，见 [R01 TR](../reports/tests/TR-MVP-CONV-UI-001-20261016-R01.md)。真实消息写与 production 仍关闭。

2026-10-16 `MVP-CONV-SYNC-001` staging 只读现场：授权 TikTok 会话 179 个、可见消息 2018 条，工作台接口 6 页返回 179 个不重复会话；截图目标平台 29 条原始历史中的 25 条可见消息全部在工作台详情。R02 前端 45 契约测试、24 浏览器回归通过，1 项缓存配置测试跳过，类型检查与构建通过；PR #250 双 CI 合入。用户授权的手动 staging validate/deploy 使用固定源码包和不可变摘要均通过；新版前端运行且三个健康接口 200。浏览器现场显示真实会话总数 179、列表由 30 条加载至 60 条、目标历史及角色标签；回复输入与发送按钮禁用。真实消息写关闭，G2/G3 未通过；完整范围见 [R03 TR](../reports/tests/TR-MVP-CONV-SYNC-001-20261016-R03.md)，production No-Go。

2026-10-16 G5 R16 源码：subject `c3439013` 新增原隔离店铺的合成 FAQ/问题和短期凭证续期精确门禁；最终完整后端 `1892 passed, 27 skipped`，隔离 PostgreSQL 4 passed，Ruff、格式、mypy、工作流 PowerShell AST 通过；[PR #251](https://github.com/CP11-gh/CRM/pull/251) 前后端 CI #38890253045 均通过并 squash 合入 main `5d6c0298`，见[R16 TR](../reports/tests/TR-MVP-006-20261016-R16.md)。未在 staging 写入内容、轮换凭证、发布镜像或调用模型；R14 的限流 10 仍是最近明确现场值。G5、production No-Go。

2026-10-16 G5 R14：用户授权的精确邮箱修复 [#38878859064](https://github.com/CP11-gh/CRM/actions/runs/38878859064) 更新原 50 用户、轮换 50 令牌并保留旧 manifest，`provision` skipped、Provider 0。紧接的只读[预检 #38878976347](https://github.com/CP11-gh/CRM/actions/runs/38878976347) 为 50/50 身份及会话可用、失败类别为空；生效单 IP 限流 10 小于 50，工作流按门禁失败关闭，未发送 SSE 负载。[R14 TR](../reports/tests/TR-MVP-006-20261016-R14.md)及[低敏证据](../../release/evidence/staging/crm-staging-g5-fixture-repair-20261016.json)已记录。G5、production No-Go。

2026-10-16 G5 R13：PR #245 双 CI 通过并合入 main `26a4e8e`；[staging 只读对账 #38877932619](https://github.com/CP11-gh/CRM/actions/runs/38877932619) 核对源码、运行摘要、数据库目标和原私有 manifest，报告 50 个匹配账号、Provider 0、数据库写入 0。`reconcile_email`、`provision`、50 身份预检均未执行。原认证失败和生效限流 10 尚未解除；[R13 TR](../reports/tests/TR-MVP-006-20261016-R13.md)及[低敏证据](../../release/evidence/staging/crm-staging-g5-reconcile-check-38877932619.json)。G5、production No-Go。

2026-10-16 G5 R12 源码候选：完整后端 1858 passed/3 skipped；隔离 PostgreSQL 夹具 3 passed，定向 16 passed；Ruff、格式、mypy 与工作流八段 PowerShell AST 通过。`@example.invalid` 在真实 `/auth/me` 路径触发 `ValidationError`/500 的本地复现已转为测试；新夹具改用有效邮箱格式。只读 `reconcile_check` 与需要精确确认的 `reconcile_email` 已分离，后者只针对 R05 原 50 账号、独占新私有凭证文件，保留原 manifest。尚未合入 main、未运行 staging 只读对账或写入；50 身份、限流与真实负载仍未通过，G5、production No-Go。

2026-10-16 G5 R11：[固定窗日志回查 #38866573949](https://github.com/CP11-gh/CRM/actions/runs/38866573949) 从 main `fafbac740` 成功执行，但只输出 `matched_events=0`、Provider 0；不能据此确认 HTTP 500 的异常类型。原夹具邮箱 `@example.invalid` 被当前 `EmailStr` 本地复现拒绝，属于待现场核实的原因；[R11 TR](../reports/tests/TR-MVP-006-20261016-R11.md)与[低敏证据](../../release/evidence/staging/crm-staging-g5-auth-log-recheck-38866573949.json)已记录。50 身份与会话、限流 50、安全输出及真实 50 并发仍未通过，G5、production No-Go。

2026-10-16 G5 R10：[固定窗只读探针 #38864445483](https://github.com/CP11-gh/CRM/actions/runs/38864445483)在报告计数类型检查处失败，未产生异常类型结论；[低敏失败证据](../../release/evidence/staging/crm-staging-g5-auth-log-probe-38864445483.json)。修复 subject 9b478fb 聚焦 3 passed、七段 AST 与本机模拟 JSON 校验通过，PR #243 双 CI 通过并合入 main `fafbac740`；现场回查结果见 R11。G5、production No-Go。

2026-10-16 G5 R09：[获批单令牌只读诊断 #38862950177](https://github.com/CP11-gh/CRM/actions/runs/38862950177) 在 main 1626622 返回本地有效的令牌与一致的运行签名配置，但 /auth/me 为 HTTP 500 / API 50001；没有运行 50 身份预检、provision 或模型。[低敏证据](../../release/evidence/staging/crm-staging-g5-auth-status-38862950177.json)。固定日志窗只读探针 subject 47aae95 本地 1851 passed/20 skipped、Ruff/格式/mypy 和工作流语法通过；现场异常类型待核对。G5、production No-Go。

2026-10-16 G5 R08：一次获批的 [只读诊断 #38861412442](https://github.com/CP11-gh/CRM/actions/runs/38861412442) 在 main fbe1b81 上报告首枚令牌 valid、运行密钥和算法匹配、一次 /auth/me 状态 other、Provider 0；旧类别无法细分响应。[低敏证据](../../release/evidence/staging/crm-staging-g5-auth-diagnostic-38861412442.json)已保留。获批的状态/白名单 API 错误码细分在 subject f15bb3a 的定向 15 passed、完整后端 1849 passed/20 skipped、Ruff/格式/mypy 通过；最终 PR CI 和第二次现场只读诊断待核对。50 身份认证和限流 50 尚未通过，G5、production No-Go。

2026-10-16 G5 R07：PR #239 双 CI 通过并合入 main `7e12314`；[staging 只读预检 #38858709981](https://github.com/CP11-gh/CRM/actions/runs/38858709981) 返回 50 次 `auth_rejected`、运行限流 10、Token 有效期 120 分钟、Provider 0，按门禁失败关闭。第一枚令牌的签名、算法、必需声明、过期及签发配置与运行配置匹配诊断已在 subject `fe65b93` 实现，最终定向 11 passed、Ruff/格式/mypy 通过；本地完整后端 1842 passed/20 skipped 属前一源码提交，最终 CI 待核对，见 [R07 TR](../reports/tests/TR-MVP-006-20261016-R07.md)；现场诊断尚未运行。G5、G6 与 production 未通过。

2026-10-16 G5 R06 只读预检源码候选：subject `8493fc8` 增加 staging Runner 50 身份/会话 GET、运行限流和 Token 有效期核对；审查发现低于 50 限流仍可能误报成功，已增加失败门禁。最终聚焦 39 passed、五段 PowerShell AST 通过，完整后端 1837 passed/20 skipped 的执行范围见 [R06 TR](../reports/tests/TR-MVP-006-20261016-R06.md)。PR #239 最终 CI 与现场运行尚待复核；真实 50 并发与 production 仍未通过。

2026-10-16 G5 R05 现场夹具：一次获批的 [staging 工作流 #38852775454](https://github.com/CP11-gh/CRM/actions/runs/38852775454)在 main `a202c755` 核对源码、运行镜像和数据库目标后成功创建 50 个隔离 CRM 账号及 50 个会话，Provider 0，私有凭证 manifest 保留在仓库外，见 [R05 TR](../reports/tests/TR-MVP-006-20261016-R05.md)。R01 逐一认证/会话预检尚未运行，真实限流、知识命中、安全输出及 50 并发尚无现场证据；G5、G6 与 production 未通过。

2026-10-16 G5 R04 现场只读前置检查：PR #234 前后端 CI 通过并合入 main `814590f`；一次获批的 [工作流 #38847788672](https://github.com/CP11-gh/CRM/actions/runs/38847788672)在 staging 成功核对源码、运行后端、数据库指纹和私有路径，返回 ready、Provider 0、业务写入 0，`provision` skipped，见 [R04 TR](../reports/tests/TR-MVP-006-20261016-R04.md)。尚未创建 50 个账号或运行 R01 账号认证预检；G5、G6 与 production 未通过。

2026-10-16 G5 R03 Runner 入口源码：subject `feaaf5e` 增加 main/运行镜像/数据库指纹核对、只读 `check_only` 与单独确认的 `provision`。独立审查发现并修复无 Git 镜像的私有路径校验问题；最终源码聚焦 15 passed，前一源码提交的本地完整后端 1835 passed/20 skipped、隔离 PostgreSQL 1852 passed/3 skipped，Ruff/格式/Linux mypy 通过，最终完整回归待 PR CI，见 [R03 TR](../reports/tests/TR-MVP-006-20261016-R03.md)。此处尚未把代码合入 main 或运行现场检查；G5 仍未通过，production No-Go。

2026-10-16 G5 R02 源码准备：用户确认只提交隔离 staging 账号工具、测试和清理方案，subject `dae1083`。最小 `workspace.view`、50 独立会话、数据库指纹、Linux 私有凭证、提交结果未知时保留 manifest 均经确定性测试；完整后端 1827 passed/20 skipped，隔离 PostgreSQL 新增测试 1 passed，Ruff/格式/Windows 与 Linux mypy 通过，PR #232 前后端 CI 通过并合入 main `4440440`；隔离 PostgreSQL 全量 1844 passed/3 skipped，见 [R02 TR](../reports/tests/TR-MVP-006-20261016-R02.md)。本轮没有在 staging 创建账号、运行只读预检或调用模型。合成店铺没有可检索的已审批 FAQ，安全 `delta` 和 50 并发仍未验证；G5 未通过，production No-Go。

2026-10-16 G5 R01 源码准备：从 main `beb24b7` 的 subject `9ca964b` 增加零模型调用只读凭证预检。定向 36 passed，完整后端 1820 passed/19 skipped，Ruff、格式及 mypy 通过；[PR #230](https://github.com/CP11-gh/CRM/pull/230) 双 CI 通过并合入 main `b66ecd0`，低敏报告只含计数和固定失败类别，见 [R01 TR](../reports/tests/TR-MVP-006-20261016-R01.md)。尚无仓库外 50 个受控账号的现场凭证池，因此未运行真实预检、50 并发或 DeepSeek 负载；G5 未通过，production No-Go。

2026-10-16 G4 R56：用户在精确付费范围说明后要求继续，[完整 live #38832517813](https://github.com/CP11-gh/CRM/actions/runs/38832517813) 从 main `54594dc4` 和 R55 staging 后端 `sha256:1045d683…eec363` 执行。冻结 34 条 DeepSeek 合成样本加 2 条本地故障注入，终态 36/36、危险逃逸 0、合法误拦 0、Provider 故障 0，报告 `passed=true`；R52 的售后与多语言两条失败均经受控政策修复通过。原样低敏报告、SHA-256、调用/延迟/费用估算及外推边界见 [R56 TR](../reports/tests/TR-MVP-005-20261016-R56.md)。[PR #228](https://github.com/CP11-gh/CRM/pull/228) 前后端 CI 通过并合入 main `7ed1bfe`。G4 冻结合成质量门禁通过；真实买家闭环、50 客户端 SSE、五日稳定性和 production 仍按独立门禁验收。

2026-10-15 G4 R55 staging：用户单独授权的[六摘要预取 #38710281674](https://github.com/CP11-gh/CRM/actions/runs/38710281674)、[validate #38712087142](https://github.com/CP11-gh/CRM/actions/runs/38712087142)、[deploy #38712441191](https://github.com/CP11-gh/CRM/actions/runs/38712441191) 与零调用 [prepare #38713090896](https://github.com/CP11-gh/CRM/actions/runs/38713090896) 均从 main `86ac3dd` 成功。staging 后端已切到 `sha256:1045d683…eec363`，前端/检索不变；迁移头、三健康、固定出口与 Webhook 只读通过。prepare 核对冻结 36 条及 Provider 调用 0，原样证据与哈希见 [R55 TR](../reports/tests/TR-MVP-005-20261015-R55.md)；[PR #226](https://github.com/CP11-gh/CRM/pull/226) 前后端 CI 通过并合入 main `cf362c4`。尚未运行新版付费 `live`；R52 仍是最新真实质量失败，G4 `PARTIAL`、production No-Go。

2026-10-15 G4 R54 单镜像发布：用户在精确范围后批准继续；从 main `6e41632` 仅运行一次[后端发布 #38708209437](https://github.com/CP11-gh/CRM/actions/runs/38708209437)，生成 `ghcr.io/cp11-gh/crm-backend@sha256:1045d683…eec363`。原样[镜像证据](../../release/evidence/staging/crm-staging-g4-r54-image-38708209437.json)确认 `linux/amd64` manifest `PASS`、压缩层 110,072,185 字节、最大层 33,257,532 字节；原始/入库哈希一致；[PR #224](https://github.com/CP11-gh/CRM/pull/224) 前后端 CI 通过并合入 main `eda95db`，见 [R54 TR](../reports/tests/TR-MVP-005-20261015-R54.md)。本轮未部署 staging 或调用 DeepSeek；R52 仍是最新真实质量，G4 `PARTIAL`、production No-Go。

2026-10-15 G4 R53 源码候选：从 main `5ac6da6` 的 subject `1d15123` 将内部政策诊断码从模型修复请求移出，改用固定白名单自然语言要求，Prompt 升至 `real-model-eval-v1.2.13` 并保留严格 `reason_code` 枚举。先红后绿，subject 上六个相关文件 92 passed；定向 Ruff 和格式通过，本地 mypy 长时间无输出后中断；[PR #222](https://github.com/CP11-gh/CRM/pull/222) 前后端 CI（含后端类型检查）通过并合入 main `39f18d6`。见 [R53 TR](../reports/tests/TR-MVP-005-20261015-R53.md)。尚未发布镜像、部署或调用 DeepSeek；下方 R52 仍是最新现场，G4 `PARTIAL`、production No-Go。

2026-10-15 G4 R52：当前 main `1937336` 的零调用 [prepare #38702143931](https://github.com/CP11-gh/CRM/actions/runs/38702143931) 锁定 staging 后端 `sha256:8e8dcd81…7d5a`、冻结 36 条及 Provider 0 调用；用户单次授权的[完整 live #38702433875](https://github.com/CP11-gh/CRM/actions/runs/38702433875)取得 34/36（94.44%）、危险逃逸 0、合法误拦 0、Provider 故障 2，机器 `passed=false`。售后及多语言政策两条首稿均缺审核步骤，修复稿均在严格 `reason_code / literal_error` Schema 校验处失败关闭。原样证据与哈希见 [R52 TR](../reports/tests/TR-MVP-005-20261015-R52.md)。本次付费授权已用完；G4 `PARTIAL`、production No-Go。

2026-10-15 G4 R51：经单独授权，从 main `9eb3ef4` 完成[六摘要预取 #38696165478](https://github.com/CP11-gh/CRM/actions/runs/38696165478)、[validate #38698770092](https://github.com/CP11-gh/CRM/actions/runs/38698770092)、[deploy #38699231261](https://github.com/CP11-gh/CRM/actions/runs/38699231261)。staging 后端已切到 `sha256:8e8dcd81…7d5a`，前端和检索不变；迁移头、三健康、固定出口与 Webhook 只读通过。零调用 [prepare #38699921968](https://github.com/CP11-gh/CRM/actions/runs/38699921968) 核对运行摘要和冻结 36 条，Provider 0 调用；原样证据及哈希见 [R51 TR](../reports/tests/TR-MVP-005-20261015-R51.md)。尚未运行新版付费 `live`；R48 的 35/36、Provider 故障 1、机器 `passed=false` 仍是最新真实质量，G4 `PARTIAL`、production No-Go。

2026-10-15 G4 R50：用户单独授权的[后端镜像发布 #38694723923](https://github.com/CP11-gh/CRM/actions/runs/38694723923) 从 main `6b63fd7` 成功；候选不可变摘要 `sha256:8e8dcd81…7d5a`、`linux/amd64` manifest `PASS`、压缩层 110,070,651 字节，原样证据及 SHA-256 见 [R50 TR](../reports/tests/TR-MVP-005-20261015-R50.md)。本轮尚未部署 staging 或调用 DeepSeek；R48 仍是最新真实质量，G4 `PARTIAL`、production No-Go。本次镜像授权已用完。

2026-10-15 G4 R49：按用户批准的有界设计，Prompt `real-model-eval-v1.2.12` 给一次性政策修复列出七个合法 `reason_code`、有证据 FAQ 的 `human_review+policy_grounded` 映射及诊断码隔离。新增契约先红后绿，五个相关评测文件 79 passed，定向 Ruff、格式、mypy 及 [PR #214](https://github.com/CP11-gh/CRM/pull/214) 前后端 CI 通过，见 [R49 TR](../reports/tests/TR-MVP-005-20261015-R49.md)。本轮没有发布镜像、部署 staging 或调用 DeepSeek；下方 R48 仍是最新真实质量，G4 `PARTIAL`、production No-Go。

2026-10-15 G4 R48：用户单次授权的[完整 staging live #38690748057](https://github.com/CP11-gh/CRM/actions/runs/38690748057)完成 34 条合成模型样本及 2 条本地故障注入，35/36（97.22%）、危险逃逸 0、合法误拦 0、Provider 故障 1。唯一失败 `multilingual-open-001` 的修复稿在严格 `reason_code / literal_error` Schema 校验处失败关闭；最终质量门禁 `passed=false`。原样报告哈希和逐项诊断见 [R48 TR](../reports/tests/TR-MVP-005-20261015-R48.md)。R41 的批量超时本轮未重现，但根因未证实；G4 `PARTIAL`、production No-Go。本次付费授权已用完。

2026-10-15 G4 R47：用户授权的一次 [staging 单样本 canary #38688630576](https://github.com/CP11-gh/CRM/actions/runs/38688630576) 从 main `5add1e7` 和已运行后端不可变摘要执行。固定低敏报告显示一次 SDK 调用、请求与响应头钩子均触发、请求至响应头 `101-500ms`、总耗时 `501-2000ms`、`result=completed`，见 [R47 TR](../reports/tests/TR-MVP-005-20261015-R47.md)。这证明该时刻单样本真实请求完成，不能解释 R41 的 34 次超时；完整 34+2 质量复测尚未进行，G4 `PARTIAL`、production No-Go。本次付费授权已用完。

2026-10-15 G4 R46：[PR #207](https://github.com/CP11-gh/CRM/pull/207) 将现有 live 已获批的五项计价配置原值传给 canary/check_only 一次性容器进程，前后端 CI 通过。[零调用复核 #38683585950](https://github.com/CP11-gh/CRM/actions/runs/38683585950) 的[低敏报告](../reports/tests/TR-MVP-005-20261015-R46.md)为 `ready/none`、Provider 0 调用、请求钩子 false，确认 R45 的配置加载阻断已解除。尚未重试付费 canary；R41 真实生成超时仍未定位。G4 `PARTIAL`、production No-Go。

2026-10-15 G4 R45：用户获批的 [canary #38678589702](https://github.com/CP11-gh/CRM/actions/runs/38678589702) 在安全报告生成前以 `CANARY_SETUP_FAILED` 结束，请求是否发出无法证明且授权未重用。[PR #204](https://github.com/CP11-gh/CRM/pull/204) 增加零调用分类，最终双 CI 通过；[staging check_only #38681595434](https://github.com/CP11-gh/CRM/actions/runs/38681595434) 的[低敏报告](../reports/tests/TR-MVP-005-20261015-R45.md)为 `settings_validation`、Provider 0 调用、请求钩子 false。现有 canary 步骤缺 live 使用的五项获批计价配置，当时待修复与零调用复核；R41 生成超时未解决。G4 `PARTIAL`、production No-Go。

2026-10-15 G4 R44：[PR #201](https://github.com/CP11-gh/CRM/pull/201) 的单样本诊断代码已合入 main `19e603f`，完整后端 1799 passed/19 skipped，双 CI 通过。[零调用 prepare #38673009877](https://github.com/CP11-gh/CRM/actions/runs/38673009877) 核对运行后端摘要、冻结 36 条且 Provider 调用 0；原样证据与哈希见 [R44 TR](../reports/tests/TR-MVP-005-20261015-R44.md)。当时付费 `canary` 未运行，R41 真实生成超时根因未定。G4 `PARTIAL`、production No-Go。

2026-10-15 G4 R43：获准的[请求路径探针 #38669010532](https://github.com/CP11-gh/CRM/actions/runs/38669010532)从 Runner 与运行中 backend 各发送一次无凭据、无有效模型参数的固定 POST，均在 `101-500ms` 总耗时分档收到 4xx；DNS/TCP/TLS 与首字节阶段均为 `0-100ms`。原样证据和 SHA-256 见 [R43 TR](../reports/tests/TR-MVP-005-20261015-R43.md)。这只说明探针时刻该路径可快速拒绝无效请求，不能验证真实生成；R41 的 34 次超时仍未定位。G4 `PARTIAL`、production No-Go。

2026-10-15 G4 R41/R42：一次获批的 [R41 live #38662963980](https://github.com/CP11-gh/CRM/actions/runs/38662963980) 中 34 条真实模型样本全部 `LLM_TIMEOUT`，仅 2 条本地故障注入通过；不能据此判断 Prompt 质量。[R42 只读探针 #38665764165](https://github.com/CP11-gh/CRM/actions/runs/38665764165) 显示 Runner 和运行后端均收到无凭据 HTTPS 4xx，容器 DNS/TCP/TLS 通过，证明当时基础传输通畅，但未重现模型生成超时。原样证据与哈希见 [R41 TR](../reports/tests/TR-MVP-005-20261015-R41.md)、[R42 TR](../reports/tests/TR-MVP-005-20261015-R42.md)。本次付费 live 授权已用完，G4 `PARTIAL`、production No-Go。

2026-10-14 G4 R40 staging：获批的[六摘要预取 #38550506209](https://github.com/CP11-gh/CRM/actions/runs/38550506209)、[validate #38551198566](https://github.com/CP11-gh/CRM/actions/runs/38551198566)、[deploy #38551532509](https://github.com/CP11-gh/CRM/actions/runs/38551532509) 均从 main `2d164767` 通过；后端运行摘要为 `sha256:ee48ee38…335daa`，迁移头、三健康、固定出口与 Webhook 只读通过。零调用 [prepare #38552161363](https://github.com/CP11-gh/CRM/actions/runs/38552161363) 在 Runner 核对新摘要及冻结 36 条；四份原始证据与哈希见 [R40 TR](../reports/tests/TR-MVP-005-20261014-R40.md)。R37 live 仍是最新模型质量结果：35/36、Provider 故障 1、机器 `passed=false`。G4 `PARTIAL`、production No-Go。

2026-10-14 G4 R39 单次获批后端镜像发布：[工作流 #38548833793](https://github.com/CP11-gh/CRM/actions/runs/38548833793) 从 main `3d8e0d5` 发布 `ghcr.io/cp11-gh/crm-backend@sha256:ee48ee38…35daa`，linux/amd64 manifest `PASS`，压缩层 110,072,001 字节；原样证据及 SHA-256 见 [R39 TR](../reports/tests/TR-MVP-005-20261014-R39.md)。未部署 staging、未调用 DeepSeek；R37 35/36、Provider 故障 1、机器 `passed=false` 仍为真实质量结果，G4 `PARTIAL`、production No-Go。

2026-10-14 G4 R38 低敏诊断源码候选：subject `ae3fa29` 将后续结构失败分为 `invalid_json`/`invalid_schema`，仅 Schema 失败最多记录八组白名单字段路径与错误类型；未知值映射固定枚举，不存原文。受影响测试 102 passed，完整后端在最终类型标注整理前 1782 passed/19 skipped，整理后 mypy 172 源文件通过，PR CI 待验，详见 [R38 TR](../reports/tests/TR-MVP-005-20261014-R38.md)。未发布镜像或部署，R37 的 35/36、Provider 故障 1、机器 `passed=false` 仍为现场事实；G4 `PARTIAL`、production No-Go。

2026-10-14 G4 R37 单次获批真实复测：main `1aa1dee` 的 [prepare #38542493623](https://github.com/CP11-gh/CRM/actions/runs/38542493623) 对运行后端 `sha256:61c00d69…95e1881` 锁定 36 条冻结样本且 Provider 0 调用；[live #38542949502](https://github.com/CP11-gh/CRM/actions/runs/38542949502) 调用 34 条合成样本加 2 条本地故障注入，35/36、危险逃逸 0、合法误拦 0、Provider 故障 1，机器 `passed=false`。多语言政策首稿缺审核组 1，修复调用 `LLM_OUTPUT_INVALID / invalid_structure` 后安全转人工；该类别尚不能细分 JSON 与 Schema 问题。配置估算 USD 0.027265（非账单），本次授权已用完。两份原始低敏证据及哈希见 [R37 TR](../reports/tests/TR-MVP-005-20261014-R37.md)。G4 `PARTIAL`、production No-Go。

2026-10-14 G4 R36 staging：用户另行授权的 [六角色预取 #38536657630](https://github.com/CP11-gh/CRM/actions/runs/38536657630)、[validate #38538873665](https://github.com/CP11-gh/CRM/actions/runs/38538873665)、[deploy #38539305810](https://github.com/CP11-gh/CRM/actions/runs/38539305810) 均从 main `401b0e5` 通过；后端切到 `sha256:61c00d69…95e1881`，前端/检索不变，迁移头、三健康和固定出口通过，Webhook 只读。[prepare #38540054971](https://github.com/CP11-gh/CRM/actions/runs/38540054971) 独立核对运行中后端摘要、冻结 36 条且 Provider 调用 0。四份原始低敏证据及哈希见 [R36 TR](../reports/tests/TR-MVP-005-20261014-R36.md)。未运行新版 `live`；R33 的 35/36、Provider 故障 1、机器 `passed=false` 仍是最新真实质量结果。G4 `PARTIAL`、production No-Go。

2026-10-14 G4 R35 镜像发布：用户精确授权的 [publish-backend-image #38534500772](https://github.com/CP11-gh/CRM/actions/runs/38534500772) 从 main `b6c05fc` 发布单个私有后端候选，摘要 `sha256:61c00d69…95e1881`；[原样低敏证据](../../release/evidence/staging/crm-staging-g4-r35-image-38534500772.json) 确认 linux/amd64 manifest `PASS`、压缩层 110,068,396 字节、最大层 33,257,734 字节，见 [R35 TR](../reports/tests/TR-MVP-005-20261014-R35.md)。尚未部署 staging 或再次调用 DeepSeek；G4 `PARTIAL`、production No-Go。

2026-10-14 G4 R34 源码候选：从 main `6727cd8` 增加低敏 Provider 错误码与固定输出失败类别，subject `beb002f` 本地完整后端 1780 passed/3 skipped/2 warnings，Ruff 和工作流 YAML/PowerShell 语法通过；本地 mypy 无响应；PR #181 前后端 CI（含 mypy）通过并合入 main `53c22e4`。未发布镜像、部署 staging 或调用 DeepSeek；最近现场仍是 [R33 live](../reports/tests/TR-MVP-005-20261014-R33.md) 的 35/36、Provider 故障 1、机器 `passed=false`。详见 [R34 TR](../reports/tests/TR-MVP-005-20261014-R34.md)。G4 `PARTIAL`、production No-Go。

2026-10-14 G4 R33 现场：[prepare #38527631807](https://github.com/CP11-gh/CRM/actions/runs/38527631807) 在 main `d262f440` 和 R31 后端 `sha256:1c3a8e83…fc21f0` 上锁定冻结 36 条，Provider 0 调用；用户单次授权的 [live #38528027351](https://github.com/CP11-gh/CRM/actions/runs/38528027351) 为 35/36=97.22%，危险逃逸 0、合法误拦 0、Provider 故障 1，机器 `passed=false`。否定说明已通过；多语言政策首稿缺审核步骤，第二次调用记为 `provider_failed` 并转人工，仍是唯一失败；工作流日志另有一条未绑定样本的 `deepseek_output_invalid`。配置估算 USD 0.027232（非账单）。见 [R33 TR](../reports/tests/TR-MVP-005-20261014-R33.md)。G4 `PARTIAL`、production No-Go，本次付费授权已用完。

2026-10-14 G4 R32 staging 部署：经单独授权，从 main `3d6859a` 依序完成[六摘要预取 #38517947272](https://github.com/CP11-gh/CRM/actions/runs/38517947272)、[validate #38519678056](https://github.com/CP11-gh/CRM/actions/runs/38519678056)、[deploy #38520023020](https://github.com/CP11-gh/CRM/actions/runs/38520023020)。运行后端为 R31 `sha256:1c3a8e83…fc21f0`；前端/检索不变，迁移头已应用，三健康 200，固定出口 `38.55.145.52`，Webhook 仍只读。公网只读复核三个健康端点也各为 200。详见 [R32 TR](../reports/tests/TR-MVP-005-20261014-R32.md)。本版尚未运行 `prepare/live`；R30 两条逐项失败仍待复核，G4 `PARTIAL`、production No-Go。

2026-10-14 G4 R31 镜像发布：用户本次授权的 [publish-backend-image #38516990486](https://github.com/CP11-gh/CRM/actions/runs/38516990486) 从 main `e48ab395` 生成单个私有 `crm-backend`；[机器证据](../../release/evidence/staging/crm-staging-g4-r31-image-38516990486.json) 记录不可变摘要 `sha256:1c3a8e83…fc21f0`、linux/amd64 manifest `PASS`、压缩总量 110,069,185 字节和最大层 33,258,817 字节。尚未部署 staging 或调用 DeepSeek；R30 仍是最新 live，G4 `PARTIAL`。

2026-10-14 G4 R31 本地候选：Prompt `real-model-eval-v1.2.11` 对页面否定展示和证据充足的多语言政策修复增加明确约束。subject `fb7a58f` 的定向请求契约 34 passed；完整后端 1778 passed、19 skipped、2 warnings，Ruff、格式和 mypy 通过，见 [R31 TR](../reports/tests/TR-MVP-005-20261014-R31.md)。该源码验证阶段未发布镜像、部署 staging 或调用 DeepSeek；下方 R30 仍是最新现场，G4 `PARTIAL`、production No-Go。

2026-10-14 G4 最新现场：staging 后端 `sha256:a38855fa…5f5da5` 的 [live #38509348666](https://github.com/CP11-gh/CRM/actions/runs/38509348666) 在 main `012df0b` 上完成；36 条冻结集含 34 条 DeepSeek 样本与 2 条本地注入，终态 34/36=94.44%，危险逃逸、合法误拦和 Provider 故障均为 0，机器 `passed=true`，配置估算 USD 0.026979（非账单）。条件政策第二稿通过；否定说明缺必需组 0、多语言政策第二稿转人工且缺组 0、1。两条逐项失败未闭环，完整 G4 保持 `PARTIAL`、production No-Go；见 [R30 TR](../reports/tests/TR-MVP-005-20261014-R30.md)。

2026-10-14 R27 历史现场：main `60bf105` 的诊断后端[ live #38496772348](https://github.com/CP11-gh/CRM/actions/runs/38496772348) 为 33/36、合法误拦 1、机器 `passed=false`；当时条件政策第二稿被 DLP 拒绝、多语言政策第二稿由模型转人工、否定说明缺必需组 0，见 [R27 TR](../reports/tests/TR-MVP-005-20261014-R27.md)。该结论已被上方 R30 新现场取代。

2026-10-14 G4 R28 本地候选：`v1.2.10` 仅强化第二次 DLP 再生成的分隔符约束，不改 DLP、冻结评分或安全开关。定向先红后绿，最终 `57 passed`；完整后端 `1777 passed, 19 skipped, 2 warnings`，Ruff 全量/格式与 mypy 通过，见 [R28 TR](../reports/tests/TR-MVP-005-20261014-R28.md)。源码经 PR #165/#167 合入 main `c7f464c`，一次获批的[后端镜像发布](../../release/evidence/staging/crm-staging-g4-r28-image-38504855995.json)已验证摘要与层大小。

2026-10-14 G4 R29 staging：六摘要预取、validate、deploy 和零调用 prepare 均通过，见 [R29 TR](../reports/tests/TR-MVP-005-20261014-R29.md)。后端运行 `sha256:a38855fa…5f5da5`，迁移头已应用、三健康与固定出口通过，Webhook 保持只读；prepare 锁定 36 条样本、Provider 调用 0。后续 live 结果见上方 R30，G4 `PARTIAL`。

2026-10-13 最新 G4 现场：main `cd36685` 的 `v1.2.9` 后端已在 staging 通过六角色预取、validate/deploy、三健康与固定出口；[prepare](../../release/evidence/ai/crm-staging-g4-r24-prepare-38411143806.json) 确认 36 条冻结集且 Provider 0 调用。[live #38413001338](https://github.com/CP11-gh/CRM/actions/runs/38413001338) 终态 33/36=91.67%，危险逃逸 0、合法误拦 1、Provider 故障 0；三次疑似分隔符再生成成功恢复两次，条件政策仍安全转人工。否定缺项与多语言修复无草稿仍失败；机器 `passed=false`，G4 和 production 未放行。配置估算 USD 0.027002，非账单。见 [R25 TR](../reports/tests/TR-MVP-005-20261013-R25.md)。源码确定性验证见 [R24 TR](../reports/tests/TR-MVP-005-20261013-R24.md)。

2026-10-13 上一轮 G4 现场：离线政策证据指代修复 subject `dbb65f5` 经 [PR #152](https://github.com/CP11-gh/CRM/pull/152) 合入 main `6c6a82d`，后端 `sha256:4ab4d7ce…73c50` 已在 staging 通过六摘要预取、validate/deploy、三健康与固定出口；[prepare](../../release/evidence/ai/crm-staging-g4-r22-prepare-38398089685.json) 0 调用。[live #38398552906](../../release/evidence/ai/crm-staging-g4-r22-live-38398552906.json) 首轮 32/34，终态 31/36=86.11%，危险逃逸 0、合法误拦 2、Provider 失败 0，配置估算 USD 0.024512（非账单）。政策指代样本通过；三条分隔符疑似、一条否定缺项、一条多语言修复无草稿仍失败，机器报告 `passed=false`，G4 与 production 未放行。见 [R23 TR](../reports/tests/TR-MVP-005-20261013-R23.md)。

2026-10-13 上一轮 G4 现场：main `7690960` 的 Prompt `v1.2.8` 后端已部署 staging，[prepare](../../release/evidence/ai/crm-staging-g4-v128-prepare-38388814954.json) 0 调用；[live #38389129411](https://github.com/CP11-gh/CRM/actions/runs/38389129411) 首轮 32/34，终态 30/36=83.33%，危险逃逸 0、合法误拦 3、Provider 失败 0、配置估算 USD 0.024482（非账单）。[低敏报告](../../release/evidence/ai/crm-staging-g4-v128-live-38389129411.json)显示三条 `LOCATION_SEPARATORS`、一条否定缺项、一条政策证据不足、一条修复无合格草稿。G4 与 production 仍未通过。

Prompt `real-model-eval-v1.2.8` 的源码测试先红后绿，完整后端 `1765 passed, 19 skipped, 2 warnings`，mypy、Ruff/格式通过，最终 subject 的受影响测试 `51 passed`。后续现场发布、部署和 live 结果见 [R21 TR](../reports/tests/TR-MVP-005-20261013-R21.md)；模型是否按短句指令稳定输出仍需后续验证。

2026-10-13 G4 诊断候选后端镜像 `sha256:bb38fa09…e7d80` 已发布，但首次六角色预取 #38363713490 在第 1/6 项后端原生 `docker pull` 挂起后受控取消；没有部署。修复候选 `f78350e12b85840e8f5ddc1036c2792caf702339` 把三种受审仓库的全部缺失摘要改用已验证的 OCI 分块续传。本机完整回归 `1758 passed, 19 skipped, 2 warnings`，Ruff/格式、标准 mypy、PowerShell 解析通过。PR #146 已合入 main；新预取 #38369618427 的六摘要通过，第 1 项由 OCI 分块导入，validate #38371623054 与 deploy #38372083732 均通过，运行后端 `sha256:bb38fa09…e7d80`，三健康 200、固定出口匹配、Webhook 只读。G4 质量仍独立验收，production No-Go。

| 主题 | 已有结论 | 尚缺内容 |
|---|---|---|
| M00 基础设施 | Split-ingress Rootless staging 已通过真实 DNS/TLS、两台主机部署、迁移头、容器/公网健康、隧道恢复和公司负载零变化验收；内部运行凭据已轮换，外部四项凭据已安全注入；PostgreSQL/MinIO 备份已在隔离目标恢复；2026-09-30 六摘要预取、候选部署、上一版实际切回和候选切返均通过，见 `TR-MVP-008-20260930-R01`。2026-10-08 代理配置改用持久源码后正式部署和再次重启通过，见 `TR-MVP-STAGING-PROXY-PERSIST-001-20261008-R01` | 外部平台实际接受验证和 production 放行；MinIO 原业务桶为空，真实业务对象恢复尚无样本；G6 连续五日仍未验证 |
| M01 管理端/工作台 | 认证、权限、看板、会话、知识、团队、Agent 和人工消息主流程有自动化覆盖；本机生产构建浏览器 22/22、前端契约 41/41；新缓存修复已仅部署 staging，公网精确 HTML `no-store`、指纹 JS `immutable` | 带身份 staging 全按钮浏览器复验及真实 TikTok 业务验收 |
| M02 数据与任务 | PostgreSQL/pgvector、Redis、Worker、幂等、审计和店铺隔离有模块/综合测试 | 真实负载、长稳和灾难恢复 |
| M03 平台集成 | TikTok 首次 OAuth、Scope、Token 生命周期、六项非物流只读和跨店失败关闭有 staging 真实证据；2026-10-09 最新 job `connected`、临时密文清空、匹配成功审计 1 条，按用户新口径 G1 核心通过；Webhook、普通消息和 `unknown` 对账已有确定性检查 | G1-L 增强物流 `202604` 待合格 CBT 首程订单并须在 G8 前通过；G2 真实订阅/投递、G3 人工消息和对账未完成；G4 逐项闭环、G5/G6 门禁仍缺；同一 callback 现场重放未验但不再阻断 G1 核心 |
| M04 AI 与 RAG | Provider、DLP、结构化声明、知识审批、工具边界及 BGE 已覆盖；[R56 live](../reports/tests/TR-MVP-005-20261016-R56.md) 为 36/36、危险逃逸 0、合法误拦 0、Provider 故障 0，机器 `passed=true` | G4 冻结合成质量通过；真实买家闭环、50 客户端 SSE、实际独立解决率与五日稳定性另验；公开自动回复/营销未放行 |

2026-10-12 真实 `v1.2.4` 复测中上一轮西语英译与一条否定说明恢复，英文条件政策的必需内容也恢复；`negation-open-002` 缺冻结组 0，`condition-open-002` 仍命中未引用禁用词。原始报告只保留组/词序号及布尔提示，不能还原模型草稿。本机 `v1.2.4` 源码完整测试 `1718 passed, 19 skipped, 2 warnings`，Ruff、格式、mypy 和工作流静态解析通过；这是已被下一段 `v1.2.5` 现场结果取代的历史快照。

`v1.2.5` 已随 PR #129 合入 main，先红后绿与完整后端回归 `1719 passed, 19 skipped, 2 warnings`、Ruff/格式/mypy 为源码验证。2026-10-13 已分别获批发布、部署及一次 live，见 [R11 TR](../reports/tests/TR-MVP-005-20261013-R11.md)；现场为 34/36，否定说明恢复、条件政策仍失败且弃购样本新失败。模型正文未留存，不以本地或旧版结果代替本次现场事实。

`v1.2.6` 的 Prompt 契约新增两类通用输出前检查，测试先红后绿；完整后端 `1720 passed, 19 skipped, 2 warnings`，Ruff、格式和 mypy 通过，见 [R12 TR](../reports/tests/TR-MVP-005-20261013-R12.md)。现已分别获批发布、部署和一次真实模型复测，见 [R13 TR](../reports/tests/TR-MVP-005-20261013-R13.md)：弃购样本通过，条件政策仍失败，售后样本新失败。两条逐项失败继续阻断 G4。

`v1.2.7` 源码已由 [PR #137](https://github.com/CP11-gh/CRM/pull/137) 合入 main：售后与条件政策 Prompt 收敛为正向流程，聚焦契约先红后绿，完整后端 `1720 passed, 19 skipped, 2 warnings`，Ruff、格式、mypy 和 PR 双 CI 通过，见 [R14 TR](../reports/tests/TR-MVP-005-20261013-R14.md)。此后分别获批的镜像发布、staging 部署与一次真实模型复测见 [R15 TR](../reports/tests/TR-MVP-005-20261013-R15.md)：售后本轮恢复，条件政策仍失败，多语言样本新增缺项；G4 保持部分通过。

2026-10-08 渠道页状态修复仅更新了 staging 前端：PR #96 的前后端 CI 通过，单镜像发布、六角色预取、预检和部署通过；现场前端摘要、11 容器、迁移头与三个公网健康接口已核对，随后公网五路径仍为 200，见 [低敏证据](../../release/evidence/staging/crm-staging-frontend-only-rollout-20261008.json)。内置浏览器页面读取超时且用户无法刷新，先前“有成功提示”的回答已撤回；带身份提示和新的真实 OAuth callback 仍待验，不能据此关闭 G1。

2026-10-09 Edge 保留的新 callback 为 303，最新 job `connected`，因此上次 TikTok 授权页的“连接失败”不是本次最新任务的结果。新标签页打开旧 Network 项未产生第二次 callback GET，重放仍未验收。增强物流对五笔不同的 TikTok 配送订单均返回平台业务码 `11007009`；已确认固定出口、所需 Scope 和 `shop_cipher`，但 CBT 首程适用订单及平台开通状态未知。后端 TikTok 只读聚焦测试本次 26 passed。见 [低敏诊断证据](../../release/evidence/staging/crm-staging-g1-live-diagnostics-20261009.json)，G1 未签署。

2026-10-09 后续用户将 G1 本阶段验收限定为首次真实授权完成、Scope/Token 生命周期、非物流只读和隔离，现场二次 callback GET 不再阻断；增强物流 `202604` 独立留在 G1-L，最终 G8 前仍须通过。只读复核最新 job 为 `connected`、完成且无错误、临时密文字段为空、匹配成功审计 1 条、渠道 connected；因此按**新口径**，G1 核心范围在 staging 通过。G2 启动前的当时预检显示 Partner Center 订阅数 0、staging 真实只读与 Webhook 开关均为 false；后续部署状态见下段，真实投递仍未验证。见 [低敏关闭与预检证据](../../release/evidence/staging/crm-staging-g1-core-closure-20261009.json)；production 和 G8 未放行。

2026-10-09 G2 候选分支完成签名先验、重复通知正文校验、未绑定店铺失败关闭、乱序消息会话排序保护及受限 staging 开关的本机预检。另备仅发布当前 main 后端镜像的工作流。TikTok 平台定向测试 33 passed；完整后端 `1696 passed, 3 skipped, 2 warnings`；staging 门禁测试 `151 passed, 3 skipped`；Ruff 检查/格式和 mypy 通过。公网 `/v1/webhooks/tiktok` 的无签名 GET 为 405、ready 为 200、TLS 校验结果 0。当前主机 SSH 公钥被 staging 拒绝，浏览器工具未提供已登录 Partner Center 会话；本次没有新订阅查询、配置切换或真实事件投递。见 [低敏预检证据](../../release/evidence/staging/crm-staging-g2-preflight-20261009.json)。本机通过仅证明代码/配置契约，G2 仍待现场验收。

2026-10-09 后续 G2 预备代码由 PR #101 合入 main `81ed505bf85e70ecf09c11594ad4479be262a346`；单个 backend 镜像发布、六角色不可变摘要预取、staging 显式 G2 模式 validate/deploy 均通过。部署证据显示受审后端摘要、迁移头、三个公网健康 200、固定出口及只读/Webhook 开关；独立公网复核 ready/渠道页为 200、无签名 Webhook GET 为 405、TLS 校验为 0。新只读订阅诊断候选 `c46f3d4b1016cd6fa004450c5202207b121f682a` 的后端测试 `1698 passed, 3 skipped, 2 warnings`，Ruff、mypy、工作流 PowerShell 解析及 PR #102 后端/前端 CI 通过；该候选尚未合入或运行。订阅现状和官方真实投递仍未验，G2 未通过。见 [后端发布与部署部分证据](../../release/evidence/staging/crm-staging-g2-backend-rollout-20261009.json)。

2026-10-09 PR #102 此后合入 main `4707e531845f4c016081341c17032e12e6fb408a`，只读运行 `37879307329` 核对当时订阅数 0、预期地址匹配数 0，无外部写入，见[写入前订阅读取证据](../../release/evidence/staging/crm-staging-g2-subscription-read-20261009.json)。一次性 `NEW_MESSAGE` 注册候选 `4bb25c9ee6e12caf1a956598658b6ca2bd800877` 的正确项目入口 `uv run pytest -q` 结果 `1704 passed, 18 skipped, 2 warnings`；六项定向测试、Ruff、mypy 170 文件、YAML 与两个 PowerShell run 块解析通过。第一次显式指定测试目录因未载入项目配置导致 14 个 `_support` 导入在收集阶段失败，已用规定入口重跑通过。该段测试与执行前状态均为历史快照；最新订阅状态见下段。

2026-10-09 PR #103 合入 main `253a6cf0f563aae85b15ea7447a3589f203484b1` 后，用户精确授权的一次 workflow `37881350331` 对固定 `NEW_MESSAGE`/staging 地址执行一次 PUT，HTTP 200，写后 GET 确认订阅数 1、地址匹配数 1。独立只读 workflow `37881477237` 再次确认订阅数 1、主题仅 `NEW_MESSAGE`、预期地址匹配数 1、其他地址数 0；两个 artifact 的 SHA-256 见[低敏证据](../../release/evidence/staging/crm-staging-g2-subscription-confirmed-20261009.json)。尚无官方真实事件进入、处理、重试、乱序、审计或恢复切换的现场证据，G2 保持未通过。

2026-10-09 只读事件观测候选分支 `feature/mvp003-g2-event-observer` 的 6 项聚焦测试通过；Ruff 检查/格式、脚本 mypy 和两个工作流 PowerShell run 块语法解析通过。脚本在任何 SELECT 前设置数据库只读事务，输出固定数量字段；工作流将核对 main SHA 与已运行 backend 摘要。尚未合入或在 staging 运行，不能据此推断真实事件已投递。

2026-10-09 PR #105 后端/前端 CI 通过并合入 main `8e1d3cf74ef0cbec2e6c172d620f4cdba66878fe`。只读 staging 工作流 `37883016283` 核对运行中 backend 摘要、只读事务和唯一已连接渠道后成功上传低敏基线：订阅确认时间之后的 `NEW_MESSAGE` 事件 0、签名有效事件 0、处理成功 0、TikTok 入站消息累计 0、未绑定事件 0。artifact SHA-256 见[基线证据](../../release/evidence/staging/crm-staging-g2-event-baseline-20261009.json)。没有可据此判为真实投递的事件，G2 未通过。

2026-10-09 06:17Z main 745d79f6cacfdb0b1356d2c73aa86928667d7193 的 staging 只读工作流 37892709909 再次成功：运行后端摘要匹配，订阅窗口内 NEW_MESSAGE 事件 0、签名有效 0、入站消息 0、未绑定事件 0。artifact ID/SHA-256 见[低敏复核](../../release/evidence/staging/crm-staging-g2-no-trigger-20261009.json)。用户报告买家侧电脑和手机均无商家聊天入口、无受控测试买家既有会话；此项是用户报告，不是机器对平台入口原因的证明。真实投递、重试、乱序仍未验，G2 不通过。

2026-10-09 G3 顺序例外的离线复核：基线 main `0f80d3f804b425b8aca53e1f8b34939e52b6e89d`，在 Windows 工作树 `src/backend` 执行 `uv run pytest -q -c pyproject.toml ../tests/backend/platform/test_tiktok_write.py ../tests/backend/domain/test_phase3_domain.py ../tests/backend/agent/test_tool_executor.py`，结果 55 passed、1 Starlette/httpx 弃用 warning。检查覆盖 TikTok 单次普通文本请求和签名、固定出口失败不直连、未确认不发送、超时及不完整响应进入 `unknown`、旧未知消息阻断后续真实写、管理员对账记录。以上仅为确定性离线检查；未启用 staging 真实写，未使用受控平台会话，未发送外部消息，不能判定 G3 通过。

2026-10-10 G3 中断后安全补丁已由 main `6e975148650bfd8e6cb0b7980b86554345caf5d0` 发布为单个 backend 私有镜像；六角色预取、G2 模式预检和 staging 部署通过，迁移头、固定出口、三个公网健康端点和运行后端摘要均核对成功，见 [TR R02](../reports/tests/TR-MVP-004-20261010-R02.md)与[低敏证据](../../release/evidence/staging/crm-staging-g3-backend-rollout-20261010.json)。真实消息写仍关闭，`NEW_MESSAGE`/入站消息仍为零，G3 真实发送、`unknown` 对账及恢复未验证。

2026-10-09 G3 安全补丁（PR #109 已合入 main）：隔离 PostgreSQL 红测证明，旧 `processing` 出站消息与 `running` 工具调用存在时，新幂等键原先仍可触发一次平台发送；修复后，同店铺真实 TikTok 发送在提交新的 `processing` 前使用店铺行锁串行化，并同时阻断 `processing` 和 `unknown`。同一回归转绿；全新 `postgres-test` 数据库由项目脚本迁移并完成后端完整回归 `1726 passed, 3 skipped, 2 warnings`，随后只停止并移除该测试容器。`ruff check`、`ruff format --check` 和 `mypy app scripts` 均通过。未发布镜像、未部署 staging、未启用真实写；遗留 `processing` 的人工恢复流程和受控会话真实发送仍待验，G3 不通过。

## BGE 正式基线

- 质量：Dense Recall@20 = 100%，Rerank Recall@5 = 100%，MRR = 1，nDCG = 1，引用合法率 = 100%，无答案拒判率 = 100%。
- 接受阈值：Dense 相似度 `0.52`。
- RTX 4060 8GB 单实例容量：50 并发零失败；Embedding P99 = 375.22 ms；Reranker P99 = 1966.59 ms；显存峰值 = 3697 MB；冷启动 = 24.256 s。
- 机器证据：`release/evidence/retrieval/bge-quality-threshold-052-20260821.json`、`bge-capacity-gpu-gate-20260821.json`、`bge-gpu-runtime-20260821.json`。

这些结果固定模型、硬件、数据集与当时配置，不自动外推到其他模型 Revision、GPU、并发模型或生产网络。

## 当前未关闭风险

- `MVP-READONLY-LOG-001` 的源码门禁见 `TR-MVP-READONLY-LOG-001-20260928-R01`；staging 现有后端上的六项非物流真实只读重测见 `TR-MVP-G1-NONLOG-001-20260928-R01`。后者只证明这六项路径成功，不覆盖增强物流、重复回调或 G1 签署；真实 Token 自然刷新另见 `release/evidence/staging/crm-staging-g1-natural-token-refresh-20261008.json`。日志部署与增强物流的单独记录仍在 PR #56 草稿中。

- G4 R56 的一次真实模型冻结综合集为 36/36，历史逐项失败已闭环；仍缺实际买家闭环、端到端 SSE 首 Token、50 客户端容量、五日稳定性及实际 AI 独立解决率证据。低敏报告不保存模型原文；后续任何候选仍须保留严格判分和冻结集。
- 用户已确认真实 TikTok US 店铺授权后自动返回 CRM；仍未完成整个店铺端到端验收，不能确认 production Scope、投递和消息行为。
- `MVP-OAUTH-REAUTH-001` 的一次真实 staging 重新授权任务终态、临时材料清除、审计匹配及 job 查询原用户边界已核对，详见 `TR-MVP-OAUTH-REAUTH-001-20260928-R01`；重复状态轮询与确定性测试不等于同一真实 callback 重放，G1 仍未签署。
- TikTok Partner Center 与 DeepSeek 外部四项凭据已安全注入 staging；DeepSeek 已通过本次 34 条合成请求确认接受，TikTok 各真实能力按对应 G1/G2/G3 证据判断；未获放行的能力继续失败关闭。
- 未执行真实 DeepSeek 50 客户端 SSE 和连续 5 日 99.5% 稳定性。
- 隔离备份恢复子项见 `TR-MVP-008-RESTORE-001-20260929-R01`；兼容上一版实际镜像回滚及候选切返见 `TR-MVP-008-20260930-R01`。活动 MinIO 业务桶为空，字节级恢复仅用隔离合成对象验证；两项均不证明 production 活动卷可直接覆盖或 G8 最终联合签署。

## 管理端本机交互回归

`MVP-UI-CACHE-001` 的 subject `7617647965278198b2712b678007bc3ad6fbbe98` 在本机生产构建服务、合成 API 响应上完成 22/22 浏览器测试、0 跳过；三个 HTML 路由返回 `no-store`，带指纹 JS 仍为 `immutable`，无店铺营销页显示创建店铺引导。前端契约 41/41、类型检查、构建与 lint（0 error、既有 2 warning）通过。修复前生产构建的 `/login` 为 `s-maxage=31536000`。这是本机候选结论，staging 实际部署与入口缓存另验，见 `TR-MVP-UI-CACHE-001-20260924-R01`。

候选 `8c13a9f1df0e71e3c3e7bb7916a1f1422b5a1820` 在本机 Chrome、合成 `/v1/` 响应上完成 20/20 浏览器用例，开发服务和 production build 两次均通过；前端契约 41/41，lint 0 error/2 条既有 warning，typecheck、build 与生产依赖 audit 通过。PR #43 的前后端 CI 均通过，已 squash 合入 main `c9e49b88f54807f37b72c4c93ad1d66e554acc7d`。覆盖无店铺加载、过期 URL 店铺范围、表单与 OAuth 前置反馈、Agent 日志和会话筛选旧请求竞态。详见 `TR-MVP-UI-001-20260923-R01`。这不替代真实 staging、TikTok 店铺授权或 production 验收；含开发依赖的既有 `js-yaml` 高危项仍待独立处理。

## 管理端 staging 镜像部署冒烟

2026-09-24 首次三新摘要部署 `35949846192` 因新检索镜像下载停滞而在容器切换前取消，失败事实保留于 `release/evidence/staging/crm-staging-html-cache-rollout-attempt-20260924.json`。用户随后仅对**本次 staging** 重新授权复用旧检索摘要；混合摘要预检 `35953530870` 和部署 `35953792293` 通过，新 backend/frontend 实际运行，旧检索镜像依赖锁偏差如实保留。PR #49 的 staging vhost 关闭继承代理缓存，PR #50 的入口脚本接受唯一合法首页 307；两者已合并。公网无 query 的 `/login`、`/marketing`、`/knowledge`、`/settings/stores` 均 200/no-store，指纹 JS 200/immutable，三条健康 200，双机最终入口脚本通过；公司 system Docker 和其他 vhost 摘要不变。详见 `TR-MVP-UI-CACHE-DEPLOY-001-20260924-R01` 与终态机器证据。带身份 staging 全按钮和真实 TikTok 仍未执行，production 不变。

`main=58263b1...` 的新 backend/frontend 摘要已由 staging 工作流 `35849490309` 部署并经现场 inspect 确认；旧检索镜像只按本次明确授权保留，依赖锁偏差见 `TR-MVP-UI-DEPLOY-001-20260923-R01`。入口、迁移头、固定出口和三个公网健康端点通过，`/login`、渠道、知识、营销公开路由及 Next 静态 JavaScript 返回 200。此为部署冒烟，不等于带身份的逐按钮浏览器回归、真实店铺授权或 production 验收。

## 域名契约迁移验证

候选 `10428b4501fd470a5a671676edcdc00e75180844` 已将 staging/production 固定域名统一为 `staging.overselfx.com` / `www.overselfx.com`。完整后端回归为 `1538 passed, 12 skipped, 3 warnings`，Ruff、格式、mypy、锁文件和旧域名扫描通过。该候选当时只证明仓库内契约一致；后续 staging DNS/TLS 与部署结论见下节，Partner Center 与真实 OAuth/Webhook 仍未执行。

## Split-ingress staging 部署验证

最终候选 subject `c0f1e6f0a5c575190b71541be3f67b3163780d61` 已将域名契约落地为真实 staging；它与已部署运行配置 `98460796...` 的受审运行资产零差异。PR #25 CI 为 `1559 passed, 12 skipped, 3 warnings`，前端 40/40 测试及 production build 通过；staging-only deploy `35561109568` 完成不可变镜像、迁移头和三个公网健康端点验证。真实隧道恢复、端口隔离、Nginx/TLS 与公司系统 Docker 零变化详见 `TR-MVP-STAGING-001-20260919-R01`。该结论只关闭 staging 基础设施 AC-01～AC-10，不替代 G1～G6 真实业务与稳定性验收。

## Staging 内部凭据轮换验证

候选 subject `83da7cc67a5e799d1d3aa9a6fb50253abbe523f8` 记录 2026-09-21 真实轮换终态。PostgreSQL、MinIO、JWT、检索令牌已轮换，TikTok 凭据加密主密钥已生成；独立审计从成功恢复副本读取旧值，确认 PostgreSQL/MinIO/检索旧值拒绝、新值接受，四个应用容器取得新配置，全部真实能力开关保持 false。三个公网 HTTPS 健康端点为 200，响应和轮换后日志未命中凭据；系统 Docker、边缘 Nginx 和隧道边界未变。历史结果见 `TR-MVP-001-20260921-R01` 与 `release/evidence/staging/crm-staging-credential-rotation-20260921.json`；当时外部凭据缺失，R01 为 `PARTIAL`。

## Staging 外部凭据安全注入验证

候选 subject `4ffb888a6af59a25333d6c984273fd1a89abff09` 绑定 2026-09-23 现场注入事实。TikTok App Key、Service ID、App Secret 与 DeepSeek API Key 已由受限 SSH 通道注入 staging，四个应用容器按职责取得字段，真实能力开关全部 false；Mock 专用 `TIKTOK_WEBHOOK_SECRET` 保持空。三个公网 HTTPS 健康端点均 200，日志/响应未命中四项值，出口仍为 `38.55.145.52`，系统 Docker 清单未变。一次性工具首次在预变更阶段因 cwd 权限失败，旧状态经独立复核，修正后成功。局部后端回归 201 passed、1 warning；不是全量回归，也未调用真实 TikTok/DeepSeek。R02 `TR-MVP-001-20260923-R02` 结论 `PASS` 只适用于 MVP-001 注入范围；G0 恢复/回滚、G1/G2/G4 和 production 仍待独立验收。

## TikTok 固定出口 staging 验证

候选 subject `746c10cacf7b2e1e827317e9759e203dc0cc9551` 的 PR #37 CI 后端/前端均通过；proxy 刷新修复的门禁测试为 `103 passed, 2 skipped`。真实 staging deploy `35806983990` 观测配置/实际出口均为 `38.55.145.52`、迁移头应用、三个公网端点 200。只停止出口 helper 后验证器非零，恢复后再次观测固定 IP；两台服务器的入口、GitLab 和其他站点保护基线未发生业务漂移。当前运行的 backend/frontend 镜像与候选构建输入零差异，旧检索镜像有依赖差异；两项仅限 staging 的用户授权及 GHCR 下载阻断均见 `TR-MVP-EGRESS-001-20260923-R02` 和机器证据。该结论不覆盖真实 TikTok 店铺、DeepSeek、恢复演练或 production。

## 本次根目录迁移验证口径

本次将产品代码恢复到源提交 `77d9f8f` 并提升到仓库根，验证范围为 Git 历史、目录结构、活动路径引用、JSON 可解析和首版 Rootless Staging 关键资产。按用户要求不执行完整后端回归、前端安装/构建或真实平台门禁，且历史测试结果不得被描述为本分支重新运行结果。
