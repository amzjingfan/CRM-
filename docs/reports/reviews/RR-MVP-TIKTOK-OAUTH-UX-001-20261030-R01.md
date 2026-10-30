---
record_id: RR-MVP-TIKTOK-OAUTH-UX-001-20261030-R01
record_type: review
revision: R01
status: APPROVE
task_id: MVP-TIKTOK-OAUTH-UX-001
reviewed_sha: be936358bdce4f633a51fe599a5e5a7bbc1e074b
implementation_record: docs/records/implementation/IR-MVP-TIKTOK-OAUTH-UX-001-20261030-R01.md
test_record: docs/reports/tests/TR-MVP-TIKTOK-OAUTH-UX-001-20261030-R01.md
review_focus: [correctness, authorization, store_isolation, low_sensitivity, scope]
created_at: 2026-10-30T03:20:11Z
updated_at: 2026-10-30T03:20:11Z
supersedes: null
---

# 审查范围、依据与重点风险

审查 `origin/main...be936358` 的授权管理页、任务状态响应与测试差异，依据用户批准的单入口方案、`docs/product/PRODUCT.md`、`docs/architecture/API.md`、`docs/engineering/DEVELOPMENT.md`。重点检查错误店铺授权、伪成功、凭证外泄、旧回跳和 Mock 渠道回归。

# 发现、级别、位置和证据

- 初次实现曾按店铺页 `row.state !== active` 展示重新授权；连接但缺少到期时间时会误提示。已改为以渠道实际连接状态及明确到期/即将到期判断；浏览器回归核对已连接行无按钮。
- 失败状态仅新增稳定错误码和已授权访问的内部店铺 ID；原任务发起用户、目标店铺访问及渠道管理权限仍先核验。Token、state/code 密文、平台原始响应均未进入响应。
- 授权页行内恢复使用该行 `channel.store_id`；不再使用默认第一家内部店铺。后台连接提交语义未改变，前端成功提示又经聚合列表确认。
- 多店选择仍由原事务和选中 ID 决定；前端在列表显示全部所选店铺连接后才报告成功。

# 已验证与未验证内容

最终候选前端契约 55、相关浏览器 9、后端 OAuth 53、类型检查、lint、格式、构建通过。全量浏览器首次运行因独立端口和并行构建环境因素未通过；真实 TikTok 与部署现场未验证。

# 结论和返修条件

本地授权边界审查批准进入 PR/合并门禁。若任务进度权限核验、回跳地址或主线源码变化，需重新评估并补跑受影响验证。本审查不批准 staging 或 production 部署。
