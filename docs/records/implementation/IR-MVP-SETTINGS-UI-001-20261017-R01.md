---
record_id: IR-MVP-SETTINGS-UI-001-20261017-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-SETTINGS-UI-001
base_sha: cf288ab5afd8347b835ace61a5d13501b7f47c8c
final_sha: 6a4398491a6956b4e55ef998debf989834f74244
requirement_ids: [MVP-SETTINGS-UI-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
test_record: docs/reports/tests/TR-MVP-SETTINGS-UI-001-20261017-R01.md
review_record: null
created_at: 2026-10-17T10:02:00+08:00
updated_at: 2026-10-17T10:56:00+08:00
supersedes: null
---

# 实施目标与范围

按用户截图为会话列表补最近消息月日与时间，并将系统设置整理为店铺、员工分组。用户确认本次只实现已有接口支持的店铺授权和员工账号功能。

# 实际变更及原因

PR #280、#282、#284 已 squash 合入 `main`，最终前端 subject 为 `6a4398491a6956b4e55ef998debf989834f74244`。工作台从 `last_message_at` 格式化浏览器本地 `MM-DD HH:mm`，空值和坏值不显示时间。设置页复用现有店铺、渠道和员工 API，提供分组导航、真实列表、搜索和状态筛选；原有新增店铺、OAuth 授权、员工角色及禁用入口保留。窄屏表格可横向滚动，状态以中文单行显示。添加对应合约与浏览器回归测试。

# 关键决定与偏差

不展示当前数据接口不支持的授权到期时间、部门、敏感词、买家黑名单、电话等字段或栏目。按用户决定不运行 GitHub Actions，镜像发布与 staging 更新走手动路径；production 不发布。

# 数据、配置、接口、迁移或 Prompt 影响

只修改前端展示和前端测试；无数据库迁移、后端 API、权限、密钥、Prompt 或 TikTok 消息写入变化。

# 验证交接

本地前端合约测试 47/47，通过 lint、typecheck、build；浏览器回归 27 通过、1 条按配置跳过。最终合入 SHA 再次通过 47 项合约测试和生产镜像构建。staging 手动发布门禁通过；带身份页面复核到真实 TikTok 会话列表时间及店铺状态。见关联 TR 与低敏发布证据。

# 限制、风险与回滚

时间按访问者浏览器的本地时区展示。列表仅展示 API 已返回的最近消息时间；时间未知时保持空白。若 staging 部署后异常，使用部署前 frontend 不可变摘要及同一受审门禁回滚，后端与检索镜像不变。
