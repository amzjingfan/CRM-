---
record_id: RR-MVP-UI-DEPLOY-001-20260923-R01
record_type: review
revision: R01
status: APPROVE
task_id: MVP-UI-DEPLOY-001
reviewed_sha: 58263b1108e96d0d6afa21a6bbfae271fb5c7a87
implementation_record: docs/records/implementation/IR-MVP-UI-DEPLOY-001-20260923-R01.md
test_record: docs/reports/tests/TR-MVP-UI-DEPLOY-001-20260923-R01.md
review_focus: [staging-only, immutable-image-provenance, explicit-model-exception, rollback-point, company-workload-isolation, production-boundary]
created_at: 2026-09-23T18:42:00+08:00
updated_at: 2026-09-23T18:42:00+08:00
supersedes: null
---

# 审查依据与结论

复核远端 `main`、镜像发布和两次 staging 预检、一次取消的全量下载、成功的限定例外部署、业务机现场摘要与公网健康。部署范围内没有未关闭的 Critical/Important；仅按本次用户明确授权批准旧检索镜像继续运行。此审查不签署真实业务功能、G0 完整恢复/回滚或 production。

# 关键发现与保留项

- 新检索镜像未能下载完成；旧镜像的检索服务代码/Dockerfile 与当前 `main` 相同，但依赖锁不同。证据没有把它描述为同源摘要。下一次镜像升级须重新通过完整镜像供应链与现场部署门禁。
- 第一次正式工作流在容器切换前取消；独立确认旧运行摘要与三个公网 200 后，才恢复旧模型引用并启动第二次预检和部署。成功工作流 `35849490309` 才是本轮部署证据。
- PostgreSQL、MinIO、环境文件恢复点已建立且可读；真正恢复及兼容回滚演练仍由 `MVP-008` 完成。失败时可按已验证的旧摘要与受限备份恢复，不能宣称本轮已演练成功。
- GitLab/system Docker 和受保护监听前后摘要一致；本轮未改 edge Nginx、隧道策略、生产域名、生产数据或生产环境。真实 TikTok/LLM/自动回复开关保持关闭。
- staging 带身份的逐按钮浏览器验收未执行；只完成了部署健康、公开 UI 路由和静态资源冒烟。该剩余项不冒充 `MVP-UI-001` 的本机合成数据测试。
