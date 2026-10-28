---
record_id: TR-MVP-STAGING-LATENCY-001-20261028-R06
record_type: test
revision: R06
status: PARTIAL
task_id: MVP-STAGING-LATENCY-001
tested_sha: ef4beff3bb0d26b86195b7b36b590eb5153cfd2e
implementation_record: docs/records/implementation/IR-MVP-STAGING-LATENCY-001-20261028-R06.md
requirement_ids: [MVP-STAGING-LATENCY-001]
acceptance_ids: [AC-01, AC-05, AC-06]
environment: local production Next.js with intercepted synthetic API, staging business and gateway read-only probes, authenticated staging browser
created_at: 2026-10-28T22:45:00+08:00
updated_at: 2026-10-28T22:45:00+08:00
supersedes: docs/reports/tests/TR-MVP-STAGING-LATENCY-001-20261028-R05.md
---

# 范围和结果

`TEST_LAYOUT=centralized`。主线代码提交 `ef4beff3`：`npm run typecheck` 通过、ESLint 0 error/8 个既有 warning、`npm test` 48/48、`npm run build` 通过、本地生产服务浏览器 `UI_CACHE_EXPECT_PRODUCTION=1 npm run test:ui` 123/123。专用 release `97ac71ef`：同样类型、lint、48/48 合同、构建通过，浏览器 119/119。两候选的三处改动同树；四项浏览器数量差来自主线已有的其他产品测试。最初把合同脚本误写成不存在的 `test:contract`，随后使用项目真实的 `npm test` 完成验证；不把错误命令计为产品失败。

并行请求回归先在原串行实现报出 `Store request waited for identity`，修改后通过。用例阻塞身份响应并确认店铺请求已发出，使用合成 API，不测真实用户的绝对耗时。原有跨授权店铺、页面写入防护和失败场景回归随 123/123、119/119 执行。

# staging 发布与只读检查

发布源、三文件差异和 OCI digest 已核对；压缩层 64,407,512 字节，传入业务机的 OCI 归档 SHA-256 两端一致，Rootless Docker 保留精确 RepoDigest。备份目录 `0700`、环境/自定义 pg_dump/MinIO tar 均 `0600` 且目录可读。`ValidateOnly=validated`。首次部署镜像拉取因空临时 GHCR 凭据失败，旧前端仍在；凭据补入后重跑 `Deploy=passed`，随后注销，远端配置回到空凭据状态。12 个 CRM 容器运行，前端换为新摘要，后端 `sha256:a1f05c91…428c36` 未变。

公网三个健康端点及三个基础接待 URL 均 200。已登录浏览器：快捷回复页面完成身份校验并显示列表空态；超时自动回复和进店欢迎语各显示一条既有策略，开关辅助说明为“仅配置状态，不自动发送”。未点击保存、发送、退款；无 Actions 部署或 production 操作。精确 SHA、备份哈希、门禁哈希和现场结果见 [低敏证据](../../../release/evidence/staging/crm-staging-reception-bootstrap-20261028.json)。

# 网络诊断与未完成项

本轮前的 30 次分段 `/healthz` 有效探测：业务机回环 TTFB p50/p95 0.000639/0.001533 秒；经隧道的入口回环 1.388/5.043 秒；公网 29/30 次 200，成功请求 p50/p95 2.260/5.126 秒。活动隧道 TCP 重传约 16%，另见上游 5 秒超时 504；这些是不同窗口的诊断样本，不作逐请求因果归因。用户确认没有备用入口/线路，并将网络异常期间公网 p50/p95 从绝对应用验收阈值改为保留记录和对比。此次未取得真实用户同条件回显前后样本，未证明全站提速；全站冷/热、跨店、失败/限流和 TikTok 只读路径的实测仍未完成，整体任务保持 `PARTIAL / VERIFYING`。
