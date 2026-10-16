---
record_id: IR-MVP-CONV-SYNC-001-20261016-R02
record_type: implementation
revision: R02
status: FINAL
task_id: MVP-CONV-SYNC-001
base_sha: 8fcfb64ef210c912bf19afcc4b546e0ff021aaf6
final_sha: 7fe97ea113b49925abc24a8438fda09e902ef519
requirement_ids: [MVP-CONV-SYNC-001]
acceptance_ids: [AC-02, AC-03, AC-04]
test_record: docs/reports/tests/TR-MVP-CONV-SYNC-001-20261016-R02.md
review_record: docs/reports/reviews/RR-MVP-CONV-SYNC-001-20261016-R02.md
created_at: 2026-10-16T19:03:00+08:00
updated_at: 2026-10-16T19:03:00+08:00
supersedes: docs/records/implementation/IR-MVP-CONV-SYNC-001-20261016-R01.md
---

# 真实会话列表的完整可达性

R01 的平台只读回填已在 staging 获得授权店铺真实数据；现场检查发现工作台会话列表固定只取第一页 30 条。R02 保持现有 `/workspace/sessions` 店铺权限与每页 30 条契约，增加“加载更多会话”，沿用平台、店铺和状态筛选；切换筛选后忽略旧请求，追加时按内部会话 ID 去重。消息详情的最新页和更早历史加载沿用 R01。

源码候选 `7fe97ea113b49925abc24a8438fda09e902ef519` 经 [PR #250](https://github.com/CP11-gh/CRM/pull/250) 双 CI 后 squash 合入 `main` `d0c9e67485d9c1252e1747c73a793a531ea05691`。此次变更仅影响前端列表和契约说明；未改变 TikTok 授权、平台发送、店铺隔离或生产运行配置。staging 回填、分页、镜像部署及现场写入开关以本版 TR 的实测为准。
