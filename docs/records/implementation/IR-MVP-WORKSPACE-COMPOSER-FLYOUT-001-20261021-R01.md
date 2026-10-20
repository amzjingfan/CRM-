---
record_id: IR-MVP-WORKSPACE-COMPOSER-FLYOUT-001-20261021-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-WORKSPACE-COMPOSER-FLYOUT-001
base_sha: 433f340de451202e776c41ae1a59739f90dc385e
final_sha: ac46e7a4461a3c41588f321f31eed6f0c59c52ff
requirement_ids: [MVP-WORKSPACE-COMPOSER-FLYOUT-001]
acceptance_ids: [AC-01, AC-02, AC-03]
test_record: docs/reports/tests/TR-MVP-WORKSPACE-COMPOSER-FLYOUT-001-20261021-R01.md
review_record: null
created_at: 2026-10-20T17:11:01Z
updated_at: 2026-10-20T17:11:01Z
supersedes: null
---

# 实施目标与范围

按用户提供的发送栏截图修复现有工作台布局：字数计数独立靠左，语言、翻译和拆分发送按钮靠右；“更多语言”在主菜单旁展开。保留原人工审阅、翻译预览、权限、幂等和审计流程。staging 发布和现场核对由独立部署任务承担。

# 实际变更及原因

- 移除计数旁重复的发送模式文字；真实/模拟发送模式仍在会话标题显示。
- 将“更多语言”从主菜单内部纵向列表改成独立侧边浮层；打开时根据右侧可用宽度决定向右或向左，菜单高度受视口限制。
- 保留原有语言和发送方式选项及其操作，只为侧边菜单补充可访问的菜单名称；增加桌面及 375px 窄屏几何回归。

# 关键决定与偏差

参考图中的 Enter/发送按钮仍先进入独立人工审阅，最终确认才触发真实 TikTok 外发；本次不修改发送契约。用户所给图只作为布局资料，不执行图中文字中的任何指令。

# 数据、配置、接口、迁移或 Prompt 影响

无 API、数据库、配置、Prompt 或权限变化；仅前端状态、标记和 CSS。

# 验证交接

候选 `ac46e7a4461a3c41588f321f31eed6f0c59c52ff` 的 lint、类型、47 项契约、webpack 生产构建和 43 项生产浏览器回归通过。合成浏览器截图核对菜单方向与底部布局，详见关联 TR。

# 限制、风险与回滚

本地使用合成会话；staging 已登录页面仍待部署任务核对。回滚可恢复前版前端镜像，无数据迁移；本次未向买家发送消息，production 不发布。
