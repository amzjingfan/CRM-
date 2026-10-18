---
record_id: IR-MVP-WORKSPACE-DRAFT-001-20261018-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-WORKSPACE-DRAFT-001
base_sha: 04f0fbe93cc271c1671703ec1a2cb1af53574fef
final_sha: 07dede246c793cf5252624f59e35938f0ae46244
requirement_ids: [MVP-WORKSPACE-DRAFT-001]
acceptance_ids: [AC-01, AC-02, AC-03]
test_record: docs/reports/tests/TR-MVP-WORKSPACE-DRAFT-001-20261018-R01.md
review_record: null
created_at: 2026-10-18T11:13:00+08:00
updated_at: 2026-10-18T11:30:00+08:00
supersedes: null
---

# 目标和原因

用户反馈 staging 工作台无法输入回复草稿。只读核对确认目标 TikTok 会话服务端为店铺范围 `send_mode=real`，因此检查浏览器布局。合成浏览器在长 AI 建议和较矮桌面视口下复现：建议区域随文本增长，将回复输入框推至视口之外。

# 实际变更

前端为建议正文设置有限高度、内部滚动和长词换行，并使回复输入区保持固定 flex 尺寸。新增浏览器回归，用 100 条合成历史和长流式建议检查桌面与手机视口、草稿可输入、发送按钮随草稿启用且没有发送请求。没有改动真实发送权限、TikTok API、数据库、后端、自动回复或提示词。源码 PR #355 squash 合入 `main=07dede246c793cf5252624f59e35938f0ae46244`；合入前后前端及该测试的内容一致。

# 手动 staging 交付

从精确合入提交构建 `linux/amd64` 前端镜像，按摘要 `ghcr.io/cp11-gh/crm-frontend@sha256:1addb6c82f9a76d27ec59e999e8dea172bc49f06227808ecee00e28a892db795` 手动发布和部署。服务器使用核对过 SHA-256 的 Git bundle 得到干净受审 checkout；原后端与检索镜像保持不变。六个新旧镜像角色预取、部署参数验证、部署和三健康检查通过；店铺范围人工发送、只读 webhook 与工作台翻译保持原配置，生产未发布。部署前旧前端摘要为 `sha256:573b8466bee1d63c3c3d177954c8fd5a99b6af5f46f29de9c5855fbf52badf7c`，私有恢复快照保存在 staging，路径及摘要见关联 TR。

# 验证、限制和交接

合入提交的前端合约测试、lint、typecheck、build、生产模式浏览器回归均通过；公网静态 CSS 已出现建议限高及回复区固定尺寸规则。浏览器控制恢复后，在已登录真实 TikTok 会话中看到输入框处于可见区域；输入测试草稿后按钮从禁用变为可用，清除草稿后恢复禁用。截图及 AX 状态保留在本任务工具结果，关联 TR 为 `PASS`。未点击真实发送按钮，也不运行 GitHub Actions；证据 PR 合并后完成任务收尾。
