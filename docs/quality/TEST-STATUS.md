# 最新测试状态

本文件只汇总当前仍有效的正式结论。历史报告用于追溯，不代表本分支重新运行。生产是否可放行以 `../operations/RELEASE-GATES.md` 为准。

## 模块状态

| 主题 | 已有结论 | 尚缺内容 |
|---|---|---|
| M00 基础设施 | Split-ingress Rootless staging 已通过真实 DNS/TLS、两台主机部署、迁移头、容器/公网健康、隧道恢复和公司负载零变化验收；内部运行凭据已轮换，外部四项凭据已安全注入；PostgreSQL/MinIO 备份已在隔离目标恢复；2026-09-30 六摘要预取、候选部署、上一版实际切回和候选切返均通过，见 `TR-MVP-008-20260930-R01`。2026-10-08 代理配置改用持久源码后正式部署和再次重启通过，见 `TR-MVP-STAGING-PROXY-PERSIST-001-20261008-R01` | 外部平台实际接受验证和 production 放行；MinIO 原业务桶为空，真实业务对象恢复尚无样本；G6 连续五日仍未验证 |
| M01 管理端/工作台 | 认证、权限、看板、会话、知识、团队、Agent 和人工消息主流程有自动化覆盖；本机生产构建浏览器 22/22、前端契约 41/41；新缓存修复已仅部署 staging，公网精确 HTML `no-store`、指纹 JS `immutable` | 带身份 staging 全按钮浏览器复验及真实 TikTok 业务验收 |
| M02 数据与任务 | PostgreSQL/pgvector、Redis、Worker、幂等、审计和店铺隔离有模块/综合测试 | 真实负载、长稳和灾难恢复 |
| M03 平台集成 | TikTok 首次 OAuth、Scope、Token 生命周期、六项非物流只读和跨店失败关闭有 staging 真实证据；2026-10-09 最新 job `connected`、临时密文清空、匹配成功审计 1 条，按用户新口径 G1 核心通过；Webhook、普通消息和 `unknown` 对账已有确定性检查 | G1-L 增强物流 `202604` 待合格 CBT 首程订单并须在 G8 前通过；G2 真实订阅/投递、G3 人工消息和对账、G4～G6 仍待验；同一 callback 现场重放未验但不再阻断 G1 核心 |
| M04 AI 与 RAG | Provider、DLP、结构化声明、知识审批、工具边界和本地 BGE 已覆盖；固定综合集为 32/36（88.89%） | 真实 DeepSeek 质量、50 客户端 SSE、5 日稳定性；公开自动回复/营销未放行 |

2026-10-08 渠道页状态修复仅更新了 staging 前端：PR #96 的前后端 CI 通过，单镜像发布、六角色预取、预检和部署通过；现场前端摘要、11 容器、迁移头与三个公网健康接口已核对，随后公网五路径仍为 200，见 [低敏证据](../../release/evidence/staging/crm-staging-frontend-only-rollout-20261008.json)。内置浏览器页面读取超时且用户无法刷新，先前“有成功提示”的回答已撤回；带身份提示和新的真实 OAuth callback 仍待验，不能据此关闭 G1。

2026-10-09 Edge 保留的新 callback 为 303，最新 job `connected`，因此上次 TikTok 授权页的“连接失败”不是本次最新任务的结果。新标签页打开旧 Network 项未产生第二次 callback GET，重放仍未验收。增强物流对五笔不同的 TikTok 配送订单均返回平台业务码 `11007009`；已确认固定出口、所需 Scope 和 `shop_cipher`，但 CBT 首程适用订单及平台开通状态未知。后端 TikTok 只读聚焦测试本次 26 passed。见 [低敏诊断证据](../../release/evidence/staging/crm-staging-g1-live-diagnostics-20261009.json)，G1 未签署。

2026-10-09 后续用户将 G1 本阶段验收限定为首次真实授权完成、Scope/Token 生命周期、非物流只读和隔离，现场二次 callback GET 不再阻断；增强物流 `202604` 独立留在 G1-L，最终 G8 前仍须通过。只读复核最新 job 为 `connected`、完成且无错误、临时密文字段为空、匹配成功审计 1 条、渠道 connected；因此按**新口径**，G1 核心范围在 staging 通过。G2 可启动准备，但 Partner Center 当前订阅数 0，staging 真实只读与 Webhook 开关均为 false，真实投递仍未验证。见 [低敏关闭与预检证据](../../release/evidence/staging/crm-staging-g1-core-closure-20261009.json)；production 和 G8 未放行。

## BGE 正式基线

- 质量：Dense Recall@20 = 100%，Rerank Recall@5 = 100%，MRR = 1，nDCG = 1，引用合法率 = 100%，无答案拒判率 = 100%。
- 接受阈值：Dense 相似度 `0.52`。
- RTX 4060 8GB 单实例容量：50 并发零失败；Embedding P99 = 375.22 ms；Reranker P99 = 1966.59 ms；显存峰值 = 3697 MB；冷启动 = 24.256 s。
- 机器证据：`release/evidence/retrieval/bge-quality-threshold-052-20260821.json`、`bge-capacity-gpu-gate-20260821.json`、`bge-gpu-runtime-20260821.json`。

这些结果固定模型、硬件、数据集与当时配置，不自动外推到其他模型 Revision、GPU、并发模型或生产网络。

## 当前未关闭风险

- `MVP-READONLY-LOG-001` 的源码门禁见 `TR-MVP-READONLY-LOG-001-20260928-R01`；staging 现有后端上的六项非物流真实只读重测见 `TR-MVP-G1-NONLOG-001-20260928-R01`。后者只证明这六项路径成功，不覆盖增强物流、重复回调或 G1 签署；真实 Token 自然刷新另见 `release/evidence/staging/crm-staging-g1-natural-token-refresh-20261008.json`。日志部署与增强物流的单独记录仍在 PR #56 草稿中。

- G4 的 4 个未通过用例尚未形成生产 AI 质量闭环；危险逃逸为 0、合法输入误拦截为 0，但综合正确率不能替代逐项关闭。
- 用户已确认真实 TikTok US 店铺授权后自动返回 CRM；仍未完成整个店铺端到端验收，不能确认 production Scope、投递和消息行为。
- `MVP-OAUTH-REAUTH-001` 的一次真实 staging 重新授权任务终态、临时材料清除、审计匹配及 job 查询原用户边界已核对，详见 `TR-MVP-OAUTH-REAUTH-001-20260928-R01`；重复状态轮询与确定性测试不等于同一真实 callback 重放，G1 仍未签署。
- TikTok Partner Center 与 DeepSeek 外部四项凭据已安全注入 staging，但尚未执行真实平台接受验证；真实能力继续失败关闭。
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
