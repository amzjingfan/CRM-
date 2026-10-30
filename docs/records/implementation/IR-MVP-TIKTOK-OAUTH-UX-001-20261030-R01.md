---
record_id: IR-MVP-TIKTOK-OAUTH-UX-001-20261030-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-TIKTOK-OAUTH-UX-001
base_sha: b21f59a76adce8775eb5f9d61993e3b42886d72a
final_sha: be936358bdce4f633a51fe599a5e5a7bbc1e074b
requirement_ids: [MVP-TIKTOK-OAUTH-UX-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
test_record: docs/reports/tests/TR-MVP-TIKTOK-OAUTH-UX-001-20261030-R01.md
review_record: docs/reports/reviews/RR-MVP-TIKTOK-OAUTH-UX-001-20261030-R01.md
created_at: 2026-10-30T03:20:11Z
updated_at: 2026-10-30T03:20:11Z
supersedes: null
---

# 实施目标与范围

用户批准店铺页作为 TikTok 新增授权入口，并要求移除授权页截图中的旧 OAuth 卡片。仅调整管理端授权流程与低敏任务进度响应；未修改 OAuth Token 交换、店铺绑定事务、授权范围或部署配置。

# 实际变更及原因

- 授权页移除全局“授权 TikTok Shop”按钮和内部店铺选择卡片；保留渠道状态与 Mock 表单。只有异常、过期或断开的 TikTok 行显示定向重新授权，回跳统一进入店铺页。旧授权页回跳 URL 转交店铺页处理，不丢失任务参数。
- 店铺页保留“添加店铺”和多店选择；已连接店铺不再显示常驻重新授权。OAuth 任务成功后刷新授权聚合列表，并核对目标店铺的渠道已连接；多店选择核对每个所选平台店铺 ID。未显示连接时不报成功。
- 任务状态接口在原用户与店铺权限核验后返回稳定 `error_code` 和既有店铺 `store_id`。店铺页按已知原因提示，并对既有店铺提供精确重试按钮；未知错误保持通用提示，不回传凭证或平台原始响应。
- 更新产品、API、任务说明和前后端行为测试。与主线 PR #649 同位置任务表冲突时保留双方任务行。

# 关键决定与偏差

错误后再次 OAuth 仍需新的平台授权；成功后不再要求第二次授权。已连接但缺少到期时间的店铺不会仅因日期缺失出现重新授权入口。授权页的行内恢复仍使用既有服务端 OAuth 接口，不新增授权方式。

# 数据、配置、接口、迁移或 Prompt 影响

`GET /settings/channels/tiktok/oauth/jobs/{job_id}` 增加可空低敏 `error_code` 和 `store_id` 字段；仅失败状态返回错误原因。无迁移、配置、密钥、Prompt 或生产数据变更。

# 验证交接

见同任务 TR 与 RR；验证均基于 `be936358bdce4f633a51fe599a5e5a7bbc1e074b`。未调用真实 TikTok，也未部署 staging 或 production。

# 限制、风险与回滚

浏览器测试使用合成响应，真实平台授权及多店现场行为需由后续部署门禁验证。回滚可撤销该主题提交；新增响应字段为可选低敏字段，旧客户端仍可忽略。
