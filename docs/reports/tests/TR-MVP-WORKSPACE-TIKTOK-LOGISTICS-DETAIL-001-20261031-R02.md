---
record_id: TR-MVP-WORKSPACE-TIKTOK-LOGISTICS-DETAIL-001-20261031-R02
record_type: test
revision: R02
status: PASS
task_id: MVP-WORKSPACE-TIKTOK-LOGISTICS-DETAIL-001
tested_sha: 8247cd5658b6c73824ebe3b85551b358fc485c18
implementation_record: docs/records/implementation/IR-MVP-WORKSPACE-TIKTOK-LOGISTICS-DETAIL-001-20261031-R01.md
requirement_ids: [MVP-WORKSPACE-TIKTOK-LOGISTICS-DETAIL-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
environment: merged-main Linux rootless staging; authenticated in-app workspace read-only observation
created_at: 2026-10-31T04:25:54Z
updated_at: 2026-10-31T04:25:54Z
supersedes: docs/reports/tests/TR-MVP-WORKSPACE-TIKTOK-LOGISTICS-DETAIL-001-20261031-R01.md
---

# 发布范围

[R01](TR-MVP-WORKSPACE-TIKTOK-LOGISTICS-DETAIL-001-20261031-R01.md) 的合成浏览器 57/57、前端契约 78/78、类型、lint 和生产构建绑定实现 subject `8247cd5658b6c73824ebe3b85551b358fc485c18`。PR #690 squash 合入 `d677dda269dfa5326ce20525a89c8585396af5bb`。本次从干净合并主线 `d47e8015f126dc0af756a02eb3febbcf41ceef47` 构建并只更新前端，后端和运行开关保留。主线从上一个已部署版本至本次发布的产品构建输入只有本任务两处前端组件变化；其余新增提交为文档证据。

# staging 门禁与结果

- 直接构建 `linux/amd64` 前端并使用 GHCR 完整不可变摘要部署；未使用 GitHub Actions。受审源码 bundle、OCI revision、平台和运行 RepoDigest 已核对。镜像传输 tar 哈希一致。
- 发布前建立私有环境、运行快照、PostgreSQL 自定义 dump 和 MinIO 归档备份，目录 `0700`、文件 `0600`，`pg_restore -l` 和 tar 清单可读。
- 旧版与候选 `ValidateOnly=validated`，候选 `Deploy=passed`；迁移保持 `047_supervisor_store_auth (head)`，12 项服务运行或健康。公网 `/healthz`、`/v1/health`、`/v1/health/ready`、`/workspace` 均返回 200。精确摘要见[低敏机器证据](../../../release/evidence/staging/crm-staging-tiktok-logistics-detail-20261031.json)。
- 已登录工作台的只读 AX 状态显示原会话及三条物流卡片、订单 ID 与物流单号；对较早卡片执行点击时浏览器工具超时，弹窗与轨迹请求记为 `UI_UNAVAILABLE`，不宣称真实交互已通过。R01 合成浏览器已覆盖卡片入口、按订单加载和缺 ID 失败关闭。
- 人工真实发送仍仅允许原两店，Webhook 读取、翻译和 Agent 开关保持；自动回复、营销、TikTok 高风险写入关闭。本次没有发送买家消息、退款或 production 操作。

# 结论与恢复

手动 staging 发布门禁通过，代码行为 AC 由 R01 验证；真实点击物流卡片的端到端观察待浏览器工具恢复后补查。回退优先恢复本证据中旧前端完整摘要，后端不变，保留部署后的业务增量；不直接覆盖新业务数据。`OTHER` 占位卡片缺官方关联字段，仍由独立阻塞任务跟进。
