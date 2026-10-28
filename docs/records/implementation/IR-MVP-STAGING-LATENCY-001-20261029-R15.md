---
record_id: IR-MVP-STAGING-LATENCY-001-20261029-R15
record_type: implementation
revision: R15
status: FINAL
task_id: MVP-STAGING-LATENCY-001
base_sha: 5e683d1928eeda254d8503229975503737606479
final_sha: 053ebc9f625042e6c38c3c3c10df6e4c9e0284ba
requirement_ids: [MVP-STAGING-LATENCY-001]
acceptance_ids: [AC-05, AC-06]
test_record: docs/reports/tests/TR-MVP-STAGING-LATENCY-001-20261029-R19.md
review_record: docs/reports/reviews/RR-MVP-STAGING-LATENCY-001-20261029-R15.md
created_at: 2026-10-29T06:58:00+08:00
updated_at: 2026-10-29T06:58:00+08:00
supersedes: docs/records/implementation/IR-MVP-STAGING-LATENCY-001-20261029-R14.md
---

# 看板授权店铺先回显

此前看板先等待 `/v1/settings/stores` 返回，才知道店铺编号并发起五个指标读取。即使店铺名称请求很慢，指标接口本身已就绪也不能回显。

本次仅修改看板页面：并行请求 `/v1/auth/me` 和店铺名称；从当前用户的授权店铺编号先选择店铺并启动指标读取，名称稍后补齐。名称列表始终按授权编号过滤，迟到名称不覆盖用户切店；名称失败保留编号显示并记录错误。没有变更 API、数据库、发送或 Agent。合成浏览器用例覆盖名称长时间未返回、授权过滤、既有切店迟到响应与组件错误。

源码候选为 `053ebc9f625042e6c38c3c3c10df6e4c9e0284ba`，详见 [TR R19](../../reports/tests/TR-MVP-STAGING-LATENCY-001-20261029-R19.md)。本记录仅对应本地源码，未声明 staging 已发布。整体任务保持 `VERIFYING`，用户可见冷/热耗时及真实跨店、401、429 仍需现场证据。
