---
record_id: RR-MVP-RAG-DOCUMENT-INGEST-001-20261023-R01
record_type: review
revision: R01
status: APPROVE
task_id: MVP-RAG-DOCUMENT-INGEST-001
reviewed_sha: 5ae37c54ec4abfe49a65b11525f08214bb182f65
implementation_record: docs/records/implementation/IR-MVP-RAG-DOCUMENT-INGEST-001-20261023-R01.md
test_record: docs/reports/tests/TR-MVP-RAG-DOCUMENT-INGEST-001-20261023-R01.md
review_focus: [tenant-isolation, csrf, idempotency, whole-version-review, atomic-version-swap, migration, cpu-fallback, dependency-security, staging-boundary]
created_at: 2026-10-23T08:05:00Z
updated_at: 2026-10-23T08:05:00Z
supersedes: null
---

# 审查范围、依据与重点风险

审查新增文档接口、上传和复核状态机、解析/分块/向量 Worker、pgvector 表及两条 `029` 迁移合流、部署配置、前端状态与依赖。重点确认跨店失败关闭、不可靠内容整版零向量、旧有效版本原子保留、资源边界以及本期不连 Agent 检索。

# 发现、级别、位置和证据

- 先前分块实现的 Token 边界存在解码膨胀风险；已在正式 subject 前修正并以真实 32/4 Token 长 PDF 验证 19 块、最大 32 Token。
- 并行主线引入另一条 `029` 迁移；以 `030_merge_rag_reception` 无数据变更合流，分别从两个已存在的 `029` 头升级通过。部署现场确认唯一头 `030`。
- 旧浏览器模拟接口仍按演示 PDF 流程响应；已改成真实文档 API 契约，85 项生产浏览器回归通过。
- Next.js 16.3.8 命中公开严重安全公告；升级到 16.4.2，官方生产依赖审计 0 项漏洞，运行容器版本与最终前端镜像摘要核对通过。开发依赖尚有 11 项审计告警，应在独立维护任务处理。
- 未发现未关闭的高优先级缺陷。MinIO/数据库旧快照不能直接覆盖部署后增量；回滚须优先切回精确镜像并保存新增数据。

# 已验证与未验证内容

已验证接口层 `knowledge.manage`/`knowledge.view`、CSRF、幂等键，服务层目标店铺再次核验和审计；索引提交前确认全部单元可靠，并在同一事务写块及切换 `active_version_number`。staging 的跨店 404、整版待复核 0 块、显式替换、旧版保留、CPU 向量化和 PostgreSQL 元数据直接佐证。尚未接通 Agent 检索/Rerank，也未做真实生产文档的版权、许可证和识别质量验收或备份全量恢复演练。

# 结论和返修条件

对当前 subject 的受限 staging 文档导入入口给出 `APPROVE`。本批准不等于 production 放行；生产前需另做真实授权样本质量、MinerU 商用许可义务、完整恢复及 G8 门禁。若修改质量判定、向量维度、迁移或店铺权限，应重新审查并发布新修订记录。
