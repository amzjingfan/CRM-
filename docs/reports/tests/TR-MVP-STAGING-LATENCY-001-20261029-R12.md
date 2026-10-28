---
record_id: TR-MVP-STAGING-LATENCY-001-20261029-R12
record_type: test
revision: R12
status: PARTIAL
task_id: MVP-STAGING-LATENCY-001
tested_sha: eab7e2c207308fde34be1ca50f25d32be1670cfa
implementation_record: docs/records/implementation/IR-MVP-STAGING-LATENCY-001-20261029-R11.md
requirement_ids: [MVP-STAGING-LATENCY-001]
acceptance_ids: [AC-05, AC-06]
environment: Windows isolated release build and staging business host Rootless Docker, authenticated in-app browser
created_at: 2026-10-29T02:58:00+08:00
updated_at: 2026-10-29T02:58:00+08:00
supersedes: docs/reports/tests/TR-MVP-STAGING-LATENCY-001-20261029-R11.md
---

# 受测范围与结果

`TEST_LAYOUT=centralized`，发布候选 `4edddffb` 相对原运行 `18cea7f2` 仅含前端认证客户端、API 说明和前端测试。release `npm run test` 51/51、生产浏览器 `npm run test:ui` 125/125、`typecheck`/`build` 通过、lint 0 error/8 既有 warning。主线原候选为 51/51、129/129；release 少四条动态 Agent 浏览器测试，因用户禁止把该版本带入 staging。Docker 构建 linux/amd64，OCI revision 与 release SHA 一致，本机和远端精确 RepoDigest 相同。

备份环境、PostgreSQL 自定义 dump 和 MinIO tar 均为私有目录 `0700`、文件 `0600`，`pg_restore -l` 与 `tar -tf` 可读；详细低敏 SHA 见 [证据](../../../release/evidence/staging/crm-staging-browser-refresh-20261029.json)。第一次业务机 GHCR 预取长时间无进展，停在服务切换前；经 SSH 传送同一镜像、核对 tar SHA、业务机加载并重新核对 GHCR RepoDigest 后再运行门禁。`ValidateOnly=validated`、`Deploy=passed`，门禁证据哈希已锁定。迁移 034 head、固定出口核对、12 容器、三公网健康 200、新前端摘要和旧后端摘要均复核。运行开关及单店人工发送范围不变；临时 GHCR 凭据已注销。

部署后公网 `/settings/stores`、`/workspace`、`/dashboard` 200；`/marketing/reception` 307 为既有重定向；四个无查询参数 HTML 路径均返回 `private, no-cache, no-store`。已登录渠道页与门店页均显示一条授权行，强制刷新门店页后可访问性树无变化。只读 UI 不发送消息，也未执行退款。几条公网 TTFB 为诊断样本，真实过期会话的并发 401、精确回显时长、全站冷热/跨店/故障/限流仍未现场验收；WAN 抖动期间公网 p50/p95 不作应用改动绝对阈值。总体任务维持 PARTIAL/VERIFYING。
