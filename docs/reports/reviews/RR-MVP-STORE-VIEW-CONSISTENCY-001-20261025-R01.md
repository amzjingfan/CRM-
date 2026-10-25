---
record_id: RR-MVP-STORE-VIEW-CONSISTENCY-001-20261025-R01
record_type: review
revision: R01
status: APPROVE
task_id: MVP-STORE-VIEW-CONSISTENCY-001
reviewed_sha: 35c3929e1d2c88ba965d4ac2f39391a826412fb0
implementation_record: docs/records/implementation/IR-MVP-STORE-VIEW-CONSISTENCY-001-20261025-R01.md
test_record: docs/reports/tests/TR-MVP-STORE-VIEW-CONSISTENCY-001-20261025-R01.md
review_focus: [correctness, store-isolation, csrf, idempotency, audit, migration, async-races, data-preservation]
created_at: 2026-10-25T03:16:21Z
updated_at: 2026-10-25T03:16:21Z
supersedes: null
---

# 审查范围、依据与重点风险

对候选 `35c3929e1d2c88ba965d4ac2f39391a826412fb0` 的知识详情、RAG 文件生命周期 API、迁移和 Worker 边界，以及看板、营销、工作台的店铺切换状态进行人工差异审查。依据用户两张详情截图、用户确认的文件编辑口径、源码、隔离数据库与浏览器回归。未把模拟数据测试当作真实 staging 操作。

# 发现、级别、位置和证据

- 原因确认：知识页 FAQ 与文件原本使用不同详情宽度与操作分支，且店铺切换不清除旧 `detailRow`；旧请求可在新店铺展示后迟到。统一外框并重置状态，详情与列表均按请求代次拒绝迟到结果。浏览器覆盖跨店铺打开详情、等宽、迟到会话详情、看板指标和营销编辑器。
- 文件元数据写入先通过授权店铺定位，跨店铺返回 404；分类必须同店铺且启用。路由保留 `knowledge.manage`、CSRF 和幂等键，审计仅记录分类和归档/删除状态，不记录正文。重复删除返回相同无内容结果；集成测试验证重复分类和删除不增加审计。
- 归档、删除保留源文件、版本和向量记录；Worker 不认领停用文件且提交新有效版本前再次核对。处理中的版本拒绝停用，避免处理队列静默卡住。未来检索必须按文件归档/删除状态过滤，已写入当前 AI 文档。
- 文件列表原有逐行获取最新版和块数会随每页条数增加查询；现在按页一次取得最新版、一次聚合块数，测试确认 2 个文件也只需固定批次查询。字段、店铺筛选和稳定排序不变。
- 迁移新增可空列，不回填既有数据；存在归档记录时降级拒绝丢弃状态。隔离库升降级验证通过。未发现需要删去的已跟踪无引用代码，按目录卫生规则不做推测性删除。

# 已验证与未验证内容

本地完整后端、前端契约、生产浏览器、lint、类型、构建及隔离 PostgreSQL 的具体结果见 TR。真实店铺页面、staging 部署、生产部署和文件内容检索未执行。GitHub Actions 是否可运行须由 PR 门禁单独确认，不能用本审查结论替代。

# 结论和返修条件

候选源码的正确性、店铺隔离与数据保留审查为 `APPROVE`。类型和状态筛选仍是当前页范围，页面与产品文档均明示；若产品要求跨全部分页全量筛选，需要新的统一服务端列表设计和验收。PR 只有在适用合并门禁通过后才可合入；任何跨店铺旧详情复现、归档后继续写入向量或审计幂等失效都应返修并重新记录。
