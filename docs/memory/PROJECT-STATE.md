# 项目状态与恢复入口

本文件是跨 Codex 会话恢复项目所需的精简摘要，不复制 `../tasks/TASKS.md` 的任务状态、`../quality/TEST-STATUS.md` 的测试结论或 `../operations/RELEASE-GATES.md` 的门禁正文。恢复工作时先读本文件，再按链接读取事实源。

2026-09-28 目录卫生补记：`MAINT-CLEANUP-20260928-001` 已移除 PR #53 合并后的 OAuth 代码本地工作树与分支，清理记录由 PR #57 合入 `main`；`MAINT-CLEANUP-20260928-002` 已按用户精确授权移除 PR #52 合并后的 HTML 缓存工作树、两份重复 SSH 私钥副本与本地诊断资料，原始密钥不变，清理记录由 PR #59 合入 `main`。另三个截图工作树因开放 PR 或未完成现场验收而保留。批次见 [`../operations/cleanup/CLEANUP-20260928-001.md`](../operations/cleanup/CLEANUP-20260928-001.md)、[`../operations/cleanup/CLEANUP-20260928-002.md`](../operations/cleanup/CLEANUP-20260928-002.md)。下方历史部署快照不是当日运行状态，以当前任务表与发布证据为准。

## 当前状态

```text
Project phase: ACTIVE
Governance tier: STANDARD
Repository identity: origin=ssh://git@ssh.github.com:443/CP11-gh/CRM.git
Primary branch: main
Working branch at this snapshot: docs/mvp005-g4-diagnostics-index-current-20261012
Governance base SHA: 5c4d5032252abeb80774f80281e5125398b8b04d
CANDIDATE_SUBJECT_SHA: 50efe5241f7779f5608f989f536473f1eca38b50
EVIDENCE_HEAD_SHA: READ_AT_GATE
Workspace hygiene: ATTENTION — `CLEANUP-20260921-004` 已删除六个已合并本地 worktree；既有隔离保留期、两份 MVP-001 root-only 恢复副本和其他忽略测试材料不在本批次范围
```

当前工程根为 `src/`，测试资产集中在 `src/tests/`。`MVP-STAGING-001` 已完成双服务器 split-ingress 真实部署：`38.55.145.52` 只承担宝塔 Nginx/TLS 和回环 `18080`，`192.168.110.210` 的 `crmdeploy` Rootless CRM 只发布回环 `18081`；DNS、Let's Encrypt 证书、迁移头、公网健康、隧道恢复和公司负载零变化已验收。最终候选 subject 为 `c0f1e6f0a5c575190b71541be3f67b3163780d61`，与已部署运行配置 `98460796...` 的受审运行资产零差异；终态证据已通过 PR #26 合入 `main`，任务状态为 `DONE`，production 未部署。`EVIDENCE_HEAD_SHA` 必须在门禁或交接时从 Git 现场读取，不在仓库中自指回填。

2026-10-12 G4 恢复点：用户批准先建立冻结独立集的 staging 一次性评测入口；PR #113 候选 subject `5ca815bbb342042572d7251f1209e72bb517c5bb` 提供 `prepare/live` 两模式，`prepare` 不调用 DeepSeek，`live` 的 34 条合成数据外发与费用尚未单独授权。聚焦测试 33 passed，工作流 YAML 与 PowerShell 静态解析通过；staging `prepare` 和真实 `live` 均未执行。过程 [IR](../records/implementation/IR-MVP-005-20261012-R01.md)/[TR](../reports/tests/TR-MVP-005-20261012-R01.md)/[RR](../reports/reviews/RR-MVP-005-20261012-R01.md) 仅覆盖入口；本分支三份索引为 `CANDIDATE_VIEW`，合入后须从 main 复核并重建为 `CURRENT`。G4 仍未通过，production 不变。

同日 PR #113 已通过前后端 CI 并合入 main `9d7b08e91069e114c7b6f6295b7ecafcdb723520`；首次 `prepare` [#38200077151](https://github.com/CP11-gh/CRM/actions/runs/38200077151) 的全仓 Git fetch 卡住约 3 分 46 秒后受控取消，预检和模型调用未开始。R02 候选 `6cec314cce39f063820e496a00a4b7a78627d2f9` 改为精确提交的六文件 GitHub API/Blob SHA 读取，本机原样步骤约 10 秒通过，冻结集 SHA-256 匹配；staging 仍须重跑 `prepare`。见 [IR R02](../records/implementation/IR-MVP-005-20261012-R02.md)/[TR R02](../reports/tests/TR-MVP-005-20261012-R02.md)/[RR R02](../reports/reviews/RR-MVP-005-20261012-R02.md)。真实 `live` 无授权且未执行。

PR #114 前后端 CI 通过并合入 main `2f0c57a7086b31e2b9ee80321152be2a426ebe2a`。第二次 `prepare` [#38201088441](https://github.com/CP11-gh/CRM/actions/runs/38201088441) 在 Runner 8 秒内取得六文件，但 `docker cp` 后的清单由 backend 非 root 用户读取时报 `PermissionError`；预检在此停止，未调用 DeepSeek。R03 候选 `a06c4305d31492b9a254b3b5397e282316b51304` 仅给本次生成的两份冻结合成输入 `0644` 读取位，仍待现场验证。见 [IR R03](../records/implementation/IR-MVP-005-20261012-R03.md)/[TR R03](../reports/tests/TR-MVP-005-20261012-R03.md)/[RR R03](../reports/reviews/RR-MVP-005-20261012-R03.md)。G4 未通过。

PR #115 前后端 CI 通过并合入 main `9638222b9e552b32f05b895c58fbc06bc7e0835e`。第三次 `prepare` [#38201755776](https://github.com/CP11-gh/CRM/actions/runs/38201755776) 成功：六文件、冻结独立集 36 条、运行 backend 摘要、容器配置和低敏 artifact 均通过，`live` 跳过，Provider 调用数为 0。artifact ID `11725641941`，JSON SHA-256 `b3e29a8cc162549786e6f92cab461fbf21d9951bf9c4d21faf39c7dd84f803dc`；[入库证据](../../release/evidence/ai/crm-staging-g4-prepare-20261012.json)与下载件哈希一致。R04 [IR](../records/implementation/IR-MVP-005-20261012-R04.md)/[TR](../reports/tests/TR-MVP-005-20261012-R04.md)/[RR](../reports/reviews/RR-MVP-005-20261012-R04.md)仅关闭准备入口；真实 DeepSeek 质量、四个历史失败复测仍待单独授权，G4 未通过。

R04 证据 PR #116 通过前后端 CI 并合入 main `8b3057a34b832094449dc5bda34ce50983ed6a0e`。从该 main 的 IR、TR、RR 各 31 份源记录逐项复核三个索引：每类 31 条，缺失/重复 ID 均为零，状态与 subject SHA 不一致均为零。此索引收尾分支据此将三个派生视图恢复为 `CURRENT`，没有修改源记录或 G4 结论。

2026-10-12 G4 新恢复点：用户明确批准一次 34 条合成数据的真实 DeepSeek 评测。main `cd21527e129aa2a3f03d73e2b90b784a18e5eca0` 上 [`live` #38208426125](https://github.com/CP11-gh/CRM/actions/runs/38208426125) 成功，34 条 Provider 样本、2 条故障注入，33/36=91.67% 超过预设 85%；危险逃逸、合法误拦与 Provider 失败均 0。历史翻译两条恢复，条件与引用两条仍命中禁用词，新增售后声明不匹配一条。原样[低敏报告](../../release/evidence/ai/crm-staging-g4-live-20261012.json) JSON SHA-256 `8ab440f99253142b9303dd90ab9df8dd7b23ffb2aecb1c5f7d70fdfe2d4fa946`；[IR R05](../records/implementation/IR-MVP-005-20261012-R05.md)/[TR R05](../reports/tests/TR-MVP-005-20261012-R05.md)/[RR R05](../reports/reviews/RR-MVP-005-20261012-R05.md)。证据 PR #118 已合入 main `105a3d0b1a925cfc13d63645cf3364f119595934`；从该 main 的 IR/TR/RR 各 32 份源记录核对索引，无缺失/重复，状态及 SHA 均一致，当前索引为 `CURRENT`。三条失败需逐项诊断，G4 仍部分通过，production No-Go。

2026-10-12 G4 低敏诊断收尾：用户批准仅给失败样本增加声明不匹配字段名、禁用词冻结序号及引号/禁止用语布尔提示；subject `50efe5241f7779f5608f989f536473f1eca38b50` 保留既有判分、85% 门槛和冻结数据，工作流增加嵌套白名单。合成测试与完整后端回归已执行，见 [IR R06](../records/implementation/IR-MVP-005-20261012-R06.md)/[TR R06](../reports/tests/TR-MVP-005-20261012-R06.md)/[RR R06](../reports/reviews/RR-MVP-005-20261012-R06.md)。PR #120 前后端 CI 通过并 squash 合入 main `5c4d5032252abeb80774f80281e5125398b8b04d`；从该 main 的 IR/TR/RR 各 33 份源记录复核，三份索引均无缺漏、重复、状态或 SHA 偏差，已恢复为 `CURRENT`。未调用 DeepSeek、发布镜像或部署 staging；旧报告不可回填，G4 仍部分通过。

2026-10-09 G2 代码预备 PR #101、只读诊断 PR #102 和一次性订阅工具 PR #103 已合入 `main` `253a6cf0f563aae85b15ea7447a3589f203484b1`；单后端镜像发布、六角色预取和 staging G2 模式部署通过，消息写入、高风险写入、自动回复仍关闭。用户精确授权后仅执行一次 `NEW_MESSAGE` 订阅 PUT；写后 GET 与独立只读 GET 均确认订阅数 1、目标地址匹配数 1、其他地址数 0，见[低敏订阅证据](../../release/evidence/staging/crm-staging-g2-subscription-confirmed-20261009.json)。当时尚无官方真实事件投递证据，`MVP-003` 仍在 `DOING`，G2 未通过，production 不变。过程记录 [IR](../records/implementation/IR-MVP-003-20261009-R03.md)、[TR](../reports/tests/TR-MVP-003-20261009-R03.md)、[RR](../reports/reviews/RR-MVP-003-20261009-R03.md)是订阅执行前的历史快照；三个记录索引已从 main 的 24 份源记录逐项核对为 `CURRENT`。

2026-10-09 G3 顺序例外：用户决定在 G2 真实投递阻塞期间先进入 G3；G2 仍为必过项。main `0f80d3f804b425b8aca53e1f8b34939e52b6e89d` 上三组人工发送、领域和工具执行聚焦测试本轮 55 passed、1 warning；staging G2 overlay 的真实普通消息写仍为 false，没有受控测试买家会话，因此未发送任何外部消息，也不能签署 G3。实施范围与解除条件见[TASKS](../tasks/TASKS.md)及[RELEASE-GATES](../operations/RELEASE-GATES.md)。

2026-10-09 G3 后续安全补丁以 main `9a6d1db4816d352cf14d79ed49fcb43c8e7ecd1f` 为基线，在隔离 PostgreSQL 红测复现遗留 `processing` 未拦截下一次真实发送，并加入同店铺行锁和 `processing/unknown` 双状态阻断。修复后的全新隔离库完整后端回归 `1726 passed, 3 skipped, 2 warnings`；候选尚未发布镜像或部署 staging，真实写保持关闭。遗留 `processing` 的安全人工恢复与受控会话现场发送仍缺证据。

本补丁的 [IR](../records/implementation/IR-MVP-004-20261009-R01.md)、[TR](../reports/tests/TR-MVP-004-20261009-R01.md)、[RR](../reports/reviews/RR-MVP-004-20261009-R01.md)绑定 subject `9ca4eea828f851b76b0fc5e05c750bea4ee80903`；PR #109 已 squash 合入 main `1eda268cd1f529d36ee53c0e44243ffeba33ba7f`，三个派生索引从主分支源记录核对为 `CURRENT`。任务仍为 `DOING`，G3 未关闭。

2026-10-10 G3 安全补丁从 main `6e975148650bfd8e6cb0b7980b86554345caf5d0` 单独发布后端并部署 staging：镜像、六角色预取、G2 模式预检/部署均通过；迁移头、固定出口、三个公网健康和运行后端摘要已核对。独立只读观察 `NEW_MESSAGE=0`、入站消息 0；真实普通消息写仍关闭，没有向买家发送测试消息。见[低敏现场证据](../../release/evidence/staging/crm-staging-g3-backend-rollout-20261010.json)与 [IR R02](../records/implementation/IR-MVP-004-20261010-R02.md)/[TR R02](../reports/tests/TR-MVP-004-20261010-R02.md)/[RR R02](../reports/reviews/RR-MVP-004-20261010-R02.md)。遗留 `processing` 恢复路径与受控买家会话仍缺，G3 未通过。

该部署记录由 PR #111 合入 main `d4a71aeb39b379ceea9a348938201d5616a4d2d5`；从该主分支的 27 份 IR、27 份 TR 和 27 份 RR 源记录逐项核对索引 ID 一一对应，本索引收尾分支将三个派生视图恢复为 `CURRENT`。此记录只改变文档索引，不改变已运行镜像或门禁结论。

2026-10-09 最新 G2 触发阻塞：用户报告电脑与手机买家侧都没有商家聊天入口，Seller Center 的 Customer Messages 存在，但没有受控测试买家的现成会话。既有 G1 低敏证据确认 `seller.customer_service` Scope 和真实会话只读查询；平台端缺入口的具体原因仍未确定。main `745d79f6cacfdb0b1356d2c73aa86928667d7193` 上只读工作流 `37892709909` 于 06:17Z 再确认 `NEW_MESSAGE=0`、入站消息 0，见[最新低敏复核](../../release/evidence/staging/crm-staging-g2-no-trigger-20261009.json)。任务状态以[TASKS](../tasks/TASKS.md)为准；解除条件为平台给出可用测试路径或取得受控真实买家入站消息，production 不变。

PR #104 将订阅事实与当时的索引合入 main `9f474243c70e0b52717e0c159457c525c78acd23`；PR #105 的只读事件观测工具随后合入 main `8e1d3cf74ef0cbec2e6c172d620f4cdba66878fe`。现场工作流 `37883016283` 核对运行后端摘要后得到零事件、零入站消息的低敏基线，见[基线证据](../../release/evidence/staging/crm-staging-g2-event-baseline-20261009.json)。尚无真实事件，G2 未通过；本分支从 main 的 25 份源记录重建三个 `CURRENT` 索引。过程记录见 [IR R04](../records/implementation/IR-MVP-003-20261009-R04.md)、[TR R04](../reports/tests/TR-MVP-003-20261009-R04.md)、[RR R04](../reports/reviews/RR-MVP-003-20261009-R04.md)。

`MVP-OAUTH-REDIRECT-001` 已由 PR #53 合入 `main`。用户重新选择 North America seller 与 US 后完成 TikTok 授权，成功页自动返回 CRM；此前卖家类型拒绝系操作选择错误，不再作为当前阻塞。现场只读预检中旧版物流 `202309` 成功，增强物流 `202604` 返回业务码 `11007009`，含义未确认，不能将两者混同；Token 生命周期、店铺隔离和重复回调现场证据仍未关闭 G1。production 未变。

`MVP-READONLY-LOG-001` 源码已由 PR #54 合入 main；staging 部署和增强物流失败的独立记录仍在 PR #56 草稿中。2026-09-28 本轮非物流预检在现有 staging 后端执行六项真实只读查询成功，未提交合成用户跨店读/OAuth 发起均 404，当前 connected 渠道的 Scope、密文和未到期刷新调度核对通过；后端本机 1650 passed/18 skipped。08:00:03Z 盘点时 OAuth job 为零，后续复核已见新 job；授权审计与该初次零值均不能证明新任务终态，成功刷新和 `202604` 增强物流仍未过。证据见下文 `MVP-G1-NONLOG-001`，G1 保持部分通过，production 不变。

`MVP-OAUTH-REAUTH-001` 本次 staging 事实：用户确认美国测试店铺授权后自动返回 CRM 并显示已连接；08:00Z 后唯一新 OAuth job 已完成为 connected、code/state 清空，同一发起用户/店铺/渠道的成功审计一条；原用户可重复读取状态，同店异人 404，合成用户已回滚。运行库迁移头 `024_tiktok_oauth_jobs`，backend/jobs 与公网 ready 健康；OAuth 聚焦 36 passed。首次权限探针在回滚后因 detached ORM 对象退出 1，修正复测通过。真实 callback 重放和 Token 成功刷新仍未验，G1/production 不放行；低敏证据见下文记录入口。

`MVP-008-RESTORE-001` 的 2026-09-29 staging 隔离恢复已现场执行：PostgreSQL 备份恢复后 `024`、29 表/85 行逐表计数一致；MinIO 原桶为空，隔离实例中用合成对象验证第二次备份恢复后字节/SHA 一致。临时数据库/容器/卷/网络已移除，受限备份保留；公司系统 Docker 基线及三个公网健康未变。用户人工审阅、独立只读复审与前后端 CI 通过后，证据由 PR #65 合入 main `ad86ce141c1a467b535378665c0e71179036f3a6`；仅隔离恢复子项可标记 DONE，兼容上一版镜像实际回滚和 G0/production 仍未通过。

`MVP-008` 早期预取连续受 GHCR/CDN TCP 重置和 Runner 自动更新超时阻断；PR #79～#83 形成分层检索镜像、Runner 2.337.0 恢复及可校验 OCI 续传。历史失败运行与原因见 `../operations/DEPLOYMENT.md`，不得将其当作当前门禁状态。

2026-09-30 已完成六摘要预取 `36699523917`、候选预检 `36700668599`、候选部署 `36701049769`、上一版三镜像实际切回 `36701815122`、候选切返 `36702556391`。切返后独立核对候选三摘要、11 个容器、数据库迁移头 `024`、三个公网健康 200 及固定出口；Docker 配置原始 SHA 恢复，环境文件 `0600` 恢复副本保留。原始 artifact 摘要见 `../../release/evidence/staging/crm-staging-mvp008-g0-20260930.json`。G0 的 staging 恢复/回滚证据已齐；G1～G6、G8 和 production 未放行。

2026-10-02 恢复点：G1 真实 callback 重放的低敏验收流程已由 PR #86 合入 `main=c707731c0d09b610938585088653875a0a377063`，见 [`../operations/RELEASE-GATES.md`](../operations/RELEASE-GATES.md)。同日 staging 11 个 CRM 容器运行，过去 24 小时新增 OAuth job 与授权/刷新审计均为零；现有访问 Token 到期时间为 2026-10-05T10:05:17Z，按当前提前一天的配置，自然刷新窗口约从 2026-10-04T10:05:17Z 开始。真实重放、成功刷新和增强物流 `202604` 仍未取得通过证据；G1 维持部分通过。

2026-10-08 恢复点：自然 Token 刷新已由后台 job 于 10-04T10:05Z 真实成功完成，渠道保持 connected，低敏证据见 [`../../release/evidence/staging/crm-staging-g1-natural-token-refresh-20261008.json`](../../release/evidence/staging/crm-staging-g1-natural-token-refresh-20261008.json)。同日发现固定出口 helper 自 10-06T18:01Z 退出，Docker 最后错误为 systemd cgroup scope 创建超时；仅重启该既有容器后健康，应用 SOCKS5H 实测仍从 `38.55.145.52` 出站，见 [`../../release/evidence/staging/crm-staging-tiktok-egress-recovery-20261008.json`](../../release/evidence/staging/crm-staging-tiktok-egress-recovery-20261008.json)。历史 Network 303 被排除为本次重放证据；新的 OAuth 发起未收到 callback，用户报告 TikTok 账号无法登录。G1 继续部分通过，G6 的五日稳定性不得包含本次出口中断。

同日 staging 全容器重启暴露 proxy 配置 bind 来源在已清理的 Runner 临时目录：proxy 首次重启失败且公网 ready 返回 502。用哈希一致的持久受审源码恢复原挂载文件后，PR #89 改为从持久目录部署；`main=dcddb26cbb6ecc92db30a11a2f504d034e6ec048` 的预检/部署 `37716193186`/`37716402745` 通过，作业结束后再次重启 proxy 健康，公网登录和三个健康接口 200，固定出口仍为 `38.55.145.52`，同机系统 Docker 容器 ID 不变。低敏证据见 [`../../release/evidence/staging/crm-staging-proxy-persistent-source-20261008.json`](../../release/evidence/staging/crm-staging-proxy-persistent-source-20261008.json)。用户新截图显示已进入 TikTok 商家中心，但授权页提示“连接失败”；CRM 起始链接仅含 `service_id`/`state`，尚无证据说明平台页失败原因或收到新的 callback，不复用截图中的状态参数。

2026-10-08 后续用户重新授权成功；现场在 02:30Z 后新增一个 `connected` OAuth job，code/state 清空、匹配成功授权审计一条，所需 Scope、加密凭证与公网 ready 均正常。代理在 03:13Z 记录两次 callback 303；尚无用户浏览器 Network 的同一请求受控重放证据，因此 G1 继续部分通过。见 [低敏复授权证据](../../release/evidence/staging/crm-staging-g1-oauth-reauth-20261008.json)，production 不变。

同日 03:48Z 另一轮授权发起返回 200，但截至 04:05Z 公网入口没有收到有效 callback，job 与成功审计未增加，原渠道的 TikTok 已授权店铺只读查询仍成功；内置浏览器自动化的 `ERR_BLOCKED_BY_CLIENT` 也出现在服务器实际返回 200/422 的无参数诊断请求上，不能据此判定用户回调被浏览器拦截。见 [低敏失败证据](../../release/evidence/staging/crm-staging-g1-oauth-no-callback-20261008.json)。

`MVP-UI-CACHE-001` 针对 staging 精确 `/marketing` 路径仍命中旧 HTML/JS 的问题，根布局改为按需生成 HTML；本机生产构建 22/22 浏览器测试、41/41 契约及构建/类型/lint 通过，独立只读复审批准。PR #47 前后端 CI 均通过并 squash 合入远端 `main=118ba775e291b88998bd033b7bca3410e29f8b88`，任务为 `DONE`，production 不变。

独立 `MVP-UI-CACHE-DEPLOY-001` 的首次三新摘要尝试因新检索镜像拉取停滞，在容器切换前取消，失败事实保留。用户随后明确批准**仅本次 staging**复用有依赖锁偏差的旧检索摘要；混合预检 `35953530870`、部署 `35953792293` 通过，新 backend/frontend 已运行。PR #49 合并并仅在 staging vhost 关闭继承的代理缓存；PR #50 合并并修正首页 307 入口验证器；证据 PR #51 前后端 CI 通过并合入 main `8038ad99c3ceb47787bb29b489611a28d012c575`。现场精确无 query 的四个 HTML 路径 200/no-store、指纹 JS immutable、三个健康 200，双机最终验证器通过，其他 vhost/公司负载未变。终态低敏证据见 `../../release/evidence/staging/crm-staging-html-cache-rollout-20260924.json`。任务标为 `DONE`；带身份 staging 全按钮、真实 TikTok、恢复演练和 production 不在此次完成范围。

`MVP-001` 已在真实 staging 完成内部凭据轮换和 TikTok App Key、Service ID、App Secret、DeepSeek API Key 四项外部凭据的安全注入；R02 现场职责矩阵、失败关闭、响应/日志无泄漏、固定出口和三个公网健康端点均通过。一次性工具首次因 cwd 权限在变更前失败，独立复核原配置与健康后修正重试成功。Mock 专用 `TIKTOK_WEBHOOK_SECRET` 不需向平台获取并保持空。R02 TR 为 `PASS`，证据已由 PR #40 合入 main；任务状态收尾为 `DONE`。真实平台接受、G0 恢复/回滚及 production 仍未通过。

`MVP-UI-001` 已修复知识/营销无店铺加载、过期 URL 店铺范围、店铺/渠道/Agent/团队表单反馈、会话筛选与 Agent 日志旧请求竞态。本机合成数据浏览器 20/20（开发服务与生产构建）、前端契约 41/41、lint/typecheck/build 及生产依赖 audit 通过；独立只读复审的问题均已返修。PR #43 前后端 CI 通过并 squash 合入 main `c9e49b88f54807f37b72c4c93ad1d66e554acc7d`，任务为 `DONE`。独立 staging 部署见 `MVP-UI-DEPLOY-001`；production 和真实 TikTok 授权仍未验收。

`MVP-UI-DEPLOY-001` 已从合并 `main=58263b1...` 发布三个镜像，业务机新 backend/frontend 摘要已实际切换且健康。约 8 GB 新检索镜像下载停滞，全量运行在切换前取消；用户明确授权**仅本次 staging**保留有依赖锁偏差的旧检索摘要。限定组合预检 `35849293069`、部署 `35849490309` 通过；固定出口、迁移头、公网三个健康端点、公司 GitLab/system Docker 前后摘要和入口隧道均复核。数据库、MinIO、环境文件受限恢复点已建且可读，未执行真正恢复/兼容回滚或带身份的 staging 逐按钮浏览器验收。证据 PR #45 已通过前后端 CI 并合入 main `ef62b4371736b144ef447352667d6854fb5dcaa8`，本次状态与索引收尾将任务标为 `DONE`；production 未部署。

`MVP-EGRESS-001` 的应用级 SOCKS5H 失败关闭、独立 Rootless helper、最小权限 `crm-egress` 安装器、出口验证器和 staging/回滚门禁已合入 `main`。staging 实际部署运行 `35806983990` 通过，固定出口配置和观测均为 `38.55.145.52`，故障关闭、TikTok 无凭据 TLS、双服务器保护基线和公网健康已验收；最终镜像摘要预检 `35808949842` 通过。业务机 GHCR 下载不稳定，用户明确批准仅本次 staging 保留构建输入等价的旧 backend/frontend 镜像及有依赖差异的旧检索镜像；差异和残余风险见 R02 记录及机器证据。R02 证据已通过 PR #38 合入 `main`；状态收尾分支将任务标为 `DONE`，production 未部署或放行。

入口服务器 root 家目录清理候选为 `85602c3c2702c33cbf00cf554afdfdc8c5ab0aa7`：3.1 GB staging 备份已原子迁入 `/var/backups/crm-staging`，退役 Python 缓存和误生成探针文件已进入 root-only 隔离目录；`/root` 顶层 CRM 项目匹配项为 0。迁移未删除数据，staging vhost、回环隧道与公网健康保持不变。

`MVP-DOMAIN-001` 的 `staging.overselfx.com` / `www.overselfx.com` 契约已合入远端 `main`；staging DNS/TLS 已由 `MVP-STAGING-001` 落地，production 与 Partner Center 仍未放行或变更。

2026-10-08 下午复核：13:32、13:51 两次 OAuth start 返回 200，但至 14:32 公网入口没有新 callback，授权任务与成功审计未新增；CRM 的 connected 仍对应 11:13 的旧授权。低敏证据见 [再次核对证据](../../release/evidence/staging/crm-staging-g1-oauth-no-new-callback-20261008-pm.json)。渠道页误导性成功提示已由 PR #94 合并修复；随后 PR #96 的单前端发布路径合入 main `f268408f3d9e396444e95cf2106141f0aae98188`，前端新摘要仅部署 staging，发布 `37742119116`、预取 `37742409755`、预检 `37743493147`、部署 `37743848722` 均通过。现场复核前端新摘要、原后端/检索、11 容器、迁移头、持久 proxy、三个公网健康 200 和固定出口；后续公网五路径也返回 200，见 [低敏发布证据](../../release/evidence/staging/crm-staging-frontend-only-rollout-20261008.json)。用户撤回此前“有顶部成功提示”的回答并称内置浏览器无法刷新，带身份页面观察仍缺；G1 继续部分通过，production 不变。

2026-10-09 恢复点：Edge 保留了 00:59:13Z 的真实 OAuth callback 303，最新 job `connected` 且临时密文字段清空；00:57:13Z 的失败 callback 属另一授权。用户从 Network 在新标签页打开原记录只看到 CRM 登录页，代理没有收到第二次 callback GET，故同一真实请求重放尚未验收。固定出口正常，后端只读聚焦测试 26 passed。测试店可见 325 笔订单，对五笔不同的 TikTok 配送订单调用增强物流 `202604` 均返回 `11007009`；官方接口针对 CBT 跨境首程，尚无已确认的合格首程订单或平台开通说明。见 [低敏现场证据](../../release/evidence/staging/crm-staging-g1-live-diagnostics-20261009.json)。G1 保持部分通过，production 未变。

2026-10-09 后续决定与恢复点：用户明确以首次有效 callback 完成授权关闭 G1 核心，现场同一 callback 二次 GET 不再阻断；`202604` 转独立 G1-L，暂不测试但最终 G8 前仍须通过。现场只读复核最新 job `connected`、完成且无错误，code/state 密文清空、匹配成功审计 1 条、渠道 connected；因此 G1 核心 staging 口径通过。Partner Center 订阅数 0，staging 真实只读和 Webhook 开关 false，公网 ready 200/TLS 正常；G2 可开始准备，真实投递未发生。见 [低敏证据](../../release/evidence/staging/crm-staging-g1-core-closure-20261009.json)，production 未变。

`MVP-002` 按上述用户决定形成 [IR](../records/implementation/IR-MVP-002-20261009-R01.md)、[TR](../reports/tests/TR-MVP-002-20261009-R01.md) 和 [RR](../reports/reviews/RR-MVP-002-20261009-R01.md)，绑定候选 subject `9526109e57fe0113451ed2f80c22c5fb2c739d1e`。PR #99 双 CI 通过并 squash 合入 main `1829991c4b780a63a6912a4652f89eea496584ae`；三份索引从合并后的源记录核对为 `CURRENT`，`MVP-002` 完成限定的 G1 核心范围，`MVP-003` 进入 G2 准备。未对 G2 执行订阅注册或运行配置切换。

## 权威入口

- 产品范围与验收：[`../product/PRODUCT.md`](../product/PRODUCT.md)
- 系统架构：[`../architecture/SYSTEM.md`](../architecture/SYSTEM.md)
- API 契约：[`../architecture/API.md`](../architecture/API.md)
- AI、RAG 与工具安全：[`../architecture/AI.md`](../architecture/AI.md)
- 唯一任务状态：[`../tasks/TASKS.md`](../tasks/TASKS.md)
- 开发与协作规范：[`../engineering/DEVELOPMENT.md`](../engineering/DEVELOPMENT.md)
- STANDARD 治理：[`../governance/GOVERNANCE.md`](../governance/GOVERNANCE.md)
- 测试策略：[`../quality/TEST-STRATEGY.md`](../quality/TEST-STRATEGY.md)
- 最新测试状态：[`../quality/TEST-STATUS.md`](../quality/TEST-STATUS.md)
- 部署边界：[`../operations/DEPLOYMENT.md`](../operations/DEPLOYMENT.md)
- 生产门禁：[`../operations/RELEASE-GATES.md`](../operations/RELEASE-GATES.md)

## 里程碑与活动任务

- 当前里程碑：关闭 TikTok 人工辅助 v0.1 的 G0～G6 真实环境门禁。
- `MVP-008` 的 staging 现场预取、候选部署、旧版回滚和切返证据已由 PR #84 合入 main `8fae4fb85c4ed9c8cdf862f99d839c3de60e55ab`；任务状态以 `../tasks/TASKS.md` 为准。
- `MVP-G1-NONLOG-001` 与 `MVP-OAUTH-REAUTH-001` 已合入 main；`MVP-002` 按用户新口径核对首次 OAuth、自然刷新、非物流只读和隔离，增强物流另属 `MVP-G1-LOG-202604-001`，G2 尚待真实投递。
- v0.1 之后的 Shopee/Amazon、生产翻译、公开自动回复、主动营销和高风险写入保持 `BACKLOG`，不得提前描述为已放行。

## 记录、索引与证据

- REPO-001 实施记录：[`../records/implementation/IR-REPO-001-20260916-R01.md`](../records/implementation/IR-REPO-001-20260916-R01.md)。
- REPO-001 测试记录：[`../reports/tests/TR-REPO-001-20260916-R01.md`](../reports/tests/TR-REPO-001-20260916-R01.md)。
- REPO-001 审查记录：[`../reports/reviews/RR-REPO-001-20260916-R01.md`](../reports/reviews/RR-REPO-001-20260916-R01.md)。三个派生索引状态为 `CURRENT`。
- TEST-001 实施记录：[`../records/implementation/IR-TEST-001-20260916-R01.md`](../records/implementation/IR-TEST-001-20260916-R01.md)。
- TEST-001 测试记录：[`../reports/tests/TR-TEST-001-20260916-R01.md`](../reports/tests/TR-TEST-001-20260916-R01.md)。
- TEST-001 审查记录：[`../reports/reviews/RR-TEST-001-20260916-R01.md`](../reports/reviews/RR-TEST-001-20260916-R01.md)。三个派生索引已从全部源记录重建为 `CURRENT`。
- MVP-DOMAIN-001 实施、测试与审查记录：[`../records/implementation/IR-MVP-DOMAIN-001-20260917-R01.md`](../records/implementation/IR-MVP-DOMAIN-001-20260917-R01.md)、[`../reports/tests/TR-MVP-DOMAIN-001-20260917-R01.md`](../reports/tests/TR-MVP-DOMAIN-001-20260917-R01.md)、[`../reports/reviews/RR-MVP-DOMAIN-001-20260917-R01.md`](../reports/reviews/RR-MVP-DOMAIN-001-20260917-R01.md)。三个派生索引从本地 `main` 读取时为 `CURRENT`。
- MVP-STAGING-001 定稿实施、测试与审查记录：[`../records/implementation/IR-MVP-STAGING-001-20260919-R01.md`](../records/implementation/IR-MVP-STAGING-001-20260919-R01.md)、[`../reports/tests/TR-MVP-STAGING-001-20260919-R01.md`](../reports/tests/TR-MVP-STAGING-001-20260919-R01.md)、[`../reports/reviews/RR-MVP-STAGING-001-20260919-R01.md`](../reports/reviews/RR-MVP-STAGING-001-20260919-R01.md)；工作流与绑定最终 subject 的终态低敏证据见 [`../../release/evidence/staging/crm-staging-deploy-35561109568.json`](../../release/evidence/staging/crm-staging-deploy-35561109568.json) 和 [`../../release/evidence/staging/crm-staging-final-state-20260921.json`](../../release/evidence/staging/crm-staging-final-state-20260921.json)。
- MVP-001 当前 R02：[`../records/implementation/IR-MVP-001-20260923-R02.md`](../records/implementation/IR-MVP-001-20260923-R02.md)、[`../reports/tests/TR-MVP-001-20260923-R02.md`](../reports/tests/TR-MVP-001-20260923-R02.md)、[`../reports/reviews/RR-MVP-001-20260923-R02.md`](../reports/reviews/RR-MVP-001-20260923-R02.md)；外部凭据低敏机器证据见 [`../../release/evidence/staging/crm-staging-external-credentials-20260923.json`](../../release/evidence/staging/crm-staging-external-credentials-20260923.json)。R01 仅代表此前内部轮换；三个派生索引已从 main 合并源记录重建为 `CURRENT`。
- MVP-EGRESS-001 staging 定稿 R02：[`../records/implementation/IR-MVP-EGRESS-001-20260923-R02.md`](../records/implementation/IR-MVP-EGRESS-001-20260923-R02.md)、[`../reports/tests/TR-MVP-EGRESS-001-20260923-R02.md`](../reports/tests/TR-MVP-EGRESS-001-20260923-R02.md)、[`../reports/reviews/RR-MVP-EGRESS-001-20260923-R02.md`](../reports/reviews/RR-MVP-EGRESS-001-20260923-R02.md)；低敏机器证据见 [`../../release/evidence/staging/crm-staging-tiktok-egress-20260923.json`](../../release/evidence/staging/crm-staging-tiktok-egress-20260923.json)。R01 为历史预部署记录，不再代表 live 结果；派生索引从 `main` 已合并源记录重建为 `CURRENT`。
- MVP-UI-001 定稿记录：[`../records/implementation/IR-MVP-UI-001-20260923-R01.md`](../records/implementation/IR-MVP-UI-001-20260923-R01.md)、[`../reports/tests/TR-MVP-UI-001-20260923-R01.md`](../reports/tests/TR-MVP-UI-001-20260923-R01.md)、[`../reports/reviews/RR-MVP-UI-001-20260923-R01.md`](../reports/reviews/RR-MVP-UI-001-20260923-R01.md)。三个派生索引已从 main 的全部合并源记录重建为 `CURRENT`。
- MVP-UI-DEPLOY-001 staging R01：[`../records/implementation/IR-MVP-UI-DEPLOY-001-20260923-R01.md`](../records/implementation/IR-MVP-UI-DEPLOY-001-20260923-R01.md)、[`../reports/tests/TR-MVP-UI-DEPLOY-001-20260923-R01.md`](../reports/tests/TR-MVP-UI-DEPLOY-001-20260923-R01.md)、[`../reports/reviews/RR-MVP-UI-DEPLOY-001-20260923-R01.md`](../reports/reviews/RR-MVP-UI-DEPLOY-001-20260923-R01.md)；低敏现场证据为 [`../../release/evidence/staging/crm-staging-ui-rollout-20260923.json`](../../release/evidence/staging/crm-staging-ui-rollout-20260923.json)。三个派生索引从 main 已合并源记录重建为 `CURRENT`。
- MVP-UI-CACHE-001 定稿 R01：[`../records/implementation/IR-MVP-UI-CACHE-001-20260924-R01.md`](../records/implementation/IR-MVP-UI-CACHE-001-20260924-R01.md)、[`../reports/tests/TR-MVP-UI-CACHE-001-20260924-R01.md`](../reports/tests/TR-MVP-UI-CACHE-001-20260924-R01.md)、[`../reports/reviews/RR-MVP-UI-CACHE-001-20260924-R01.md`](../reports/reviews/RR-MVP-UI-CACHE-001-20260924-R01.md)。
- MVP-UI-CACHE-DEPLOY-001 staging 定稿 R01：[`../records/implementation/IR-MVP-UI-CACHE-DEPLOY-001-20260924-R01.md`](../records/implementation/IR-MVP-UI-CACHE-DEPLOY-001-20260924-R01.md)、[`../reports/tests/TR-MVP-UI-CACHE-DEPLOY-001-20260924-R01.md`](../reports/tests/TR-MVP-UI-CACHE-DEPLOY-001-20260924-R01.md)、[`../reports/reviews/RR-MVP-UI-CACHE-DEPLOY-001-20260924-R01.md`](../reports/reviews/RR-MVP-UI-CACHE-DEPLOY-001-20260924-R01.md)；现场终态证据为 [`../../release/evidence/staging/crm-staging-html-cache-rollout-20260924.json`](../../release/evidence/staging/crm-staging-html-cache-rollout-20260924.json)。三个派生索引从已合并的 main 源记录重建为 `CURRENT`。
- MVP-OAUTH-REDIRECT-001 已合入 R01：[`../records/implementation/IR-MVP-OAUTH-REDIRECT-001-20260924-R01.md`](../records/implementation/IR-MVP-OAUTH-REDIRECT-001-20260924-R01.md)、[`../reports/tests/TR-MVP-OAUTH-REDIRECT-001-20260924-R01.md`](../reports/tests/TR-MVP-OAUTH-REDIRECT-001-20260924-R01.md)、[`../reports/reviews/RR-MVP-OAUTH-REDIRECT-001-20260924-R01.md`](../reports/reviews/RR-MVP-OAUTH-REDIRECT-001-20260924-R01.md)。
- MVP-READONLY-LOG-001 定稿 R01：[`../records/implementation/IR-MVP-READONLY-LOG-001-20260928-R01.md`](../records/implementation/IR-MVP-READONLY-LOG-001-20260928-R01.md)、[`../reports/tests/TR-MVP-READONLY-LOG-001-20260928-R01.md`](../reports/tests/TR-MVP-READONLY-LOG-001-20260928-R01.md)、[`../reports/reviews/RR-MVP-READONLY-LOG-001-20260928-R01.md`](../reports/reviews/RR-MVP-READONLY-LOG-001-20260928-R01.md)。三个派生索引从已合并 main 的源记录重建为 `CURRENT`。
- MVP-G1-NONLOG-001 非物流预检 R01 已由 PR #61 合入 main：[`../records/implementation/IR-MVP-G1-NONLOG-001-20260928-R01.md`](../records/implementation/IR-MVP-G1-NONLOG-001-20260928-R01.md)、[`../reports/tests/TR-MVP-G1-NONLOG-001-20260928-R01.md`](../reports/tests/TR-MVP-G1-NONLOG-001-20260928-R01.md)、[`../reports/reviews/RR-MVP-G1-NONLOG-001-20260928-R01.md`](../reports/reviews/RR-MVP-G1-NONLOG-001-20260928-R01.md)；低敏机器证据为 [`../../release/evidence/staging/crm-staging-g1-nonlog-20260928.json`](../../release/evidence/staging/crm-staging-g1-nonlog-20260928.json)。三个派生索引从已合并 main 的源记录重建为 `CURRENT`。
- MVP-OAUTH-REAUTH-001 staging R01 已由 PR #63 合入 main：[`../records/implementation/IR-MVP-OAUTH-REAUTH-001-20260928-R01.md`](../records/implementation/IR-MVP-OAUTH-REAUTH-001-20260928-R01.md)、[`../reports/tests/TR-MVP-OAUTH-REAUTH-001-20260928-R01.md`](../reports/tests/TR-MVP-OAUTH-REAUTH-001-20260928-R01.md)、[`../reports/reviews/RR-MVP-OAUTH-REAUTH-001-20260928-R01.md`](../reports/reviews/RR-MVP-OAUTH-REAUTH-001-20260928-R01.md)；低敏证据为 [`../../release/evidence/staging/crm-staging-oauth-reauth-20260928.json`](../../release/evidence/staging/crm-staging-oauth-reauth-20260928.json)。三个派生索引从已合并 main 源记录重建为 `CURRENT`。
- MVP-008-RESTORE-001 staging R01 已由 PR #65 合入 main：[`../records/implementation/IR-MVP-008-RESTORE-001-20260929-R01.md`](../records/implementation/IR-MVP-008-RESTORE-001-20260929-R01.md)、[`../reports/tests/TR-MVP-008-RESTORE-001-20260929-R01.md`](../reports/tests/TR-MVP-008-RESTORE-001-20260929-R01.md)、[`../reports/reviews/RR-MVP-008-RESTORE-001-20260929-R01.md`](../reports/reviews/RR-MVP-008-RESTORE-001-20260929-R01.md)；低敏证据为 [`../../release/evidence/staging/crm-staging-isolated-restore-20260929.json`](../../release/evidence/staging/crm-staging-isolated-restore-20260929.json)。三个派生索引从已合并 main 的源记录重建为 `CURRENT`；本任务不代表 G0 签署。
- MVP-008 staging G0 R01 已由 PR #84 合入 main：[`../records/implementation/IR-MVP-008-20260930-R01.md`](../records/implementation/IR-MVP-008-20260930-R01.md)、[`../reports/tests/TR-MVP-008-20260930-R01.md`](../reports/tests/TR-MVP-008-20260930-R01.md)、[`../reports/reviews/RR-MVP-008-20260930-R01.md`](../reports/reviews/RR-MVP-008-20260930-R01.md)；[低敏 G0 现场证据](../../release/evidence/staging/crm-staging-mvp008-g0-20260930.json)。三个派生索引已从 main 的源记录重建为 `CURRENT`。
- MVP-STAGING-PROXY-PERSIST-001 staging R01 已由证据 PR #90 合入 main：[`../records/implementation/IR-MVP-STAGING-PROXY-PERSIST-001-20261008-R01.md`](../records/implementation/IR-MVP-STAGING-PROXY-PERSIST-001-20261008-R01.md)、[`../reports/tests/TR-MVP-STAGING-PROXY-PERSIST-001-20261008-R01.md`](../reports/tests/TR-MVP-STAGING-PROXY-PERSIST-001-20261008-R01.md)、[`../reports/reviews/RR-MVP-STAGING-PROXY-PERSIST-001-20261008-R01.md`](../reports/reviews/RR-MVP-STAGING-PROXY-PERSIST-001-20261008-R01.md)；[低敏持久挂载证据](../../release/evidence/staging/crm-staging-proxy-persistent-source-20261008.json)。三份索引已从合并 main 的源记录核对为 `CURRENT`，任务为 `DONE`，G1/G6 和 production 不因此放行。
- 发布基线与低敏机器证据：[`../../release/`](../../release/)。
- 目录卫生：`frontend/` 空缓存树与 `.test-tmp/` 零字节测试残留已移出活动根并进入 `.maintenance/` 持久隔离；`CLEANUP-20260916-001` 状态为 `VERIFIED_UNUSED`，从实际隔离时间起保留满 7 天后，最早永久删除时间为 2026-09-23T14:00:00+08:00。
- `CLEANUP-20260916-002` 已将主 checkout 中唯一的旧 `src/backend/tests/` pytest 缓存隔离到 `.maintenance/`，状态为 `VERIFIED_UNUSED`，最早永久删除时间为 2026-09-23T18:05:00+08:00，恢复方法和摘要见 [`../operations/cleanup/CLEANUP-20260916-002.md`](../operations/cleanup/CLEANUP-20260916-002.md)。
- `CLEANUP-20260921-003` 已把入口服务器 root 家目录中的 staging 备份迁入 `/var/backups/crm-staging`，把两个退役生成物迁入 `/var/lib/crm-staging/quarantine/CLEANUP-20260921-003/root-home/`；状态为 `QUARANTINED`，备份永久保留，隔离物最早复核时间为 2026-09-28T14:37:17+08:00，详见 [`../operations/cleanup/CLEANUP-20260921-003.md`](../operations/cleanup/CLEANUP-20260921-003.md)。
- `CLEANUP-20260921-004` 已通过 PR #32 合入 `main`：截图中的六个已合并本地 worktree 和对应本地短期分支已删除，共移除 2,749,219,080 B；`origin/main`、主 checkout 的本地领先提交与未跟踪 `.superpowers/` 均未改变，详见 [`../operations/cleanup/CLEANUP-20260921-004.md`](../operations/cleanup/CLEANUP-20260921-004.md)。
- TEST-001 验证保留了已忽略的 `src/tests/.artifacts/task6-4cd6664-temp/`，仓库外受控验证工作区也保留 candidate-scoped archive、override 和 temp。它们是已知可重建临时材料，但未建立独立清理任务/批次，未移动或删除，因此目录卫生不标记 `CLEAN`。

## 阻塞、决定与风险

- G0 staging 恢复/回滚现场与 G1 核心口径通过；G1-L、G2～G6 尚未全部取得真实环境证据，G8 保持阻塞，production 未部署。
- 2026-10-09 最新 OAuth 回调和 job 终态真实成功，2026-10-04 自然刷新也已通过。用户决定现场 callback 二次 GET 不阻断 G1 核心；增强物流 `202604` 对五笔不同 TikTok 配送订单仍返回 `11007009`，须取得合格 CBT 首程订单或平台说明并在 G8 前通过。G2 staging 只读与 Webhook 开关已受控开启；独立查询确认 `NEW_MESSAGE` 订阅数 1，尚无官方投递。
- `MVP-001` 的内部轮换及外部四项凭据注入已通过；TikTok OAuth 已获用户确认，DeepSeek 平台已接受本次 34 条合成评测请求。固定出口已在 live staging 观测为 `38.55.145.52`；Partner Center 白名单只有用户截图，仍需真实平台出口证据确认。Mock 专用 `TIKTOK_WEBHOOK_SECRET` 不是外部待准备凭据。
- `AUTO_REPLY_ENABLED=false` 与 `REAL_TIKTOK_HIGH_RISK_WRITE_ENABLED=false` 继续作为安全基线。
- staging DNS/TLS、`18080 → 18081` 隧道和 Rootless CRM 可用；现运行 2026-10-09 G2 后端、2026-10-08 前端与既有分层检索不可变摘要。固定出口 helper 曾异常退出，2026-10-08 已恢复健康，G2 部署又复测 `38.55.145.52`；后续须核对是否再发以及告警覆盖。
- 入口服务器仍有一个失败且非持久的 `crm-external-image-prepare.service` transient unit，引用已不存在的退役脚本；本清理批次未扩大范围修改它，当前不监听端口且不影响 staging。
- TEST-001 独立审查 Critical 0、Important 0；非阻塞 Minor 建议是未来在 `src/tests/README.md` 说明 sibling-path 聚焦 pytest 需要 `-c pyproject.toml`，本候选未因此改变。
- TEST-001 仍保留两个既有前端 lint warning、两个 Python 弃用 warning 与一个 npm high severity audit 项；依赖升级另立任务，ignored temp 清理须遵守独立清理治理。
- MVP-UI-001 的本机隔离浏览器交互和本轮 staging 镜像部署/公开路由冒烟分别有证据；带身份的 staging 逐按钮浏览器与真实 TikTok 授权仍待专门验收。用户根 checkout 的本地 `main` 另有一个未推送提交及未知 `.superpowers/`，本分支没有修改它们。
- 本轮成功恢复点为 `/var/backups/crm-staging/secrets/20260921T080357Z/`；两份失败尝试恢复副本仍为 root-only 0600，清理必须另立 `MAINT-CLEANUP-*`，当前不得删除。
- Git、文件、Codex UI 与 GitHub 不是原子事务；每一步必须查重、执行、复核并保留恢复点。

## 最多三个下一动作

1. G4 低敏诊断已合入 main；下一步先确定新 backend 镜像的精确发布与 staging 部署范围，另获真实 Provider 复测授权后取得三条新失败的字段与语境并逐项复核，不改冻结阈值或重放旧请求。
2. G2 由店铺所有者经 Partner Center 确认买家聊天入口或官方测试投递；取得受控真实入站后复测，不再执行订阅 PUT。G3 保持真实写关闭，待受控会话、单次消息授权与 `unknown` 对账方案。
3. G1-L 增强物流待合格 CBT 首程订单或平台说明；G2、G3、G1-L 和 G4～G6 仍阻断 G8，production 保持 No-Go。
