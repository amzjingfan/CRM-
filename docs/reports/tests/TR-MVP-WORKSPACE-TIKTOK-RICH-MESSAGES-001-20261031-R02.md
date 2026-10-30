---
record_id: TR-MVP-WORKSPACE-TIKTOK-RICH-MESSAGES-001-20261031-R02
record_type: test
revision: R02
status: PASS
task_id: MVP-WORKSPACE-TIKTOK-RICH-MESSAGES-001
tested_sha: 60265d6566fca45ef1196ac777ea281be0662016
implementation_record: docs/records/implementation/IR-MVP-WORKSPACE-TIKTOK-RICH-MESSAGES-001-20261031-R02.md
requirement_ids: [MVP-WORKSPACE-TIKTOK-RICH-MESSAGES-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
environment: staging, linux/amd64 Rootless Docker, PostgreSQL 16, TikTok read-only two authorized channels, migration 046_merge_templates_dispatch
created_at: 2026-10-30T16:53:52Z
updated_at: 2026-10-30T17:43:07Z
supersedes: docs/reports/tests/TR-MVP-WORKSPACE-TIKTOK-RICH-MESSAGES-001-20261030-R01.md
---

# 测试范围、环境与 TEST_LAYOUT

`TEST_LAYOUT: centralized`。源码测试见 R01；本记录验证合并主线发布、现有 staging 的运行开关和两家授权店旧消息只读回填。未构造真实买家发送、退款或 production 操作。

# 命令和逐项结果

- 发布前只读检查：staging 运行源 `fbacb37299c4793ef166b2123e111b24095001b0`、`046_merge_templates_dispatch`；当前主线 `d67078db7445b1ef71a35af095075b1280f0d70c` 相对运行版的产品代码差异仅本次富消息修复。旧 045 hotfix 未使用。
- d670 干净源码 Git bundle 本地/远端 SHA256 一致；linux/amd64 新前后端 OCI revision 均为 d670、RepoDigest 与候选摘要一致。GHCR 拉取停滞后通过 SSH 传输同一镜像，传输 tar 两端 SHA256 一致、导入后再核对摘要。
- PostgreSQL custom dump 的 `pg_restore -l`、MinIO archive 的 `tar -tzf`、私有环境备份的权限和 SHA256 校验通过；备份目录 0700、文件 0600。
- `Test-StagingProductionGates.ps1` 依次对原运行版和候选执行 `ValidateOnly`，均通过；候选 `Deploy` 返回 `production_release=false`、部署与健康验证通过。精确摘要见低敏机器证据。
- 发布后 12 个 CRM 服务健康/运行，后端和前端运行摘要匹配候选，迁移仍为 `046_merge_templates_dispatch (head)`；公网 `/healthz`、`/v1/health`、`/v1/health/ready`、`/workspace` 为 HTTP 200，固定出口 `38.55.145.52`。
- 运行模式只读核对：人工真实发送允许列表仍为 2 家，Webhook 读取、Agent 调试/正式建议、文档导入保持；自动回复、营销、高风险 TikTok 写入关闭。没有平台写入测试。
- 已登录 staging 工作台 AX 树和截图看到原生订单、物流卡片，含平台商品图、订单状态、金额和物流摘要。另一真实买家会话的 AX 树看到 3 张图片链接与两张商品卡片，截图确认照片与商品图/价格实际显示，均不再是 `[TikTok IMAGE]` 或 `[TikTok PRODUCT_CARD]`；第三个真实买家会话看到 2 个 TikTok 视频播放器，截图确认画面，其中一条现场播放至 `0:12/0:12`。
- 旧占位初始共 4301 条：TikTok US 测试店铺 189、XBM 4112。`python -m scripts.sync_tiktok_conversations --channel-id <精确授权渠道> --store-id <精确授权店铺> --refresh-rich` 逐店执行，列表回填分别处理 180 与 1000 个会话，后者同步时新增 2 条本地消息。XBM 尚余 150 条，分布于 31 个不在官方最近 1000 会话列表内的旧会话；通过官方单会话和消息只读接口逐一补录，第一个会话修复 11 条，其余 30 个会话修复 139 条，定向补录新增本地消息 0、错误 0。最终两家店铺 `[TikTok ` 类型占位均为 0。
- 最终数据库聚合：XBM 有 43 条图片、2 条视频、3 条表情、11 条商品卡片、1142 条订单卡片、2945 条物流卡片具备对应 `media`/`card` 展示字段；TikTok US 测试店铺有 38 条图片、3 条视频、2 条商品卡片、35 条订单卡片、105 条物流卡片和 6 条从订单进入卡片具备展示字段。补录后公网四路径再次 HTTP 200。
- 回填收尾时复核到并行 Agent 模板任务已把 staging 前端切换为 `sha256:1a235bf2…8df0`，OCI revision `a0d9938e`，它是本次发布源码 `d67078db` 的后继主线；后端仍为本次 `sha256:1ad9b54a…7c56`。本轮原始 Deploy 输出的前端摘要与收尾时当前摘要分开保留，避免将并行部署误归于本任务。

# REQ/AC 或门禁与证据映射

AC-01：R01 的解析/合同/浏览器与本轮实际订单和物流卡片；AC-02：R01 隔离 PostgreSQL 幂等测试及本轮双店只读补录；AC-03：R01 安全 URL、全量测试及本轮运行开关/店铺核对；AC-04：本轮精确源码/镜像、私有备份、双预检、Deploy、046 和健康。机器摘要与完整性见 `release/evidence/staging/crm-staging-tiktok-rich-messages-20261031.json`。

# 缺陷、未执行项与残余风险

本轮未向真实买家发送消息，也没有验证签名视频 URL 到期后的播放情况。TikTok 未给播放地址的视频只能显示封面和提示；原平台 `[Other]` fallback 不伪造卡片。R01 的生产浏览器全套含一项独立 Agent 模板搜索失败，本轮未将其伪报通过。

# 结论和复测条件

发布及运行门禁通过，两店历史类型占位清零。可播放性仍受 TikTok 返回地址与签名有效期约束。
