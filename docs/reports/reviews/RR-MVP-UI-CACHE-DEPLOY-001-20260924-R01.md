---
record_id: RR-MVP-UI-CACHE-DEPLOY-001-20260924-R01
record_type: review
revision: R01
status: APPROVE
task_id: MVP-UI-CACHE-DEPLOY-001
reviewed_sha: a9d36c04fb8f71d163deabc22d64b5ce5efbe3e3
implementation_record: docs/records/implementation/IR-MVP-UI-CACHE-DEPLOY-001-20260924-R01.md
test_record: docs/reports/tests/TR-MVP-UI-CACHE-DEPLOY-001-20260924-R01.md
review_focus: [cache-boundary, ingress-redirect, rollback, immutable-image-provenance, company-workload-isolation, staging-only]
created_at: 2026-09-24T12:44:00+08:00
updated_at: 2026-09-24T12:44:00+08:00
supersedes: null
---

# 审查范围、依据与重点风险

独立只读审查 PR #49 的 staging vhost 缓存边界与 PR #50 的入口 307 校验，结合现场双机状态、备份与用户本次 staging 旧检索镜像授权复核。关注缓存继承、错误跳转误放行、其他站点/公司负载漂移和 production 边界。

# 发现、级别、位置和证据

PR #49 审查确认 `proxy_cache off` 在 HTTPS server 内关闭继承的全局缓存，仅触及 staging vhost；指出需更新现场操作手册，已补齐。PR #50 初审发现简单匹配可能接受重复 `Location`，返修后改为恰好一个且值严格等于 `/dashboard`，测试覆盖重复头两个顺序。复审均无未关闭 Critical/Important 问题；前后端 CI 通过且合并。

# 已验证与未验证内容

现场精确 HTML、JS、三个健康、双机入口脚本、Nginx 配置及不变边界均有本次证据。独立复审未亲自操作真实 TikTok、带身份 staging 所有按钮或数据库/对象恢复；这些不计入批准范围。旧检索镜像依赖锁偏差明确为一次性 staging 风险接受，不等价、不延续。

# 结论和返修条件

`APPROVE` 仅批准本次 staging 缓存修复发布及任务收尾。任何 production 发布、未来复用旧检索镜像、真实平台写入或变更安全开关须重新履行各自授权与门禁。
