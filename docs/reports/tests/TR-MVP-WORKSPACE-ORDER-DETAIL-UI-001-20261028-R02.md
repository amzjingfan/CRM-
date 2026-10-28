---
record_id: TR-MVP-WORKSPACE-ORDER-DETAIL-UI-001-20261028-R02
record_type: test
revision: R02
status: PASS
task_id: MVP-WORKSPACE-ORDER-DETAIL-UI-001
tested_sha: 0e4100b2b83012692ac2fb368707946687c9cde8
implementation_record: docs/records/implementation/IR-MVP-WORKSPACE-ORDER-DETAIL-UI-001-20261026-R01.md
requirement_ids: [MVP-WORKSPACE-ORDER-DETAIL-UI-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05]
environment: Windows isolated worktree; production Next.js build; staging Rootless Docker; authenticated browser; read-only live order
created_at: 2026-10-28T04:05:00Z
updated_at: 2026-10-28T04:05:00Z
supersedes: TR-MVP-WORKSPACE-ORDER-DETAIL-UI-001-20261026-R01
---

# 验证范围与来源

订单源码 subject `5ff30c11` 已由 PR #561 合入主线 `8ee98830`。本次从干净 `main=0e4100b2` 构建前端；staging 现有后端 OCI revision `5f0feb7f` 已包含该订单源码，仅更换前端。保留 Agent 调试及原人工辅助模式。详情读取只在已有授权会话、订单及买家核验路径中进行；没有发送消息或执行退款。

# 本地与部署门禁

- `npm run typecheck`、`npm run build` 通过；`npm test` 48/48；生产 standalone 服务在独立端口的 `UI_CACHE_EXPECT_PRODUCTION=1 npm run test:ui` 113/113。`npm run lint` 为 0 error、8 warning。首次浏览器运行因本地 standalone 未复制静态资源而超时，按生产镜像布局补齐静态资源后在同一源码重跑全部通过；未改产品代码或测试阈值。
- `git bundle verify` 通过，远端干净源码 HEAD 与主线 SHA 一致。私有环境、PostgreSQL、MinIO 快照为 `0700/0600`；`pg_restore -l` 可读。完整摘要见[低敏证据](../../../release/evidence/staging/crm-staging-order-detail-redeploy-20261028.json)。
- 前端 GHCR 不可变摘要与 OCI `linux/amd64`、revision `0e4100b2` 在 staging 核对；`ValidateOnly=validated`，`Deploy=passed`。数据库头 `034_agent_debug_runs`，12 个 CRM 容器运行，固定 TikTok 出口一致；公网三健康及 `/workspace` 均 200，HTML `no-store`、指纹 JS `immutable`。
- 后端、检索及文档解析镜像摘要保持原值。Webhook 读取、单店人工发送、翻译、文档摄取与 Agent 调试保留；自动回复、自动营销、通用 LLM 及高风险写入仍关闭。部署未使用 GitHub Actions。

# 已登录订单页面

真实已送达订单详情的订单、物流、商品和付款四区可见。订单区实际提供电话与完整收件地址；物流默认 2 条，点击“展开更多”后显示 8 条并可收起；商品实际提供规格及卖家 SKU。只记录字段存在性和条数，不记录买家、订单、电话或地址值。浏览器在窄视口需先打开“客户信息”侧栏，卡片进入可见区域后才按需加载详情；这符合当前惰性读取交互。

# 结论与限制

AC-01～AC-05 在本次 staging 范围 **PASS**。现场只核对一笔授权真实订单；其他订单的收件字段仍以 TikTok 实际返回为准，缺失或掩码不得推断。保留旧前端摘要与私有备份供回滚，不能以旧数据库快照覆盖部署后业务增量。production G8 继续 No-Go。
