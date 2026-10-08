# 项目任务状态

本文件是 CRM 智能聊天系统任务状态的唯一事实源。产品范围与验收原则见 `../product/PRODUCT.md`，生产门禁状态见 `../operations/RELEASE-GATES.md`，治理流程与证据格式见 `../governance/GOVERNANCE.md`。README、项目恢复摘要、报告和 Codex 侧栏只能引用本表，不维护第二套任务状态。

## 状态规则

```text
BACKLOG → READY → DOING → VERIFYING → DONE
DOING/VERIFYING → BLOCKED
未完成状态 → CANCELLED
```

- `BACKLOG`：事项有业务价值，但范围、验收、依赖、资源或授权尚未全部具备。
- `READY`：可验证结果、验收或门禁、依赖、授权边界和验证方法完整。
- `DOING`：已经记录短期分支、`BASE_SHA` 和实际执行范围。
- `VERIFYING`：实现已完成，正在执行验证、审查、文档同步和证据定稿。
- `DONE`：验收通过，最终 IR/TR 已定稿，需要的 RR 已关闭，文档已同步，“最终 SHA”为真实 `CANDIDATE_SUBJECT_SHA`，证据尾区间只包含允许路径。`DONE` 不接受 `WORKTREE`。
- `BLOCKED`：阻塞原因、已尝试措施和解除条件明确；解除后回到 `DOING` 或 `VERIFYING`。
- `CANCELLED`：记录取消原因和恢复/清理需要，不等同于完成。

空白证据或 SHA 表示尚未产生，不表示 `N/A`。只有经过风险判断确认不需要审查时，RR 才可写 `N/A` 并在任务说明中给出理由。

## P0：关闭 TikTok 人工辅助 v0.1 门禁

除已经取得精确范围、环境、验收步骤、资源和授权并进入执行的事项外，其余事项保持 `BACKLOG`。

| ID | 可验证结果 | 需求/验收或门禁 | 状态 | 分支 | 依赖 | IR | TR | RR | 最终 SHA |
|---|---|---|---|---|---|---|---|---|---|
| MVP-DOMAIN-001 | staging/production 的 OAuth、Webhook、CORS、公开地址、TLS 示例和部署守卫统一使用 `staging.overselfx.com` / `www.overselfx.com` | G0/G1/G2；用户 2026-09-17 域名决定；AC-01～AC-05；`BASE_SHA=9f432c853dc5d31a9c2a013b6769b162934976d4` | DONE | fix/staging-production-domain-overselfx | none | [IR](../records/implementation/IR-MVP-DOMAIN-001-20260917-R01.md) | [TR](../reports/tests/TR-MVP-DOMAIN-001-20260917-R01.md) | [RR](../reports/reviews/RR-MVP-DOMAIN-001-20260917-R01.md) | 10428b4501fd470a5a671676edcdc00e75180844 |
| MVP-STAGING-001 | `staging.overselfx.com` 经新服务器宝塔 TLS、受限 SSH 反向隧道访问旧服务器 Rootless CRM，且 GitLab 与其他公司负载零变化 | [双服务器 Split-Ingress Staging 部署设计](../superpowers/specs/2026-09-19-split-ingress-staging-deployment-design.md) AC-01～AC-10；`BASE_SHA=98414c2b51bfd403365aa6c72e0585f045d4a26a` | DONE | PR #20～#26（已合并） | MVP-DOMAIN-001 | [IR](../records/implementation/IR-MVP-STAGING-001-20260919-R01.md) | [TR](../reports/tests/TR-MVP-STAGING-001-20260919-R01.md) | [RR](../reports/reviews/RR-MVP-STAGING-001-20260919-R01.md) | c0f1e6f0a5c575190b71541be3f67b3163780d61 |
| MVP-STAGING-PROXY-PERSIST-001 | staging 代理的 Nginx bind 来源在 Runner 临时目录清理后仍可重启，且不影响其他业务容器 | G0/G6 运行恢复；AC-01 `deploy`/`rollback` 只从已校验源码包创建唯一持久目录；AC-02 现场 proxy 挂载为持久普通文件且内容 SHA-256 一致；AC-03 再次重启 proxy 后健康和公网接口恢复；AC-04 公司系统 Docker 容器 ID 不变、production 不变；`BASE_SHA=87acfd643720ec2a120ee78b5e57ecaebff8e93d` | DOING | fix/staging-persistent-proxy-source-20261008 | MVP-STAGING-001 | | | required | |
| MVP-EGRESS-001 | TikTok 服务端流量只经 `38.55.145.52` 出站，隧道不可用时失败关闭且不影响现有入口与公司负载 | [TikTok 固定出口设计](../superpowers/specs/2026-09-21-tiktok-fixed-egress-design.md)；G0/G1/G2/G3；`BASE_SHA=99800c3bfac29df31392a05344e7dcb9a2d34fb1`；live staging 门禁 `35806983990` 通过；用户仅限本次 staging 授权镜像复用，详见 R02 | DONE | PR #34～#38 已合并；R02 现场证据入 main `626437e105622e67d622fb38f370586588b85265`；production 未部署 | MVP-STAGING-001 | [IR](../records/implementation/IR-MVP-EGRESS-001-20260923-R02.md) | [TR](../reports/tests/TR-MVP-EGRESS-001-20260923-R02.md) | [RR](../reports/reviews/RR-MVP-EGRESS-001-20260923-R02.md) | 746c10cacf7b2e1e827317e9759e203dc0cc9551 |
| MVP-001 | 轮换并通过密钥管理安全注入 v0.1 所需凭证，确认日志与响应无泄漏 | G0；内部轮换与 staging 外部四项注入已通过；真实平台验收另属 G1/G2/G4，恢复/回滚另属 MVP-008；`TIKTOK_WEBHOOK_SECRET` 仅用于本地 Mock；`BASE_SHA=55395fa4a4f8ddbe72274d95fb6c496827e8e3f0` | DONE | PR #40 已合并；production 未部署 | none | [IR](../records/implementation/IR-MVP-001-20260923-R02.md) | [TR](../reports/tests/TR-MVP-001-20260923-R02.md) | [RR](../reports/reviews/RR-MVP-001-20260923-R02.md) | 4ffb888a6af59a25333d6c984273fd1a89abff09 |
| MVP-OAUTH-REDIRECT-001 | TikTok OAuth callback 快速回跳、后台一次性交换、重复回调去重及低敏状态反馈通过代码和隔离测试 | [获批快速回跳设计](../superpowers/specs/2026-09-24-tiktok-oauth-fast-redirect-design.md)；G1 前置；`BASE_SHA=7adb26927a717b3fca04056e779bd09bd05d9c75`；production 不变 | DONE | PR #53 前后端 CI 通过并合入 main `c72406349c56f55f9e433b64523b3626682c4adb`；现场部署另行验收 | MVP-001, MVP-EGRESS-001 | [IR](../records/implementation/IR-MVP-OAUTH-REDIRECT-001-20260924-R01.md) | [TR](../reports/tests/TR-MVP-OAUTH-REDIRECT-001-20260924-R01.md) | [RR](../reports/reviews/RR-MVP-OAUTH-REDIRECT-001-20260924-R01.md) | 8a1b81f44478f2c71c4f275873cb68d0b8f4528f |
| MVP-OAUTH-REDIRECT-DEPLOY-001 | 合并后的快速回跳镜像仅部署 staging，迁移、健康、重复回调与真实浏览器回跳有现场证据 | G1 前置；用户此前已报告 North America seller/US 授权后自动返回 CRM；2026-10-08 新授权受 TikTok 账号登录问题阻断，历史 Network 303 不算同一 callback 的重放；重复回调与发布终态机器证据仍待整理；production 不变 | BACKLOG | | MVP-OAUTH-REDIRECT-001, MVP-STAGING-001 | | | required | |
| MVP-OAUTH-REAUTH-001 | staging 美国测试店铺一次重新授权完成真实浏览器回跳、一次性任务终态与低敏权限核对，不替代完整 OAuth 部署或 G1 | G1 子集；AC-01 用户确认自动回到 CRM 且当前唯一新 job connected；AC-02 code/state 清空、凭证加密且匹配成功审计一条；AC-03 原用户可读取 job、同店异人 404、探针回滚且审计不变；AC-04 迁移头 `024`、backend/jobs 与公网 ready 健康；`BASE_SHA=fd750c15b6c2970b250de4f7218a4d456a3257aa`；真实 callback 重放、Token 成功刷新、增强物流和 production 不在本任务范围 | DONE | PR #63 前后端 CI 通过、独立只读审查通过并 squash 合入 main `1f1286f8538b1298e91b1be57c2f8f6ccea48940`；仅此窄范围，完整 OAuth 部署和 G1 未签署 | MVP-OAUTH-REDIRECT-001, MVP-STAGING-001 | [IR](../records/implementation/IR-MVP-OAUTH-REAUTH-001-20260928-R01.md) | [TR](../reports/tests/TR-MVP-OAUTH-REAUTH-001-20260928-R01.md) | [RR](../reports/reviews/RR-MVP-OAUTH-REAUTH-001-20260928-R01.md) | fd750c15b6c2970b250de4f7218a4d456a3257aa |
| MVP-READONLY-LOG-001 | 真实 TikTok 只读冒烟的第三方请求日志不泄漏签名 URL/标识，同时保留仅聚合计数的成功输出 | G1 前置日志安全；AC-01 合成签名 URL、店铺/订单标识及异常链不进入脚本输出；AC-02 成功计数 JSON 保留；AC-03 后端质量门禁；`BASE_SHA=c72406349c56f55f9e433b64523b3626682c4adb`；production 不变 | DONE | PR #54 前后端 CI 通过，squash 合入 main `a8e36c5ce8350044d5bd2f088da1aa274acf329d`；本地 1650 passed/18 skipped，独立复审 Critical/Important 0；staging 部署另立门禁 | MVP-001, MVP-EGRESS-001 | [IR](../records/implementation/IR-MVP-READONLY-LOG-001-20260928-R01.md) | [TR](../reports/tests/TR-MVP-READONLY-LOG-001-20260928-R01.md) | [RR](../reports/reviews/RR-MVP-READONLY-LOG-001-20260928-R01.md) | a2f4da8e12ae10efb27adea400f96b9e037cd6ea |
| MVP-002 | 专用真实店铺完成 TikTok OAuth、Scope、Token 生命周期、只读能力与店铺隔离验收 | G1；2026-10-04 自然 Token 刷新成功，见 [低敏证据](../../release/evidence/staging/crm-staging-g1-natural-token-refresh-20261008.json)；同一真实 callback 重放和增强物流 `202604` 仍未通过 | BACKLOG | | MVP-001, MVP-EGRESS-001, MVP-OAUTH-REDIRECT-DEPLOY-001, MVP-READONLY-LOG-001 | | | required | |
| MVP-G1-NONLOG-001 | 在 staging 留存非物流 G1 预检：六项只读、跨店失败关闭、现有 OAuth/Scope 状态与未到期刷新调度；不替代完整 G1 | G1 子集；AC-01 六项只读均执行且仅输出聚合数；AC-02 未提交的合成用户跨店读与授权均拒绝、回滚后不存在；AC-03 核对连接、Scope、密文和审计，不把历史审计冒充当前 OAuth job；AC-04 未到期刷新处理数零且凭证不变；`BASE_SHA=3568f037782a183ea99775515eafe45b5d42fa45`；production 不变 | DONE | PR #61 前后端 CI 通过，独立审查通过并 squash 合入 main `7f580f87f8e35c5949251fb1602280bd1dcd448f`；仅此非物流子集，G1 未签署 | MVP-001, MVP-EGRESS-001, MVP-READONLY-LOG-001 | [IR](../records/implementation/IR-MVP-G1-NONLOG-001-20260928-R01.md) | [TR](../reports/tests/TR-MVP-G1-NONLOG-001-20260928-R01.md) | [RR](../reports/reviews/RR-MVP-G1-NONLOG-001-20260928-R01.md) | 3568f037782a183ea99775515eafe45b5d42fa45 |
| MVP-UI-001 | 修复管理端无店铺加载、表单反馈、渠道授权前置说明及会话筛选后详情不一致；隔离数据浏览器复验 | 用户 2026-09-23 确认的 UI 缺陷修复；AC-01 无店铺不无限加载且指引下一步；AC-02 无效店铺编码在提交前拦截且服务端错误可见；AC-03 渠道、Agent、团队无店铺操作有明确反馈；AC-04 会话筛选后详情与列表一致；AC-05 错误不伪装空数据；`BASE_SHA=98de3732412095d4252ffb3dcd272904b406e4a3` | DONE | PR #43 已 squash 合入 main `c9e49b88f54807f37b72c4c93ad1d66e554acc7d`；CI 前后端通过；staging 部署另见 MVP-UI-DEPLOY-001，production 未部署 | none | [IR](../records/implementation/IR-MVP-UI-001-20260923-R01.md) | [TR](../reports/tests/TR-MVP-UI-001-20260923-R01.md) | [RR](../reports/reviews/RR-MVP-UI-001-20260923-R01.md) | 8c13a9f1df0e71e3c3e7bb7916a1f1422b5a1820 |
| MVP-UI-DEPLOY-001 | 已合并 UI 修复的不可变前端/后端镜像在 staging 运行健康，旧检索摘要仅按本次明确授权保留 | AC-01 镜像绑定远端 main；AC-02 staging 门禁与公网健康通过；AC-03 GitLab/入口隔离及恢复点保留；AC-04 版本偏差和未测项如实记录；`BASE_SHA=58263b1108e96d0d6afa21a6bbfae271fb5c7a87` | DONE | PR #45 已合入 main `ef62b4371736b144ef447352667d6854fb5dcaa8`；staging 门禁通过，production 未部署 | MVP-UI-001, MVP-STAGING-001 | [IR](../records/implementation/IR-MVP-UI-DEPLOY-001-20260923-R01.md) | [TR](../reports/tests/TR-MVP-UI-DEPLOY-001-20260923-R01.md) | [RR](../reports/reviews/RR-MVP-UI-DEPLOY-001-20260923-R01.md) | 58263b1108e96d0d6afa21a6bbfae271fb5c7a87 |
| MVP-UI-CACHE-001 | 管理端 HTML 不跨版本长期缓存，已发布修复不会因旧页面缓存失效；指纹静态资源缓存不变 | 用户 2026-09-24 确认；AC-01 生产构建 HTML 返回 no-store；AC-02 无店铺营销页显示创建店铺指引；AC-03 指纹 JS 仍为 immutable；AC-04 本地回归与构建通过；`BASE_SHA=7890f4acf12e956544c0acbd34033857dce88d81` | DONE | PR #47 CI 通过并 squash 合入 main `118ba775e291b88998bd033b7bca3410e29f8b88`；production 不部署 | MVP-UI-001, MVP-UI-DEPLOY-001 | [IR](../records/implementation/IR-MVP-UI-CACHE-001-20260924-R01.md) | [TR](../reports/tests/TR-MVP-UI-CACHE-001-20260924-R01.md) | [RR](../reports/reviews/RR-MVP-UI-CACHE-001-20260924-R01.md) | 7617647965278198b2712b678007bc3ad6fbbe98 |
| MVP-UI-CACHE-DEPLOY-001 | 合并后的 HTML 缓存修复以不可变前后端镜像仅部署 staging，现场精确路径不再命中旧页面，且公司负载与 production 不变 | 用户 2026-09-24 确认；AC-01～AC-04；`BASE_SHA=118ba775e291b88998bd033b7bca3410e29f8b88`；首次全新摘要部署因检索镜像拉取停滞在切换前取消，用户仅授权**本次 staging** 复用旧检索摘要并记录依赖锁偏差。混合摘要预检 `35953530870`、部署 `35953792293` 通过；PR #49/#50/#51 已合并 main `8038ad99c3ceb47787bb29b489611a28d012c575`；staging vhost 精确 HTML no-store、JS immutable，双机最终入口验证器通过，公司负载/其他站点摘要不变。见 [终态证据](../../release/evidence/staging/crm-staging-html-cache-rollout-20260924.json) 与 [首次尝试](../../release/evidence/staging/crm-staging-html-cache-rollout-attempt-20260924.json) | DONE | 仅 staging；production 不部署；带身份现场全按钮与真实 TikTok 不在本任务结论；旧检索例外不得延续 | MVP-UI-CACHE-001, MVP-STAGING-001 | [IR](../records/implementation/IR-MVP-UI-CACHE-DEPLOY-001-20260924-R01.md) | [TR](../reports/tests/TR-MVP-UI-CACHE-DEPLOY-001-20260924-R01.md) | [RR](../reports/reviews/RR-MVP-UI-CACHE-DEPLOY-001-20260924-R01.md) | a9d36c04fb8f71d163deabc22d64b5ce5efbe3e3 |
| MVP-003 | Partner Center 完成真实 Webhook 投递、签名、幂等、重试、乱序与审计验收 | G2 | BACKLOG | | MVP-001, MVP-002 | | | required | |
| MVP-004 | 低风险会话完成一次人工确认普通文本发送，并验证成功、`unknown` 对账和禁止盲重试 | G3 | BACKLOG | | MVP-002 | | | required | |
| MVP-005 | 用冻结低敏数据完成 DeepSeek 建议质量、DLP、结构化声明、引用与转人工复测 | G4 | BACKLOG | | MVP-001 | | | required | |
| MVP-006 | 完成 50 客户端 SSE 容量门禁并记录延迟、错误、断连、队列和资源证据 | G5 | BACKLOG | | MVP-005 | | | required | |
| MVP-007 | 连续运行五日并达到 99.5% 可用性，验证告警、积压、资源和故障恢复 | G6 | BACKLOG | | MVP-002, MVP-003, MVP-004, MVP-005, MVP-006 | | | required | |
| MVP-008-RESTORE-001 | 仅在 staging 对 PostgreSQL 与 MinIO 建立受限备份并恢复至隔离目标，验证迁移、数据与对象完整性且活动服务及公司负载不变；不替代实际镜像回滚 | G0 子项；用户 2026-09-29 确认隔离演练；AC-01 备份受限且可读取；AC-02 隔离 PostgreSQL 恢复并核对 `024`、表和行数；AC-03 隔离 MinIO 恢复并核对对象数/校验值；AC-04 活动数据、容器、健康和公司负载前后不变（容器无演练前 ID 快照，结论限定为运行/启动时间）；`BASE_SHA=b08fc76b2a9c6de04d6daf7e1e0c2ed784ab5184`；对象业务桶为空，另用隔离合成对象验证字节恢复；production 不变 | DONE | PR #65 前后端 CI 通过、独立只读复审及用户人工审阅通过，squash 合入 main `ad86ce141c1a467b535378665c0e71179036f3a6`；仅关闭隔离恢复子项，实际镜像回滚/G0/production 未通过 | MVP-001 | [IR](../records/implementation/IR-MVP-008-RESTORE-001-20260929-R01.md) | [TR](../reports/tests/TR-MVP-008-RESTORE-001-20260929-R01.md) | [RR](../reports/reviews/RR-MVP-008-RESTORE-001-20260929-R01.md) | 675b362cd7b0a8c69384a38815ae3b2351f5b6db |
| MVP-008 | 完成数据库、对象存储恢复与上一版本实际回滚演练 | G0；隔离 PostgreSQL/MinIO 恢复由 MVP-008-RESTORE-001 通过；PR #83 的可校验 OCI 续传已合入 main `3b091055908a4fd374dc95518dfd31d8d8960a47`。六摘要预取 `36699523917`、候选预检 `36700668599`、候选部署 `36701049769`、上一版三摘要实际切回 `36701815122` 和候选切返 `36702556391` 均通过；切返后独立核对候选三摘要、迁移头 `024`、11 容器和三公网健康 200。低敏原始 artifact SHA-256 汇总见 [G0 证据](../../release/evidence/staging/crm-staging-mvp008-g0-20260930.json)。production 未部署；G1～G6 独立验收。PR #84 前后端 CI 通过并 squash 合入 main `8fae4fb85c4ed9c8cdf862f99d839c3de60e55ab`。 | DONE | PR #84 已合并；production 未部署 | MVP-001, MVP-008-RESTORE-001 | [IR](../records/implementation/IR-MVP-008-20260930-R01.md) | [TR](../reports/tests/TR-MVP-008-20260930-R01.md) | [RR](../reports/reviews/RR-MVP-008-20260930-R01.md) | 58f095b730022fa5f792a751f991aca2ee1d5fce |
| MVP-009 | 汇总 G0～G6 证据并取得最终 Go/No-Go 决定 | G8 | BACKLOG | | MVP-001～MVP-008 | | | required | |

## P1：v0.1 之后

这些主题明确不属于当前 v0.1 放行范围。开始前必须建立独立需求、验收、安全边界和门禁，不能复用 v0.1 的限定结论。

| ID | 可验证结果 | 需求/验收或门禁 | 状态 | 分支 | 依赖 | IR | TR | RR | 最终 SHA |
|---|---|---|---|---|---|---|---|---|---|
| MVP-010 | 建立 Shopee 与 Amazon 真实授权、消息和订单/物流适配的独立产品与技术基线 | 新需求与门禁 | BACKLOG | | MVP-009 | | | required | |
| MVP-011 | 建立生产翻译质量、多语言安全和数据边界的独立验收 | 新需求与门禁 | BACKLOG | | MVP-009 | | | required | |
| MVP-012 | 建立公开自动回复、主动营销与高风险写入的审批、频控、幂等、审计、容量和回滚基线 | G7；新需求与门禁 | BACKLOG | | MVP-009 | | | required | |
| MVP-013 | 根据真实流量复核 BGE/DeepSeek 容量与成本并形成后续容量决定 | 新需求与门禁 | BACKLOG | | MVP-006, MVP-007 | | | required | |

## P2：仓库与文档维护

| ID | 可验证结果 | 需求/验收或门禁 | 状态 | 分支 | 依赖 | IR | TR | RR | 最终 SHA |
|---|---|---|---|---|---|---|---|---|---|
| DOCS-001 | 按职责域分类 `docs/` 当前文档并修复活动引用，不改变项目事实 | 本设计规格的 7 项验收标准；`BASE_SHA=318d0e0272a580e0eb36f17e6188944276d2c9be` | DONE | codex/docs-classify-documentation | none | N/A | N/A | N/A（纯文档路径重组） | 35e41ee641e15ce124e3ad09a27f3d8bef1caeec |
| GOV-001 | PR 人工审阅改为按需合并门禁，同步 Agent、工程、治理与 CODEOWNERS 说明，保留适用 CI、代码审查、安全检查及高风险批准 | 用户 2026-09-29 明确决定；`BASE_SHA=ff1565fa78810bd10bee5dd6dc9098ef117c7916`；AC-01 三处当前规则及 CODEOWNERS 说明一致；AC-02 人工审阅不再是统一前置；AC-03 其他批准边界不变 | DONE | PR #69 已通过双 CI 和独立只读复核，squash 合入 main `4cf16bb6f9b3a7af6287f0c71aff5b0d08e58214` | none | N/A（纯规则文字） | N/A（静态文档校验与双 CI 通过） | N/A（未修改运行行为；独立复核无剩余问题） | a023092112e506cf235b2ed46d6abba3449b51ed |
| REPO-001 | 将全部工程代码与运行资产迁入 `src/`，并通过完整构建和实际启动验证 | `src/` 工程根迁移设计的 9 项验收标准；`BASE_SHA=6b726a32502a364040ccf0a0b251a320d379ee7d` | DONE | codex/src-layout-migration | none | [IR](../records/implementation/IR-REPO-001-20260916-R01.md) | [TR](../reports/tests/TR-REPO-001-20260916-R01.md) | [RR](../reports/reviews/RR-REPO-001-20260916-R01.md) | a8c15b516052dc8733ec3764d4d0e6d606ddc11e |
| MAINT-CLEANUP-20260916-001 | 根目录本地生成残留按 `CLEANUP-20260916-001` 隔离、验证并保留可恢复性 | [清理批次](../operations/cleanup/CLEANUP-20260916-001.md)；`BASE_SHA=c9128a5b2e1b6d102d90699b6b50da84a63820df` | DONE | docs/root-hygiene-cleanup-20260916 | none | N/A（本地非跟踪残留） | N/A（静态结构验证） | N/A（低风险可恢复隔离；独立审查问题已关闭） | 848c134f0d99c710b9375b4d992c6a4bb249b32a |
| MAINT-CLEANUP-20260916-002 | 将主 checkout 中旧 `src/backend/tests/` pytest 缓存按 `CLEANUP-20260916-002` 可恢复隔离，并恢复集中式布局守卫 | [清理批次](../operations/cleanup/CLEANUP-20260916-002.md)；`BASE_SHA=bec5d290b75ad14df954d9f4732c7934c8157549` | DONE | fix/centralized-test-layout-cache | TEST-001 | N/A（本地被忽略测试残留） | N/A（合并后全量门禁记录在批次） | N/A（低风险可恢复隔离；独立审查 Critical/Important 为 0） | 43b9ea86b674e7ea563738a16dac686748463fc9 |
| MAINT-CLEANUP-20260921-003 | 将入口服务器 `/root` 下的 CRM staging 备份、退役缓存和误生成探针文件迁入 `/var/backups` 与受控隔离目录，保持线上入口零变化和可恢复性 | [清理批次](../operations/cleanup/CLEANUP-20260921-003.md)；`BASE_SHA=79fa405f5fd0cea6bdf9b3cf1c0d88fa6b72166e` | DONE | PR #28（已合并） | MVP-STAGING-001 | N/A（线上文件布局清理；事实记录在清理批次） | N/A（现场验证记录在清理批次） | N/A（同文件系统可恢复移动；不删除对象） | 85602c3c2702c33cbf00cf554afdfdc8c5ab0aa7 |
| MAINT-CLEANUP-20260921-004 | 删除六个已合并、远端分支已删除且无独有交付内容的本地 worktree 与对应本地短期分支 | [清理批次](../operations/cleanup/CLEANUP-20260921-004.md)；`BASE_SHA=6147d3d9f89011dc52e313da89080b3ca7d39f47` | DONE | PR #32（已合并） | none | N/A（Git 工作副本清理） | N/A（使用合并状态、全量门禁和清理后 Git 复核） | N/A（用户明确授权的已合并本地分支清理） | 6b1d929f53c8bef6c4031fb3be42c29e591848ab |
| MAINT-CLEANUP-20260928-001 | 仅清理截图中已合并且无唯一内容的 OAuth 代码本地 worktree 与对应本地分支；其余未完成或含密钥的目录保留 | [清理批次](../operations/cleanup/CLEANUP-20260928-001.md)；`BASE_SHA=c99df142bb987a8afd65410998298e39b0ae50a7` | DONE | PR #57 已合并 main `c64572492c72053b5722c6a859634891da48c2b5` | none | N/A（Git 工作副本清理） | 精确路径与分支消失、JSON/diff 校验、PR #57 双 CI 通过且合并 | N/A（用户明确要求清理所示分支） | 73222bde22e21d6a9823a506b47150aea90dc3d9 |
| MAINT-CLEANUP-20260928-002 | 清理 PR #52 已合并的 HTML 缓存本地工作树、分支及获准删除的诊断文件和两份重复 SSH 私钥副本，原始密钥不动 | [清理批次](../operations/cleanup/CLEANUP-20260928-002.md)；`BASE_SHA=289f1981ec3342e7e9cab8787b173305a0f4a5ae` | DONE | PR #59 已合并 main `f3a83c518d0934576a3f13a26c76d45df3b5cc9d` | none | N/A（Git 工作副本清理） | 精确目录与分支消失、原始密钥哈希未变、JSON/diff 校验、PR #59 双 CI 通过且合并 | N/A（用户明确授权精确副本和本地证据删除） | 8d05447025d6ba80374297b0e68a257cb8fa49ac |
| TEST-001 | 所有测试源码、AI eval 数据与普通结果统一迁入 `src/tests/` 并按职责分类，所有现有质量入口保持可用 | [统一测试目录设计](../superpowers/specs/2026-09-16-centralized-test-layout-design.md) 的 10 项验收标准；`BASE_SHA=17bb9bf9501ead60aafe8eed6bddc331f26c43f0` | DONE | feature/unified-test-layout | none | [IR](../records/implementation/IR-TEST-001-20260916-R01.md) | [TR](../reports/tests/TR-TEST-001-20260916-R01.md) | [RR](../reports/reviews/RR-TEST-001-20260916-R01.md) | 4cd66643540d7e70acaeae2229a0f10620f7b6ae |

## 维护规则

1. 开始任务时只选择依赖已满足的最高优先级 `READY` 项，并在同一次更新中写入分支和基线。
2. 范围或验收改变时先更新 `docs/product/PRODUCT.md` 或相关当前事实文档，再更新本表。
3. 失败验证回到同一任务和分支修复，不新建重复任务制造“通过”。
4. 实际清理使用 `MAINT-CLEANUP-YYYYMMDD-NNN`，并链接精确 `CLEANUP-YYYYMMDD-NNN` 批次。
5. 超过约 20 个活动任务或进入多人长期协作后，才评估独立任务文件或外部任务平台；在此之前不扩展状态系统。
