---
record_id: IR-MVP-MARKETING-BASIC-RECEPTION-POLICY-003-20261023-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-MARKETING-BASIC-RECEPTION-POLICY-003
base_sha: d82a3445cb00db50182fbadd45b977614e59ab5e
final_sha: 77c1086ca3059a2d4483eb49014fec59a298ebb5
requirement_ids: [MVP-MARKETING-BASIC-RECEPTION-POLICY-003]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05]
test_record: docs/reports/tests/TR-MVP-MARKETING-BASIC-RECEPTION-POLICY-003-20261023-R01.md
review_record: docs/reports/reviews/RR-MVP-MARKETING-BASIC-RECEPTION-POLICY-003-20261023-R01.md
created_at: 2026-10-23T08:41:10Z
updated_at: 2026-10-23T08:41:10Z
supersedes: null
---

# 实施目标与范围

修复超时自动回复、进店欢迎语的多店策略保存后列表不可见问题，并按用户提供的界面参考实现店铺多选、三种有效期、状态和列表操作。两类策略仍只保存配置，不触发自动消息。

# 实际变更及原因

- 根因是列表始终带默认首家店铺 ID 查询，保存到另一家店铺的策略虽成功持久化，却被列表筛掉。列表接口现在可查询当前用户有查看权限的全部店铺，前端再按店铺名称或别名筛选；多店关联只要有一家无查看权限，整条策略不返回，避免借列表泄露跨店配置。
- 创建或调整关联店铺时同时校验 `marketing.manage` 和 `marketing.view`，保证提交者可以在管理列表看到刚保存的策略。原有 CSRF、幂等键与审计链路保持。
- 新增长期、起止日期、固定每日时段的本地有效期结构与 JSONB 迁移；列表按各店铺时区计算仅供展示的生效状态。旧 UTC 起止字段保留，原记录编辑时不改有效期可原样保存。
- 两页共用策略列表：全部、有效、失效，状态说明，店铺搜索，多选下拉，启停、编辑、复制、下移、置底、删除、批量关联和分页。开关只表示配置状态。
- 文档摄取与接待分组的两条 029 迁移已由主线 030 合流，本任务 031 接在 030 后。同步调整新主线的迁移头契约测试，并让 Windows 的 Git 路径读取显式使用 UTF-8。

# 关键决定与偏差

固定时段限定同一天内的开始时间早于结束时间。多店状态只要一家店处于有效时段即显示“生效中”，但该展示不驱动发送。用户已明确“先实现页面与配置，不自动发送”；没有接入定时器、Webhook 自动回复或买家外发。

# 数据、配置、接口、迁移或 Prompt 影响

`GET /v1/marketing/reception/policies` 的 `store_id` 改为可选，`kind` 仍必填；未传店铺时按授权店铺返回去重分页。创建/更新/查看模型新增可选 `schedule`。迁移 `031_reception_policy_schedule` 给 `reception_policies` 增加可空 JSONB 列；若已有新有效期数据，降级失败关闭并要求从部署备份恢复。无新权限、密钥或运行服务。

# 验证交接

隔离 PostgreSQL、后端全量及权限回归、前端合同和生产浏览器、类型、lint、构建、迁移升降级见 TR；源码风险审查见 RR。最终 staging 现场状态以合并后直接部署记录为准。

# 限制、风险与回滚

新增有效期仅用于策略配置及界面展示，服务端没有自动执行。回滚应用前需核对已写入的 `schedule` 数据；不可盲目降级。合并后的 staging 部署须维持现场 RAG 文档解析 Worker、单店人工发送、Webhook 读取与翻译模式，并先完成私有备份和 ValidateOnly；production 不在本任务范围。
