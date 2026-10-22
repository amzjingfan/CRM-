---
record_id: TR-MVP-WORKSPACE-TRACKING-TIMELINE-001-20261022-R03
record_type: test
revision: R03
status: PASS
task_id: MVP-WORKSPACE-TRACKING-TIMELINE-001
tested_sha: 39244eb15b6c11db9b7463656304de1a92153c9d
implementation_record: docs/records/implementation/IR-MVP-WORKSPACE-TRACKING-TIMELINE-001-20261022-R03.md
requirement_ids: [MVP-WORKSPACE-TRACKING-TIMELINE-001]
acceptance_ids: [AC-03, AC-04, AC-05]
environment: merged-main Linux amd64 staging Rootless Docker; user-confirmed authenticated UI; synthetic Chrome intercepts all API calls
created_at: 2026-10-22T03:25:07Z
updated_at: 2026-10-22T03:25:07Z
supersedes: docs/reports/tests/TR-MVP-WORKSPACE-TRACKING-TIMELINE-001-20261022-R02.md
---

# 范围与执行结果

继承 R02 subject 上的本地回归：后端 2229 passed/29 skipped，前端契约 47 passed，本地开发与生产合成浏览器各 27 passed，受影响 Ruff、TypeScript、构建通过。GitHub Actions PR #508 的前后端作业均在零步骤失败，没有测试日志，不能记作 CI 通过。

本次从 `main=218befe0` 的干净源码构建两个 `linux/amd64` 镜像；源码 bundle `581c3907…22f7b3` 和双镜像归档 `a0a8d515…ea644bd` 在 staging 与本机 SHA-256 相同。导入后镜像 ID 与 OCI revision 精确一致；GHCR 发布并核对后端 `sha256:9a881e64…6e8868`、前端 `sha256:eb7d5893…67761`。旧三摘要复核后，六摘要预取 `passed`、配置验证 `validated`、私有 PostgreSQL 备份 `0600` 且 `pg_restore -l` 可读、部署门禁 `passed`。运行摘要与候选一致，检索摘要未改，11 个容器运行，迁移头、固定出口与四个公网健康路径通过。门禁原件保存在 staging 私有目录，SHA-256 与摘要见[低敏证据](../../../release/evidence/staging/crm-staging-workspace-tracking-bulk-20261022.json)。

已部署页面运行 `UI_BASE_URL=https://staging.overselfx.com node --test --test-name-pattern='tracking popover|cross border tracking|bulk tracking translation' src/tests/frontend/browser/workspace-experience.test.mjs`：3 passed，全部 `/v1/` 请求为合成拦截，发送调用 0。新翻译 POST 未携带身份与 CSRF 的探针返回 HTTP 403，未读店铺或调用模型。用户随后在已登录 staging 会话回复“可以了”，确认问题中的一键翻译所有节点、原文切换/重新翻译，以及物流卡片仅预填发送栏而没有直接发送。

# AC 映射与剩余风险

AC-03/04/05 的本地、部署页合成和用户登录态确认通过；staging 门禁与运行摘要通过，结论 `PASS`。未独立读取实际模型调用审计；当前授权店铺无已确认 CBT 多包裹首程样本，不能据此宣布该额外场景或 production 放行。备份脚本首次因 CRLF 在 `set -o pipefail` 前失败，确认未生成备份后换为 LF、重验脚本哈希并成功执行；容器切换只在备份成功之后。
