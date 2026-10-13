# 真实环境发布门禁

状态含义：`已实现` 只说明代码/确定性测试存在；`待真实验证` 表示仍缺真实账号、负载或持续运行证据；`阻塞` 表示不能签署发布；`范围外` 表示不属于 TikTok 人工辅助 v0.1。

| 门禁 | 范围 | 当前状态 | 阻断条件 / 证据入口 | 下一动作 |
|---|---|---|---|---|
| G0 | 基础设施、配置、密钥、备份与回滚 | 通过（staging） | `MVP-STAGING-001` split-ingress Rootless 部署、`MVP-001` 凭据轮换/安全注入、`MVP-EGRESS-001` 固定出口均有现场证据；`MVP-008-RESTORE-001` 已在隔离 PostgreSQL/MinIO 验证备份恢复。2026-09-30 六个不可变镜像摘要预取、候选部署、上一版三镜像实际切回及候选切返均通过，切返后候选三摘要、迁移头 `024`、11 容器、三个公网健康接口 200 和固定出口 `38.55.145.52` 已核对，见 [G0 现场证据](../../release/evidence/staging/crm-staging-mvp008-g0-20260930.json)。2026-10-08 固定出口 helper 被发现退出，已只启动该容器并复核健康与固定 IP，见 [恢复证据](../../release/evidence/staging/crm-staging-tiktok-egress-recovery-20261008.json)；该运行中断须计入 G6。活动 MinIO 业务桶为空，真实对象字节恢复只在隔离合成对象上验证；不外推 production | 转向 G1～G6 的真实平台、模型、容量和持续运行验收；G8 仍阻塞 |
| G1 | TikTok 首次 OAuth、Token 生命周期、非物流只读与店铺隔离 | 通过（staging 核心口径） | 2026-10-09 08:59（北京时间）真实 callback GET 为 303，最新 job `connected`、一次性 code/state 密文字段清空、匹配成功审计 1 条，渠道 connected；2026-10-04 自然刷新成功；六项非物流只读和跨店失败关闭已有现场证据。见 [本次诊断](../../release/evidence/staging/crm-staging-g1-live-diagnostics-20261009.json)、[自然刷新](../../release/evidence/staging/crm-staging-g1-natural-token-refresh-20261008.json)及 [非物流只读](../../release/evidence/staging/crm-staging-g1-nonlog-20260928.json)。用户 2026-10-09 明确将现场二次 callback GET 从本阶段关闭条件移除；确定性幂等回归仍保留 | 允许进入 G2；本结论仅限 staging，最终发布仍需 G1-L 及其他门禁 |
| G1-L | 增强物流 `202604` | 延后，最终 G8 前必须通过 | 五笔不同 TikTok 配送订单均返回平台码 `11007009`；尚无确认符合 CBT 首程条件的订单或平台开通说明，不能宣称物流已通过。用户决定不以此阻止 G2，v0.1 物流范围不删除 | 取得合格包裹或平台适用性说明后重测，并保留低敏成功证据 |
| G2 | TikTok Webhook | 阻塞（缺真实消息来源） | PR #101～#105 已合入 main；单 backend 私有镜像发布、六角色预取和 staging G2 模式 validate/deploy 通过，见[部署证据](../../release/evidence/staging/crm-staging-g2-backend-rollout-20261009.json)。用户授权的一次 `NEW_MESSAGE` PUT 后，写后 GET 与独立只读 GET 均确认订阅数 1、预期地址匹配数 1、其他地址数 0，见[订阅证据](../../release/evidence/staging/crm-staging-g2-subscription-confirmed-20261009.json)。只读事件聚合现场基线为新消息事件 0、入站消息 0、未绑定事件 0，见[基线证据](../../release/evidence/staging/crm-staging-g2-event-baseline-20261009.json)。2026-10-12 最新[只读复核](../../release/evidence/staging/crm-staging-g2-observer-38213787332.json)仍为新消息事件 0、入站消息 0。用户报告买家侧电脑和手机均无商家聊天入口；Seller Center 有 Customer Messages，但没有受控测试买家现成会话。已有 G1 证据确认 customer_service Scope 与真实只读会话查询；当前不能将入口缺失归因为权限、地区或平台故障。官方投递、重试、乱序、审计及恢复切换仍无现场证据 | 请店铺所有者通过 Partner Center 支持确认该 US 跨境店的买家发起消息条件，以及是否有官方 NEW_MESSAGE 测试投递方式；取得可控真实入站消息后重跑只读观察，核对签名、绑定、处理与审计，再验重试、乱序及恢复。不得向真实顾客发送测试消息，也不得把订阅或零事件计为通过 |
| G3 | 人工确认普通消息 | 实施中，真实发送待验 | 用户 2026-10-09 决定先于受阻的 G2 推进 G3 准备；此顺序例外不关闭 G2，也不放行 G8。基线 `0f80d3f804b425b8aca53e1f8b34939e52b6e89d` 上人工发送客户端、领域与工具执行三组聚焦测试本轮 55 passed、1 warning，覆盖确认、签名、单次请求、固定出口、`unknown` 和对账边界。staging G2 overlay 的 `REAL_TIKTOK_MESSAGE_WRITE_ENABLED=false`；没有受控测试买家会话，尚无真实发送、平台对账和回滚证据 | 保持真实写关闭；取得由店铺所有者控制的 TikTok 测试会话后，形成精确单次发送与恢复方案，另行确认外部消息和运行开关范围，再执行并观察平台、消息、审计及 `unknown` 收敛。不得用真实顾客或 Mock 代替现场验收 |
| G4 | DeepSeek、RAG、DLP 与知识审批 | 部分通过 | main `769096098b743992d223f01fa44d9c62da97ba1b` 的 Prompt `v1.2.8` 后端已部署 staging；[prepare](../../release/evidence/ai/crm-staging-g4-v128-prepare-38388814954.json) 为 36 条冻结样本、零 Provider 调用；[live #38389129411](https://github.com/CP11-gh/CRM/actions/runs/38389129411) 为 34 条合成模型请求、2 条本地注入、首轮 32/34、终态 30/36=83.33%，低于 85% 门槛；危险逃逸 0、合法误拦 3、Provider 失败 0。[低敏报告](../../release/evidence/ai/crm-staging-g4-v128-live-38389129411.json)显示三条 `LOCATION_SEPARATORS`、一条否定缺项、一条政策证据不足、一条修复无草稿；G4 未签署。BGE 证据见 `release/evidence/retrieval/` | 保持 DLP 失败关闭，分别定位标点误拦边界、政策证据指代和多语言修复；确定性安全验证后才做下一候选。G5/G6 另验 |
| G5 | 50 客户端 DeepSeek SSE | 未开始 | 缺授权真实 Provider、50 客户端并发、P99/错误/断连恢复证据 | 在 staging 执行低敏冻结负载测试 |
| G6 | 连续 5 日稳定性 | 未开始 | 缺 99.5% 可用性、队列、资源、告警和恢复证据；2026-10-06～10-08 固定出口 helper 退出且未自行恢复，本次中断不得计入稳定运行 | G1～G5 完成并处理固定出口运行中断风险后，重新开始 5 日观察 |
| G7 | 高风险写入与自动化 | 范围外 | `AUTO_REPLY_ENABLED=false`、`REAL_TIKTOK_HIGH_RISK_WRITE_ENABLED=false`；无放行证据 | v0.1 后另立需求、评审和门禁 |
| G8 | 最终生产签署 | 阻塞 | G1 核心范围已按 2026-10-09 用户决定通过，但 G1-L、G2～G6 未全部完成，安全、业务、运维尚未联合签署 | 汇总真实证据并召开最终 Go/No-Go |

G4 政策证据指代候选 subject `dbb65f5` 的确定性测试见 [R22 TR](../reports/tests/TR-MVP-005-20261013-R22.md)，尚未发布镜像、部署或真实模型复测；表中 30/36 仍是最新现场事实。其他失败和 G5/G6 不因本地代码通过而关闭。

2026-10-12 G4 `v1.2.4` 的低敏缺失组序号已在一次获批真实复测中产生，历史报告不能回填。本轮仍有两条失败：英文否定状态说明缺组 0、英文条件说明命中未引用禁用词。新增诊断不放宽禁用词规则、阈值或冻结数据；下一次镜像/部署及模型调用须独立授权。

2026-10-13 Prompt `v1.2.5` 已分别获批发布镜像、部署 staging 和运行一次真实 DeepSeek 复测，见 [R11 TR](../reports/tests/TR-MVP-005-20261013-R11.md)。两条禁用内容失败使 G4 保持部分通过；不得将综合 85% 门槛当成逐项通过，也不得复用本次付费授权。

Prompt `v1.2.6` 已按用户确认的有界设计增加条件政策与购物车草稿的通用输出前检查，本机测试见 [R12 TR](../reports/tests/TR-MVP-005-20261013-R12.md)。随后镜像、staging 和单次付费复测分别获批并完成，见 [R13 TR](../reports/tests/TR-MVP-005-20261013-R13.md)；条件政策仍失败且售后出现新失败，不能复用本次付费授权或把 85% 总分当作 G4 关闭。

`v1.2.7` 已由 [PR #137](https://github.com/CP11-gh/CRM/pull/137) 合入 main：政策答复收敛为有证据的正向申请和审核流程，删除重复反向禁令；本地全量回归、静态检查和 PR 双 CI 通过，见 [R14 TR](../reports/tests/TR-MVP-005-20261013-R14.md)。后续单后端镜像、staging 部署及一次付费 DeepSeek live 已分别获批并完成，见 [R15 TR](../reports/tests/TR-MVP-005-20261013-R15.md)。两条逐项失败继续阻断 G4，不能复用本次付费授权。

G4 政策校验与一次修复已由 [PR #141](https://github.com/CP11-gh/CRM/pull/141) 合入，且按上表部署并首次真实评测。此次失败是当前结论；[R17 TR](../reports/tests/TR-MVP-005-20261013-R17.md)保留受审的低敏现场事实和诊断候选，不能沿用之前 34/36 的数值关闭 G4。

2026-10-09 G3 安全补丁在隔离 PostgreSQL 复现并修复了中断后遗留 `processing` 消息未阻断下一次真实发送的问题；完整后端回归 `1726 passed, 3 skipped`，PR #109 已合入 main。2026-10-10 单后端镜像发布、六角色预取、G2 模式 validate/deploy 和运行摘要核对通过，见[低敏现场证据](../../release/evidence/staging/crm-staging-g3-backend-rollout-20261010.json)；staging 真实消息写仍关闭。若将来出现遗留 `processing`，不得自动重发或直接改写数据库；需先确认没有在途调用、核对平台事实并形成受审恢复路径。补丁和部署健康不替代受控会话的一次真实发送与对账，G3 仍未通过。

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
