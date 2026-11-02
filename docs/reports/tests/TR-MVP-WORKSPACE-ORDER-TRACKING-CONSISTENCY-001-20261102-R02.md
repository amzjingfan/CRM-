---
record_id: TR-MVP-WORKSPACE-ORDER-TRACKING-CONSISTENCY-001-20261102-R02
record_type: test
revision: R02
status: PARTIAL
task_id: MVP-WORKSPACE-ORDER-TRACKING-CONSISTENCY-001
tested_sha: 248fc487a07388ac7392339bfc262459e4ac7596
implementation_record: docs/records/implementation/IR-MVP-WORKSPACE-ORDER-TRACKING-CONSISTENCY-001-20261102-R01.md
requirement_ids: [MVP-WORKSPACE-ORDER-TRACKING-CONSISTENCY-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05]
environment: merged-main Linux rootless staging; public read-only health; Codex in-app browser unavailable
created_at: 2026-11-02T14:28:17+08:00
updated_at: 2026-11-02T14:28:17+08:00
supersedes: docs/reports/tests/TR-MVP-WORKSPACE-ORDER-TRACKING-CONSISTENCY-001-20261102-R01.md
---

# 测试范围、环境与 TEST_LAYOUT

R01 已记录合成浏览器 65/65、契约 80/80、类型、lint 与构建通过，绑定源码 subject `248fc487a07388ac7392339bfc262459e4ac7596`。PR #713 合并主线 `64da0bd76bd705cc0421e4dfcfd33770bc301738`，本轮从干净合并源码构建，仅更新 staging 前端。测试布局仍为 centralized。

# 命令和逐项结果

- `docker buildx build --platform linux/amd64 --push` 成功；GHCR 精确摘要和 OCI revision 与合并主线核对。业务机 GHCR 直拉迟缓，改用 `docker save`、SHA-256 校验、内网传输、`docker load`，再按摘要拉取并核对 RepoDigest。
- 发布前保存私有环境、PostgreSQL 自定义格式 dump 和 MinIO 归档；`pg_restore -l`、归档清单可读，目录 `0700`、文件 `0600`，未做恢复演练。
- `Test-StagingProductionGates.ps1 -ValidateOnly` 为 `validated`；`-Deploy` 为 `passed`。迁移头 `049_agent_auto_reply_preview (head)`，12 服务运行或健康，前后端实际摘要符合预期。精确摘要及证据文件哈希见[低敏发布证据](../../../release/evidence/staging/crm-staging-order-tracking-consistency-20261102.json)。
- 公网 `/healthz`、`/v1/health`、`/v1/health/ready`、`/workspace`、`/settings/stores` 均返回 200。
- Codex 内置浏览器原标签绑定连续超时；重新打开工作台标签并再次绑定仍超时，未取得已登录订单卡、物流卡及详情页的现场截图。该项标记 `UI_UNAVAILABLE`。
- 原两店人工发送、翻译与 Agent 模式保持；自动回复、营销、高风险写入仍关闭。未向真实买家发送消息，未执行退款或 production 发布；部署未使用 GitHub Actions。

# REQ/AC 与证据映射

AC-01 至 AC-04 的展示行为由 R01 合成契约和浏览器测试证明；本轮证明其精确镜像已部署且服务健康。AC-05 的 staging 已登录订单页面只读验收尚缺证据，不能以公网 200 或旧页面快照代替。

# 缺陷、未执行项与残余风险

首轮 GHCR 拉取与一次镜像摘要参数输入失败均在容器切换前停止；修正后门禁完整通过。内置浏览器绑定故障阻断真实页面回显验收。备份未恢复演练，也未制造真实订单状态变化。后端和迁移未变，本轮未重复运行后端全量测试。

# 结论和复测条件

staging 发布门禁 PASS，任务整体 PARTIAL：浏览器可用后用已登录只读页面核对不同店铺已完成订单统一标签、实际承运商、通用轨迹成功时的增强错误提示和真实轨迹详情。若失败，保留现有发布证据并按具体样本修复；production 仍 No-Go。
