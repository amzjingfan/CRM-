# 真实环境发布门禁

状态含义：`已实现` 只说明代码/确定性测试存在；`待真实验证` 表示仍缺真实账号、负载或持续运行证据；`阻塞` 表示不能签署发布；`范围外` 表示不属于 TikTok 人工辅助 v0.1。

| 门禁 | 范围 | 当前状态 | 阻断条件 / 证据入口 | 下一动作 |
|---|---|---|---|---|
| G0 | 基础设施、配置、密钥、备份与回滚 | 通过（staging） | `MVP-STAGING-001` split-ingress Rootless 部署、`MVP-001` 凭据轮换/安全注入、`MVP-EGRESS-001` 固定出口均有现场证据；`MVP-008-RESTORE-001` 已在隔离 PostgreSQL/MinIO 验证备份恢复。2026-09-30 六个不可变镜像摘要预取、候选部署、上一版三镜像实际切回及候选切返均通过，切返后候选三摘要、迁移头 `024`、11 容器、三个公网健康接口 200 和固定出口 `38.55.145.52` 已核对，见 [G0 现场证据](../../release/evidence/staging/crm-staging-mvp008-g0-20260930.json)。2026-10-08 固定出口 helper 被发现退出，已只启动该容器并复核健康与固定 IP，见 [恢复证据](../../release/evidence/staging/crm-staging-tiktok-egress-recovery-20261008.json)；该运行中断须计入 G6。活动 MinIO 业务桶为空，真实对象字节恢复只在隔离合成对象上验证；不外推 production | 转向 G1～G6 的真实平台、模型、容量和持续运行验收；G8 仍阻塞 |
| G1 | TikTok OAuth 与只读 | 部分通过，未签署 | 用户确认 staging 美国测试店铺授权后自动回到 CRM；既有任务 `connected`、code/state 已清空、匹配成功审计一条，异人读取 404，证据见 `release/evidence/staging/crm-staging-oauth-reauth-20260928.json`。六项非物流只读和跨店失败关闭见 `crm-staging-g1-nonlog-20260928.json`。2026-10-04 后台 job 真实成功刷新 Token，渠道保持 connected，见 [自然刷新证据](../../release/evidence/staging/crm-staging-g1-natural-token-refresh-20261008.json)。2026-10-08 用户重新授权后，现场新增一个 `connected` job，code/state 清空、成功授权审计一条、所需 Scope 与加密凭证正常，见 [复授权证据](../../release/evidence/staging/crm-staging-g1-oauth-reauth-20261008.json)。代理记录两次 callback 303，但尚未证明第二次由同一浏览器重开同一请求，现场受控重放仍未验。同日 03:48Z 新授权发起返回 200，但截至 04:05Z 公网入口未见该次有效 callback，OAuth job/成功审计未新增，原渠道的 TikTok 已授权店铺只读查询仍成功；无参数诊断 callback 的 422 不计入授权，见 [未到达回调证据](../../release/evidence/staging/crm-staging-g1-oauth-no-callback-20261008.json)。同日 05:32Z 与 05:51Z 再次发起均返回 200，但截至 06:32Z 公网入口仍无新 callback，数据库仍只有 03:13Z 完成的旧任务；CRM 页面显示的旧连接不计作本次授权，见 [再次核对证据](../../release/evidence/staging/crm-staging-g1-oauth-no-new-callback-20261008-pm.json)。增强物流 `202604` 返回 `11007009`，不能以旧版或其他接口成功替代；Webhook 订阅查询为零不代表 G2 通过 | 在普通 Chrome 中从 CRM 新发起授权，保留 Network 并核对同一 callback 受控重放；若仍无公网回调，记录浏览器低敏错误并核对 TikTok 授权页；单独确认 `202604` 平台错误；维持 production No-Go |
| G2 | TikTok Webhook | 已实现，待真实验证 | 签名、幂等和内部回归已覆盖；缺 Partner Center 实际投递、重试与乱序证据 | 注册真实订阅并验证投递、重放和审计 |
| G3 | 人工确认普通消息 | 已实现，待真实验证 | 确定性发送、`unknown`、对账已覆盖；缺真实发送、对账和回滚证据 | 以低风险测试会话发送一次并制造/收敛不确定状态 |
| G4 | DeepSeek、RAG、DLP 与知识审批 | 部分通过 | 固定综合集 32/36=88.89%，危险逃逸 0、合法输入误拦截 0；BGE 证据见 `release/evidence/retrieval/`。生产翻译、公开回复、营销和数据出境未验收；后三者不属 v0.1 | 完成 v0.1 AI 建议真实质量与数据边界复测 |
| G5 | 50 客户端 DeepSeek SSE | 未开始 | 缺授权真实 Provider、50 客户端并发、P99/错误/断连恢复证据 | 在 staging 执行低敏冻结负载测试 |
| G6 | 连续 5 日稳定性 | 未开始 | 缺 99.5% 可用性、队列、资源、告警和恢复证据；2026-10-06～10-08 固定出口 helper 退出且未自行恢复，本次中断不得计入稳定运行 | G1～G5 完成并处理固定出口运行中断风险后，重新开始 5 日观察 |
| G7 | 高风险写入与自动化 | 范围外 | `AUTO_REPLY_ENABLED=false`、`REAL_TIKTOK_HIGH_RISK_WRITE_ENABLED=false`；无放行证据 | v0.1 后另立需求、评审和门禁 |
| G8 | 最终生产签署 | 阻塞 | G0～G6 未全部完成，安全、业务、运维尚未联合签署 | 汇总真实证据并召开最终 Go/No-Go |

2026-10-08 staging proxy 的临时配置挂载在容器重启时导致短暂 502；PR #89 的持久源码部署和作业结束后再次重启已通过，见 [持久挂载证据](../../release/evidence/staging/crm-staging-proxy-persistent-source-20261008.json)。G0 的本次运行恢复已复测，G6 仍需重新开始连续五日观察。

## 判定规则

- Mock、合成数据和确定性测试只能证明实现，不证明真实生产环境。
- Split-ingress 主机、隧道与入口代理可配置只证明部署路径可建，不证明应用、证书、密钥或恢复已验收。
- 固定出口的代码、Compose、安装器或本地验证通过，只证明候选可部署；必须用合并 main 的不可变镜像在真实 staging 观察 `38.55.145.52`、验证断隧道无直连回退并复核公司负载，才能签署该项。
- 任何门禁出现跨店铺、凭证暴露、重复平台写入、危险内容逃逸或无法回滚时立即 No-Go。
- 机器证据路径和 SHA-256 以 `release/baselines/` 与模型清单为准；文档摘要不能替代原始 JSON/JSONL。

## G1：真实 OAuth callback 重放验收

此步骤只在 staging 的专用测试店铺进行。授权操作人先在自己的浏览器开发者工具中开启 Network 的 Preserve log，再从 CRM 发起一次 TikTok 授权；保留首次 callback 的网络请求，等待 CRM 显示已连接。验证人员在操作前后只读取 staging 的任务状态、审计聚合数与健康状态，不读取或导出回调 `code`、`state`、Token、带查询参数的 URL 或 HAR。

首次 callback 必须返回到 CRM，并且在本次观测窗口内恰好新增一个 OAuth job；该 job 最终为 `connected`，`code_cipher` 与 `state_cipher` 均清空，匹配的 `channel.authorize/succeeded` 审计恰好新增一条。然后由授权操作人在同一浏览器的 Network 面板中把**同一条** callback 请求重新打开一次，确认浏览器确实发出第二次 GET。若浏览器不支持从该请求直接重新打开，暂停现场验收，不把重新发起授权或反复轮询 job 状态当作重放。

第二次 GET 应返回 303，指向第一次相同的 job 且状态为 `connected`；前后对比 OAuth job 总数和成功授权审计数均不得再次增加，渠道 Token 密文应保持不变。证据只保存时间窗口、环境/镜像摘要、HTTP 状态、相同 job 的布尔判断、任务终态、密文字段为空和凭证未变化的布尔判断及聚合增量。任一条件不满足，或日志/响应出现回调参数，G1 维持未签署并记录低敏失败码。自然 Token 刷新和增强物流 `202604` 仍分别验收。
