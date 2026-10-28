---
record_id: IR-MVP-STAGING-LATENCY-001-20261029-R14
record_type: implementation
revision: R14
status: FINAL
task_id: MVP-STAGING-LATENCY-001
base_sha: 85572de4f2534513605849be83c15fa2a0dfcaf5
final_sha: 86e5c4e48862da445932ad50529c3a85bd3801f5
requirement_ids: [MVP-STAGING-LATENCY-001]
acceptance_ids: [AC-05, AC-06]
test_record: docs/reports/tests/TR-MVP-STAGING-LATENCY-001-20261029-R17.md
review_record: docs/reports/reviews/RR-MVP-STAGING-LATENCY-001-20261029-R14.md
created_at: 2026-10-29T06:30:00+08:00
updated_at: 2026-10-29T06:30:00+08:00
supersedes: docs/records/implementation/IR-MVP-STAGING-LATENCY-001-20261029-R13.md
---

# 实施与发布

PR #617 把基础接待授权店铺编号先回显、名称后补齐的局部前端修复合入主线 `fd836af1`；PR #618 从权威主线核对三索引并合入 `1597248e`。此次 staging 发布从实际运行的性能专用 release `eb0eedc7` 建立干净隔离源码 `82e9fd83`，只移入两个前端组件和一个合成浏览器测试，组件及测试 blob 与合并主线相同。未把最新 main 的动态 Agent v2 带到 staging。

前端镜像以 `82e9fd83` 为 OCI revision 发布为不可变摘要 `sha256:7ff00989…1a30`；本机与业务机按摘要拉回、linux/amd64、revision 一致。业务机用经 SHA256 校验的 Git bundle 从旧持久源码建立干净新目录；部署前将环境、PostgreSQL 自定义 dump、MinIO tar 留在私有 `0700/0600` 目录并验证可读。相同配置先 `ValidateOnly`，再直接运行 `Deploy`，迁移头与 12 容器通过，运行前端切换到新摘要，后端、检索、解析保持。没有使用 GitHub Actions 部署。

# 边界和回滚

原单店人工发送、Webhook 读取、翻译、Agent 调试、文档导入和固定出口保持；自动回复、通用 LLM、高风险写入继续关闭。没有发送真实买家消息、退款或操作 production。回滚仅切回发布前前端精确摘要 `sha256:73304958…fdff9`，保留业务增量。完整哈希、门禁和局部现场结果见 [TR R17](../../reports/tests/TR-MVP-STAGING-LATENCY-001-20261029-R17.md) 及[低敏发布证据](../../../release/evidence/staging/crm-staging-reception-progressive-20261029.json)。整体性能任务保持 `VERIFYING`。
