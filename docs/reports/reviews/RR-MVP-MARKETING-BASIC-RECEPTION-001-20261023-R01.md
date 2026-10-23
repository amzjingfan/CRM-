---
record_id: RR-MVP-MARKETING-BASIC-RECEPTION-001-20261023-R01
record_type: review
revision: R01
status: APPROVE
task_id: MVP-MARKETING-BASIC-RECEPTION-001
reviewed_sha: 439c50c926240e34e85d543629dab9cd03bdaea4
implementation_record: docs/records/implementation/IR-MVP-MARKETING-BASIC-RECEPTION-001-20261023-R01.md
test_record: docs/reports/tests/TR-MVP-MARKETING-BASIC-RECEPTION-001-20261023-R01.md
review_focus: [authorization, store-isolation, csrf, idempotency, audit, migration, no-auto-send, manual-send]
created_at: 2026-10-23T02:47:35Z
updated_at: 2026-10-23T03:16:13Z
supersedes: null
---

# 审查范围、依据与重点风险

审查 `reception` 配置接口、迁移 028、智能营销三页、工作台快捷回复弹层和测试，依据用户确认的配置优先且不自动发送边界、现有店铺权限/CSRF/幂等/审计规则和项目架构文档。重点是跨店铺与个人话术隔离、配置开关误触发平台发送、草稿与真实发送路径、迁移恢复。

# 发现、级别、位置和证据

早期独立审查指出以下交互问题，相关源码已修正并补浏览器用例：未知 `/快捷键` 按回车不应触发意外路径；分页请求的旧响应不能覆盖新搜索；策略“下移”菜单需可用；分组超过 100 条仍可显示；站点标签不应误导为会话站点过滤。

最终代码审查发现两项 P2：编辑快捷回复时先改 `shortcut` 再查询重复值，SQLAlchemy 提前刷新导致冲突返回 500；`/快捷键` 只加载个人范围，团队独有快捷键无法选用。最终候选已在修改对象之前查重并返回 409，同时按个人优先、团队其次检索；隔离 PostgreSQL 专测 7/7 通过，新增团队快捷键浏览器用例。独立复查关闭这两项发现。未发现自动发送或跨店读取的新阻断问题。

# 已验证与未验证内容

后端专门测试检查个人/团队权限、跨店 404、多店策略、写入幂等、审计不含回复正文、配置开关不创建营销事件。路由沿用 Cookie CSRF；工作台回复只填草稿或进入现有人工审阅，无直接发送调用。最终候选完成迁移 upgrade/downgrade/upgrade、Ruff、mypy、隔离 PostgreSQL 全量 2294 passed/3 skipped、前端契约 48/48、生产浏览器 81/81、lint/typecheck/build。未验证真实登录态与 staging 冒烟；跳过的 3 条为本机不适用的 POSIX bash 进程等待器用例。

# 结论和返修条件

`APPROVE`：已关闭两项 P2，允许最终源码进入 PR 合并和受控的 staging 手动部署。该结论不代表 staging 已部署或真实店铺已验收；任务维持 `VERIFYING`，现场门禁另取证。自动向 TikTok 买家发送仍未启用；production 不在本次审查放行范围内。
