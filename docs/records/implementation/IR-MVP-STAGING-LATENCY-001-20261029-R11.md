---
record_id: IR-MVP-STAGING-LATENCY-001-20261029-R11
record_type: implementation
revision: R11
status: FINAL
task_id: MVP-STAGING-LATENCY-001
base_sha: 18cea7f2ea873b30f5ea9966ff26502d43189256
final_sha: eab7e2c207308fde34be1ca50f25d32be1670cfa
requirement_ids: [MVP-STAGING-LATENCY-001]
acceptance_ids: [AC-05, AC-06]
test_record: docs/reports/tests/TR-MVP-STAGING-LATENCY-001-20261029-R12.md
review_record: docs/reports/reviews/RR-MVP-STAGING-LATENCY-001-20261029-R11.md
created_at: 2026-10-29T02:58:00+08:00
updated_at: 2026-10-29T02:58:00+08:00
supersedes: docs/records/implementation/IR-MVP-STAGING-LATENCY-001-20261029-R10.md
---

# 目标与实际发布

认证刷新源码 `eab7e2c2` 已由 [PR #605](https://github.com/CP11-gh/CRM/pull/605) 合入 main `f8c3be74`，索引经 [PR #606](https://github.com/CP11-gh/CRM/pull/606) 从主线源记录对账。按用户“仅部署当前性能修复”的边界，从当前运行的隔离 release `18cea7f2` 精确摘取两次认证源码提交，形成干净 release `4edddffb`；与基线的 diff 仅为认证客户端、API 说明及两项前端测试。主线动态 Agent 重写未纳入。

本机构建发布唯一 linux/amd64 前端镜像，核对远端索引摘要与 OCI revision。业务机 GHCR 层拉取超过五分钟未完成，且服务未切换；停止该预取后，将已按摘要拉回的同一镜像通过现有 SSH 传送，核对 tar SHA、加载后再次从 GHCR 取回同一 RepoDigest 并复核 revision。后端、检索、解析镜像保持原摘要。使用 Git bundle 从旧干净源码创建新的干净部署目录，备份环境、PostgreSQL 与 MinIO 到仓库外私有目录，验证权限、数据库目录和 tar 可读性。运行 `ValidateOnly` 后 `Deploy` 成功；迁移仍为 034，12 容器健康，固定出口 IP 运行核对一致。原 Webhook 读取、单店人工发送、工作台翻译、Agent 调试和文档摄取保持；自动回复、LLM、高风险写入仍关闭。临时 GHCR 登录均已注销。

# 限制与恢复

已登录渠道和门店页面各显示一条授权，门店页强制刷新后仍有该行；公网健康和页面只读响应正常。未人为过期真实浏览器会话，因此并发 401 只由本地合成测试验证。公网几条未配对样本和浏览器控制工具壁钟时间不能证明用户可见加速；全站冷热、跨店、失败/限流及 WAN 仍待验。无真实消息、退款或 production 操作。回滚只切回发布前前端摘要 `a91d1c1f...`，不恢复数据库/MinIO 备份覆盖业务增量；精确摘要及私有备份校验见 [TR R12](../../reports/tests/TR-MVP-STAGING-LATENCY-001-20261029-R12.md) 与 [低敏证据](../../../release/evidence/staging/crm-staging-browser-refresh-20261029.json)。
