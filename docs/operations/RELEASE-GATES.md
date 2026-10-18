# 真实环境发布门禁

状态含义：`已实现` 只说明代码/确定性测试存在；`待真实验证` 表示仍缺真实账号、负载或持续运行证据；`阻塞` 表示不能签署发布；`范围外` 表示不属于 TikTok 人工辅助 v0.1。

| 门禁 | 范围 | 当前状态 | 阻断条件 / 证据入口 | 下一动作 |
|---|---|---|---|---|
| G0 | 基础设施、配置、密钥、备份与回滚 | 通过（staging） | `MVP-STAGING-001` split-ingress Rootless 部署、`MVP-001` 凭据轮换/安全注入、`MVP-EGRESS-001` 固定出口均有现场证据；`MVP-008-RESTORE-001` 已在隔离 PostgreSQL/MinIO 验证备份恢复。2026-09-30 六个不可变镜像摘要预取、候选部署、上一版三镜像实际切回及候选切返均通过，切返后候选三摘要、迁移头 `024`、11 容器、三个公网健康接口 200 和固定出口 `38.55.145.52` 已核对，见 [G0 现场证据](../../release/evidence/staging/crm-staging-mvp008-g0-20260930.json)。2026-10-08 固定出口 helper 被发现退出，已只启动该容器并复核健康与固定 IP，见 [恢复证据](../../release/evidence/staging/crm-staging-tiktok-egress-recovery-20261008.json)；该运行中断须计入 G6。活动 MinIO 业务桶为空，真实对象字节恢复只在隔离合成对象上验证；不外推 production | 转向 G1～G6 的真实平台、模型、容量和持续运行验收；G8 仍阻塞 |
| G1 | TikTok 首次 OAuth、Token 生命周期、非物流只读与店铺隔离 | 通过（staging 核心口径） | 2026-10-09 08:59（北京时间）真实 callback GET 为 303，最新 job `connected`、一次性 code/state 密文字段清空、匹配成功审计 1 条，渠道 connected；2026-10-04 自然刷新成功；六项非物流只读和跨店失败关闭已有现场证据。见 [本次诊断](../../release/evidence/staging/crm-staging-g1-live-diagnostics-20261009.json)、[自然刷新](../../release/evidence/staging/crm-staging-g1-natural-token-refresh-20261008.json)及 [非物流只读](../../release/evidence/staging/crm-staging-g1-nonlog-20260928.json)。用户 2026-10-09 明确将现场二次 callback GET 从本阶段关闭条件移除；确定性幂等回归仍保留 | 允许进入 G2；本结论仅限 staging，最终发布仍需 G1-L 及其他门禁 |
| G1-L | 增强物流 `202604` | 延后，最终 G8 前必须通过 | 五笔不同 TikTok 配送订单均返回平台码 `11007009`；尚无确认符合 CBT 首程条件的订单或平台开通说明，不能宣称物流已通过。用户决定不以此阻止 G2，v0.1 物流范围不删除 | 取得合格包裹或平台适用性说明后重测，并保留低敏成功证据 |
| G2 | TikTok Webhook | 实施中（受控买家两次真实入站） | [订阅证据](../../release/evidence/staging/crm-staging-g2-subscription-confirmed-20261009.json)确认唯一回调。2026-10-17 受控手机买家的首条真实消息已在 Seller Center 与 CRM 显示，[预检](../../release/evidence/staging/crm-staging-tiktok-inbound-preflight-20261017.json)证实验签与处理；双向复测时买家回复再次经 `BUYER`、验签通过且店铺绑定的 Webhook 入库，平台到接收 2.3 秒、接收到处理 0.5 秒，见[G3 低敏证据](../../release/evidence/staging/crm-staging-g3-bidirectional-20261017.json)。真实重试、乱序、完整审计和持续恢复尚未验收 | 继续验证重试、乱序、持续恢复与完整审计；两次成功事件不替代 G2 全部门禁 |
| G3 | 人工确认普通消息 | 通过（staging 已审核单店人工范围） | 原受控会话经用户逐条授权完成一次真实外发、TikTok 官方历史回读及手机买家回复入库，见 [MVP-004 R04](../reports/tests/TR-MVP-004-20261017-R04.md)。随后店铺范围源码 PR #348/#350 与手动 validate/deploy 通过；同店铺 180 个现有会话运行汇总均为 `send_mode=real`，两个真实会话工作台显示真实发送，跨店拒绝与 `unknown` 失败关闭由 337 项定向测试覆盖，见[店铺范围 TR](../reports/tests/TR-MVP-TIKTOK-STORE-SEND-001-20261018-R01.md)及[低敏运行汇总](../../release/evidence/staging/crm-staging-store-send-runtime-20261018.json)。R80 独立 G5 窗口已再次恢复原后端和 G3 单店范围。未对所有会话逐一外发，模式可用不等于每条平台投递成功 | 保持 staging 已审核单店、人工确认的普通文本范围；遇到不确定结果先平台对账。其他店铺、自动发送和 production 均需独立批准与验证；G2/G8 不因本项通过而关闭 |
| G4 | DeepSeek、RAG、DLP 与知识审批 | 通过（staging 冻结合成质量） | [R55 部署与零调用准备](../reports/tests/TR-MVP-005-20261015-R55.md) 锁定运行后端 `sha256:1045d683…eec363` 和冻结 36 条；[R56 一次获批 live](../reports/tests/TR-MVP-005-20261016-R56.md) 从 main `54594dc4` 执行 34 条 DeepSeek 合成样本加 2 条本地故障注入，逐项 36/36，危险逃逸、合法误拦、Provider 故障均为 0，机器 `passed=true`。两条 R52 政策失败经受控修复通过；BGE Top-5/0.52 与知识审批确定性证据沿用既有基线。 | 当前 G4 冻结合成质量门禁关闭；R41 批量超时根因仍未证实，持续观察。真实买家闭环、端到端 SSE 和实际 AI 独立解决率不能由本轮推断；G1-L、G2/G3、G5/G6 及 G8 独立验收，production No-Go |
| G5 | 50 客户端 DeepSeek SSE | 单会话与 50/50 安全输出通过；严格并发时延未通过 | [R80 手动窗口](../reports/tests/TR-MVP-006-20261018-R80.md)从 main `22e9f8a1` 发布并临时部署 R79 后端；50/50 隔离身份、唯一 FAQ ready，单会话首安全 delta 2152.8 ms、总 2155.1 ms，严格 `<3000/<5000 ms` 通过。50 并发全部 HTTP 200 且 50/50 有安全 delta，无 Provider 故障；首输出 P99 7287.4 ms、总 P99 7293.9 ms，严格门槛失败，最快首 delta 仍为 3068.4 ms。检索 P99 3336.6 ms，入口 accepted P99 2266.0 ms，需只读拆分归因。资源 20 秒采 7 点，未含 BGE 服务；断连尚未独立验收。原 G3 单店人工发送、三健康与固定出口已恢复 | 零 DeepSeek 只读定位 BGE、数据库和入口时延；有界修复后完整重测 50/50 安全输出、严格 P99、资源/断连与 G3 恢复。Schema、DLP、独立复核和阈值不放宽。production No-Go |
| G6 | 连续 5 日稳定性 | 未开始 | 缺 99.5% 可用性、队列、资源、告警和恢复证据；2026-10-06～10-08 固定出口 helper 退出且未自行恢复，本次中断不得计入稳定运行 | G1～G5 完成并处理固定出口运行中断风险后，重新开始 5 日观察 |
| G7 | 高风险写入与自动化 | 范围外 | `AUTO_REPLY_ENABLED=false`、`REAL_TIKTOK_HIGH_RISK_WRITE_ENABLED=false`；无放行证据 | v0.1 后另立需求、评审和门禁 |
| G8 | 最终生产签署 | 阻塞 | G1 核心范围已按 2026-10-09 用户决定通过，但 G1-L、G2～G6 未全部完成，安全、业务、运维尚未联合签署 | 汇总真实证据并召开最终 Go/No-Go |

G5 [R77 修复](../reports/tests/TR-MVP-006-20261018-R77.md)已合入并在 [R78 现场](../reports/tests/TR-MVP-006-20261018-R78.md)完成手动单会话和 50 并发复测：本地检索排队显著缩短，但安全输出仍为 49/50 且首输出/总时延 P99 超限。旧 G3 模式已恢复；G5 和 production 仍未放行。

G5 [R79 本地候选](../reports/tests/TR-MVP-006-20261018-R79.md)已通过连接池复用、G5 专用 4 worker 和独立复核温度 0 的确定性及完整后端门禁；零模型探针仅提供 G3 空载入口基线。它不改变上表 R78 的真实失败状态；必须经手动镜像、可恢复 staging 窗口重新取得 50/50 安全输出、严格时延、资源与断连证据。

G5 [R80 现场](../reports/tests/TR-MVP-006-20261018-R80.md)已验证 R79 候选 50/50 安全输出及原 G3 恢复；并发 P99 仍失败，资源未含 BGE、断连未独立验收。以该轮真实结果作为当前 G5 结论，先做零 DeepSeek 分阶段诊断。

G5 [R81 只读诊断](../reports/tests/TR-MVP-006-20261018-R81.md)在恢复 G3 后测得空载四路本地 BGE/50 路 FAQ SQL 较快；与 R80 真实并发检索长尾并存，尚不能确认原因。按同批匿名客户端关联，接入和检索/Agent 都与首安全输出变慢共同变化。下一现场窗口须同步采样负载时的本地 BGE、SQL 和接入阶段，再依据证据修复；不得用空载探针宣称 G5 通过。

G5 R69 组合 FAQ 源码已合并并在 R70 手动窗口实测。真实模型虽然完成分类与草稿，但把内容层 `needs_human` 与 CRM 固有人工发送复核混同，安全转人工；没有可计时的安全 `delta`。R70 的 Agent 检索/组合调用/独立复核耗时 269/1948/637 ms，内部首次输出 3004 ms 不代替 SSE 安全输出。R71 本地候选仅修正 Prompt 歧义并通过确定性回归，尚无真实模型与延迟证据；不能用这一次 HTTP 200 启动 50 并发。

G5 [R49 手动候选镜像](../../release/evidence/staging/crm-staging-g5-r49-manual-backend-image-20261017.json)随后经 OCI index `sha256:8dabe73b…c017` 完成两次获批的 [R50 手动窗口](../reports/tests/TR-MVP-006-20261017-R50.md)。第一次单会话被 Origin/CORS 拒绝；第二次 HTTP 200 但 FAQ 草稿 `invalid_schema`，无安全 `delta`，50 并发未启动。旧后端与 G3 限定会话已恢复，production 仍为 No-Go。

G5 [R34 续期源码](../reports/tests/TR-MVP-006-20261017-R34.md) 的连续编号、历史验签、精确路径与独占创建本地门禁通过；当时第三份 50 枚令牌已过期。第四份已在 [R38](../reports/tests/TR-MVP-006-20261017-R38.md) 精确现场窗口签发并核对；凭证就绪不代表安全 `delta` 或 50 并发验收通过。
G5 R37 手动窗口的[预取](../../release/evidence/staging/crm-staging-g5-r37-prefetch-20261017.json)与[验证](../../release/evidence/staging/crm-staging-g5-r37-validate-20261017.json)通过；迁移容器因 G5 backend 缺少既有内部检索令牌而失败。已按[恢复证据](../../release/evidence/staging/crm-staging-g5-r37-restore-20261017.json)重新运行旧后端、TikTok Webhook 只读与工作台翻译，三健康 200、LLM/SSE 关闭、限流 10。第四份令牌未签发，合成 SSE 与 DeepSeek 均未调用；G5 仍未通过。G5 专用令牌注入与部署前一致性校验已在源码修复，现场需从修复合入后的当前 main 另行核对。

G5 [R38 现场窗口](../reports/tests/TR-MVP-006-20261017-R38.md)已验证修复版部署与恢复，但单会话只发生安全转人工且没有 `delta`，不能作为质量或容量通过证据。下一次须先确认隔离合成输入能命中受支持的意图与现有 FAQ，再在新授权范围内复测单会话。

`MVP-CONV-SYNC-001` 的 [R03 现场核对](../reports/tests/TR-MVP-CONV-SYNC-001-20261016-R03.md) 曾从授权 TikTok Shop 只读接口回填 179 个会话、2018 条可见历史。该轮工作台只读、真实写关闭；其后 G3 R04 已在受控单会话开通并验证双向普通文本，现行能力以本表 G3 行为准。G2/G8 与 production 仍单独验收。

G5 R12 源码经 [PR #245](https://github.com/CP11-gh/CRM/pull/245) 双 CI 合入 main；[R13 staging 只读对账](../reports/tests/TR-MVP-006-20261016-R13.md) #38877932619 报告原 50 账号匹配、Provider 0、数据库写入 0。[R14 精确修复与预检](../reports/tests/TR-MVP-006-20261016-R14.md) #38878859064/#38878976347 已更新原 50 邮箱并轮换凭证，50/50 身份/会话通过；生效限流仍为 10，预检按 50 并发门禁失败关闭，没有 SSE 负载。G5 和 production 继续 No-Go。

G5 R15 受控窗口源码已由 PR #249 合入 main，但未切换 staging。[R16 源码](../reports/tests/TR-MVP-006-20261016-R16.md)经 [PR #251](https://github.com/CP11-gh/CRM/pull/251) 双 CI 合入 main `5d6c0298`，补原 50 个会话的合成 FAQ/问题与短期凭证续期门禁；仅有源码和隔离数据库证据，尚无现场写入、向量 ready、单会话安全 `delta` 或 50 并发结果。上表 G5 状态继续为未通过；R14 的限流 10 仍是最近明确核对的现场值。

G5 [R17 手动路径](../reports/tests/TR-MVP-006-20261016-R17.md)在本地通过 9 项契约测试及静态检查，尚未发布 R16 新后端镜像或在 staging 执行；用户选择后续不再运行 GitHub Actions。手动入口准备不改变上表 G5 的未通过结论。

G5 [R18 现场只读检查](../reports/tests/TR-MVP-006-20261016-R18.md)已从 GitHub 凭据手动路径在 staging 验证当前 main 源码包、Rootless 身份和环境文件，`service_mutation=false`。此处的 CheckOnly 未核对尚未发布的候选后端、G5 覆盖层、知识/凭证或真实 SSE，因此 G5 继续未通过。

G5 [R19 恢复策略](../reports/tests/TR-MVP-006-20261016-R19.md)补上已部署源码在 main 后续文档提交后仍可执行受审默认恢复/回滚的代码门禁；只有本地契约证据，没有现场恢复演练。G5 状态不变。

G5 [R20 手动只读核对](../reports/tests/TR-MVP-006-20261016-R20.md)使用新版界面配套的运行后端与受审源码，确认原 50 会话全部匹配，但合成 FAQ 尚未准备；Provider 0、业务写入 0。持久夹具入口的容器工作目录需修复。现有工作台翻译与 TikTok 只读模式仍运行；G5 压测窗口和恢复该模式均未验收，G5/production 不放行。

G5 [R22 手动夹具源码](../reports/tests/TR-MVP-006-20261017-R22.md)仅在本地通过完整后端与安全门禁测试，续期后只读对账已纳入；没有新的 staging 内容写入、凭证续期或 50 并发证据。G5/production 结论不变。

G5 [R23 手动 staging 门禁](../reports/tests/TR-MVP-006-20261017-R23.md)从当前 main `7b7acc35` 的新后端镜像完成六角色预取、validate/deploy；实际运行摘要、迁移头、三项公网健康、固定出口、TikTok 只读及工作台翻译均通过。零调用内容检查仍为原 50/50 会话、合成知识未准备、凭证原状态；SSE 关闭、限流 10。原 G5 表格中的“需匹配运行镜像”和“需修复工作目录”已由本轮运行路径解决，但合成内容、向量、凭证、单会话、50 并发与恢复仍未验收，G5/production 不放行。

G5 [R21 恢复模式源码](../reports/tests/TR-MVP-006-20261016-R21.md)已允许手动从 SSE 窗口显式恢复当前 TikTok 只读加工作台翻译组合；本地 151 项相关门禁回归与独立审查通过。尚未在 staging 演练，不能把源码通过视为恢复证据；G5/production 结论不变。

G4 政策证据指代修复 subject `dbb65f5` 的确定性测试见 [R22 TR](../reports/tests/TR-MVP-005-20261013-R22.md)，新镜像、部署和真实模型复测见 [R23 TR](../reports/tests/TR-MVP-005-20261013-R23.md)。单项 `condition-open-002` 通过不代表其他五项通过；G5/G6 独立验收。

G4 `v1.2.9` 的源码验证见 [R24 TR](../reports/tests/TR-MVP-005-20261013-R24.md)，当时的 staging 部署和真实模型复测见 [R25 TR](../reports/tests/TR-MVP-005-20261013-R25.md)；R30 曾缩减到两条逐项失败，当前结论以表中的 R56 为准。

2026-10-14 [R26 本地诊断](../reports/tests/TR-MVP-005-20261014-R26.md)只增加第二次调用的固定低敏结果类别，未改变判分或安全门禁。它已在 main `60bf105` 发布部署；[R27 现场复测](../reports/tests/TR-MVP-005-20261014-R27.md)提供新字段的真实分类。当时的合法误拦和三条失败已由后续 R30 缩减为两条逐项失败，当前签署状态以上表为准。

2026-10-14 [R28 源码候选](../reports/tests/TR-MVP-005-20261014-R28.md)只强化疑似分隔符第二稿的生成约束，保留原 DLP 失败关闭及最多两次调用。候选[单后端镜像](../../release/evidence/staging/crm-staging-g4-r28-image-38504855995.json)已从 main `c7f464c` 发布并验证 manifest。[R29 staging 门禁](../reports/tests/TR-MVP-005-20261014-R29.md)确认新摘要部署、迁移头、三健康、固定出口及零调用 prepare；[R30 live](../reports/tests/TR-MVP-005-20261014-R30.md) 的机器质量门槛已通过，但两条逐项失败仍阻断完整 G4 签署。

2026-10-14 R31 Prompt `v1.2.11` 已合入 main；单个后端[候选镜像](../../release/evidence/staging/crm-staging-g4-r31-image-38516990486.json)从 main `e48ab395` 获批发布并核对不可变摘要及压缩层。镜像发布不等于 staging 运行或模型验收；新候选尚未经过六摘要预取、validate/deploy、零调用 prepare 和受控 live。G4 仍为部分通过，production 不放行。

2026-10-12 G4 `v1.2.4` 的低敏缺失组序号已在一次获批真实复测中产生，历史报告不能回填。本轮仍有两条失败：英文否定状态说明缺组 0、英文条件说明命中未引用禁用词。新增诊断不放宽禁用词规则、阈值或冻结数据；下一次镜像/部署及模型调用须独立授权。

2026-10-13 Prompt `v1.2.5` 已分别获批发布镜像、部署 staging 和运行一次真实 DeepSeek 复测，见 [R11 TR](../reports/tests/TR-MVP-005-20261013-R11.md)。两条禁用内容失败使 G4 保持部分通过；不得将综合 85% 门槛当成逐项通过，也不得复用本次付费授权。

Prompt `v1.2.6` 已按用户确认的有界设计增加条件政策与购物车草稿的通用输出前检查，本机测试见 [R12 TR](../reports/tests/TR-MVP-005-20261013-R12.md)。随后镜像、staging 和单次付费复测分别获批并完成，见 [R13 TR](../reports/tests/TR-MVP-005-20261013-R13.md)；条件政策仍失败且售后出现新失败，不能复用本次付费授权或把 85% 总分当作 G4 关闭。

`v1.2.7` 已由 [PR #137](https://github.com/CP11-gh/CRM/pull/137) 合入 main：政策答复收敛为有证据的正向申请和审核流程，删除重复反向禁令；本地全量回归、静态检查和 PR 双 CI 通过，见 [R14 TR](../reports/tests/TR-MVP-005-20261013-R14.md)。后续单后端镜像、staging 部署及一次付费 DeepSeek live 已分别获批并完成，见 [R15 TR](../reports/tests/TR-MVP-005-20261013-R15.md)。两条逐项失败继续阻断 G4，不能复用本次付费授权。

G4 政策校验与一次修复已由 [PR #141](https://github.com/CP11-gh/CRM/pull/141) 合入，且按上表部署并首次真实评测。此次失败是当前结论；[R17 TR](../reports/tests/TR-MVP-005-20261013-R17.md)保留受审的低敏现场事实和诊断候选，不能沿用之前 34/36 的数值关闭 G4。

2026-10-09 G3 安全补丁在隔离 PostgreSQL 复现并修复了中断后遗留 `processing` 消息未阻断下一次真实发送的问题；完整后端回归 `1726 passed, 3 skipped`，PR #109 已合入 main。2026-10-10 单后端镜像发布、六角色预取、G2 模式 validate/deploy 和运行摘要核对通过，见[当时的低敏现场证据](../../release/evidence/staging/crm-staging-g3-backend-rollout-20261010.json)；当时 staging 真实消息写仍关闭。若将来出现遗留 `processing`，不得自动重发或直接改写数据库；需先确认没有在途调用、核对平台事实并形成受审恢复路径。2026-10-17 的受控双向现场结果以本表 G3 行及 [R04 TR](../reports/tests/TR-MVP-004-20261017-R04.md) 为准。

2026-10-08 staging proxy 的临时配置挂载在容器重启时导致短暂 502；PR #89 的持久源码部署和作业结束后再次重启已通过，见 [持久挂载证据](../../release/evidence/staging/crm-staging-proxy-persistent-source-20261008.json)。G0 的本次运行恢复已复测，G6 仍需重新开始连续五日观察。

同日渠道页 OAuth 状态修复已由 PR #96 的单前端镜像部署到 staging，发布、预取、预检、部署以及前端摘要/健康/迁移头现场核对通过，见 [前端更新证据](../../release/evidence/staging/crm-staging-frontend-only-rollout-20261008.json)。用户撤回此前“有顶部成功提示”的回答，内置浏览器又无法刷新；公网五路径 200 和容器健康仅证明服务可用，带身份页面提示仍待核对。新授权的同一 callback 重放与增强物流 `202604` 仍缺证据，G1 未签署。

2026-10-09 用户在 Edge 保留了本次 OAuth callback 的 Network 记录，staging 代理见 00:59:13Z 的 303，最新任务为 `connected`，code/state 密文字段已清空；00:57:13Z 的另一次 callback 对应独立授权，因 `RESOURCE_CONFLICT` 失败。原 Network 记录在新标签页打开后只到 CRM 登录页，代理没有收到第二次 callback GET，因此不计作同一请求重放。固定出口实测正常；六项非物流只读的既有证据仍有效。本次遍历测试店可见的 325 笔订单，首批 100 笔包含 78 笔 `shipping_type=TIKTOK`；对五笔不同的已跟踪 TikTok 配送订单调用增强物流 `202604`，平台均返回 `11007009`，错误文字指向订单不受支持。[官方说明](https://partner.tiktokshop.com/docv2/page/8syhoy40)限定该接口用于 CBT 跨境首程；目前没有确认这家店存在符合条件的首程扫描订单，也未确认平台是否已为应用/店铺开放此能力，故不能断言代码缺陷或把接口判为通过。见 [本次低敏诊断证据](../../release/evidence/staging/crm-staging-g1-live-diagnostics-20261009.json)。下一步获取平台适用性说明或合格测试订单，再验 `202604`；另择有效新授权完成同一 callback 的真实二次 GET。G1 仍为部分通过，production No-Go。

2026-10-09 后续决定：用户确认只以**这次首次有效回调是否成功**关闭 G1，现场第二次 callback GET 不再作为本阶段前置；增强物流 `202604` 另列 G1-L，暂不测试且不阻止 G2，仍阻止最终 G8。只读复核显示最新授权任务 `connected`、已完成、无错误码、code/state 密文清空、匹配成功审计恰好 1 条且渠道 connected；当前 G1 表格状态以上述新口径为准。G2 启动前的当时预检查得 Partner Center 订阅数 0、staging 真实只读及 Webhook 开关均为 false，公网 ready 200/TLS 校验通过；此后部署状态见 G2 表格，仍未接收真实事件。见 [G1 核心关闭与 G2 预检低敏证据](../../release/evidence/staging/crm-staging-g1-core-closure-20261009.json)。

## 判定规则

- Mock、合成数据和确定性测试只能证明实现，不证明真实生产环境。
- Split-ingress 主机、隧道与入口代理可配置只证明部署路径可建，不证明应用、证书、密钥或恢复已验收。
- 固定出口的代码、Compose、安装器或本地验证通过，只证明候选可部署；必须用合并 main 的不可变镜像在真实 staging 观察 `38.55.145.52`、验证断隧道无直连回退并复核公司负载，才能签署该项。
- 任何门禁出现跨店铺、凭证暴露、重复平台写入、危险内容逃逸或无法回滚时立即 No-Go。
- 机器证据路径和 SHA-256 以 `release/baselines/` 与模型清单为准；文档摘要不能替代原始 JSON/JSONL。

## 可选强化验证：同一 OAuth callback 现场重放

以下保留原受控流程，供后续安全回归使用。按 2026-10-09 用户明确决定，其现场执行结果不再阻止本阶段 G1 核心范围关闭；代码幂等和失败关闭要求仍然有效。

此步骤只在 staging 的专用测试店铺进行。授权操作人先在自己的浏览器开发者工具中开启 Network 的 Preserve log，再从 CRM 发起一次 TikTok 授权；保留首次 callback 的网络请求，等待 CRM 显示已连接。验证人员在操作前后只读取 staging 的任务状态、审计聚合数与健康状态，不读取或导出回调 `code`、`state`、Token、带查询参数的 URL 或 HAR。

首次 callback 必须返回到 CRM，并且在本次观测窗口内恰好新增一个 OAuth job；该 job 最终为 `connected`，`code_cipher` 与 `state_cipher` 均清空，匹配的 `channel.authorize/succeeded` 审计恰好新增一条。然后由授权操作人在同一浏览器的 Network 面板中把**同一条** callback 请求重新打开一次，确认浏览器确实发出第二次 GET。若浏览器不支持从该请求直接重新打开，暂停现场验收，不把重新发起授权或反复轮询 job 状态当作重放。

第二次 GET 应返回 303，指向第一次相同的 job 且状态为 `connected`；前后对比 OAuth job 总数和成功授权审计数均不得再次增加，渠道 Token 密文应保持不变。证据只保存时间窗口、环境/镜像摘要、HTTP 状态、相同 job 的布尔判断、任务终态、密文字段为空和凭证未变化的布尔判断及聚合增量。任一条件不满足，或日志/响应出现回调参数，须记录低敏失败码并修复安全缺陷；该可选现场验证未执行不推翻首次授权成功的结论。增强物流 `202604` 按 G1-L 单独验收。
