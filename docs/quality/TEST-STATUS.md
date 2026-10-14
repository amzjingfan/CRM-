# 最新测试状态

本文件只汇总当前仍有效的正式结论。历史报告用于追溯，不代表本分支重新运行。生产是否可放行以 `../operations/RELEASE-GATES.md` 为准。

## 模块状态

2026-10-14 G4 R31 本地候选：Prompt `real-model-eval-v1.2.11` 对页面否定展示和证据充足的多语言政策修复增加明确约束。subject `fb7a58f` 的定向请求契约 34 passed；完整后端 1778 passed、19 skipped、2 warnings，Ruff、格式和 mypy 通过，见 [R31 TR](../reports/tests/TR-MVP-005-20261014-R31.md)。本轮未发布镜像、部署 staging 或调用 DeepSeek；下方 R30 仍是最新现场，G4 `PARTIAL`、production No-Go。

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
| M04 AI 与 RAG | Provider、DLP、结构化声明、知识审批、工具边界和本地 BGE 已覆盖。`v1.2.10` 后端已部署 staging；[live #38509348666](https://github.com/CP11-gh/CRM/actions/runs/38509348666) 终态 34/36（94.44%）、危险逃逸 0、合法误拦 0、Provider 故障 0，机器 `passed=true`，见[低敏报告](../../release/evidence/ai/crm-staging-g4-r30-live-38509348666.json) | 否定说明缺项、多语言政策第二稿转人工，两条逐项失败未闭环；G4 仍部分通过。50 客户端 SSE、5 日稳定性未完成；公开自动回复/营销未放行 |

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

- G4 最新真实复测有 2 个未通过用例：否定说明缺必需组 0，多语言政策修复转人工且缺组 0、1。危险逃逸和合法输入误拦截为 0，但综合正确率不能代替逐项关闭；低敏报告不保存模型原文，后续候选须保留严格判分和冻结集。
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
