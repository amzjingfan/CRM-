# Agent 模板精简与回复偏好实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** 精简四处管理界面，使三类回复偏好通过发布快照真实作用于回答。

**Architecture:** 沿用 Next.js 与 Python 模块化单体、不可变版本和现有批任务服务。前后端按互不重叠路径实施，统一联合验证；无新依赖，无真实消息发送。

**Tech Stack:** Next.js/React/TypeScript、FastAPI/Pydantic/SQLAlchemy、PostgreSQL、现有模型 Provider。

**Spec:** `docs/superpowers/specs/2026-10-31-agent-template-ui.md`（已确认）

## Global Constraints

- 只在 `feature/agent-template-ui-20261031` 隔离 worktree 修改，基线 d5fe2735eeb7b5d6d48939a0b32b10b1803930e8，目标 origin/main。
- 不部署；不发送买家消息；不动用户现有模板、Agent、文件和预览批次。
- 测试和临时输出只在 src/tests；保留租户权限、CSRF、幂等、审计和不可变发布。
- 参数只影响表达，不能替代事实、安全和工具权限。客户语言与坐席语言分离。

## Review Focus

1. 更新草稿与切换版本不能影响已发布回答；旧版本必须兼容。
2. 多 Agent 语言偏好冲突仍按明确且可审计的规则汇总，不随机选配置。
3. 折叠 UI 不应让冲突、知识缺失或只读历史不可见/不可操作。
4. 切换模板/任务/店铺时旧异步结果不能覆盖新上下文；URL 与分页可恢复。
5. 小屏长名称、长提示词和多店差异不应产生横向裁切或嵌套滚动。

## Task 1：回复偏好发布与运行（后端）

Files: `src/backend/app/agents/management/{models,service,schemas}.py`、`runtime/`、`orchestration/`、`delivery/`、`core/reply_policy.py`、必要迁移及 `src/tests/backend/agent/`、`src/tests/integration/postgres/`。

Produces: 已发布 Agent 带冻结回复偏好；Worker、汇总和坐席视图使用同一表达策略。保持现有 API 字段，必要的坐席说明为兼容可选结果。

- [x] 先写能复现偏好未冻结/未消费的测试，运行确认失败。
- [x] 实现冻结字段、旧版本兼容、发布比较、表达编译及运行/汇总传递；四种语气、三种客户语言、两种坐席语言均可达。客户正文与坐席说明分离。
- [x] 运行相关 pytest、Ruff、mypy；覆盖发布/模板应用、跨店隔离、草稿不影响运行、多 Agent 语言冲突和流式最终结果。

## Task 2：四处管理界面精简（前端）

Files: `src/frontend/app/agents/{page.tsx,templates/,template-batches/}`、`components/agents/templates/` 及模板 CSS；测试位于 `src/tests/frontend/`。

Consumes: 既有管理/模板 API 与 reply_profile；后端新增结果仅兼容扩展。Produces: 分组模板编辑、逐步批量应用、下拉批次选择、精简 Agent 关联操作。

- [x] 为任务下拉/深链接、模板分组/保存/发布、批量步骤与冲突可见写行为回归，先确认失败。
- [x] 删除模板职责说明编辑项与大块来源显示；保留 Agent 路由职责。默认隐藏编码/UUID/无变化值，低频能力折叠可达。
- [x] 实施统一样式、状态反馈与窄屏布局；保留脏表单保护、取消/重试、权限、分页与知识映射。
- [x] 运行 contract、lint、typecheck；构建后执行浏览器回归和截图核对。

## Task 3：联合验收与清理

Files: `src/tests/ai/`（必要合成用例）、`src/tests/.artifacts/agent-template-ui-20261031/`（运行输出）；正式文档由控制者维护。

- [x] 使用隔离 PostgreSQL 和本地生产前端 Docker 完成后端及前端回归，所有结果记录实际源码 SHA。
- [x] 真实模型仅用合成消息验证表达偏好；保存/发布/运行/汇总全链路与确定性测试分开记录。不使用真实买家字段。
- [x] 截图桌面/窄屏模板、应用、批次、Agent 参数界面；清理本轮测试数据与自建服务，复核用户数据未变。
- [x] 按 spec 与质量审查，修复后验证最终候选；同步 AI/API/测试/任务与 IR/TR/RR。
- [x] 读取最终 CI 作业并适用已批准零步骤本地替代门禁，满足门禁后合并并核实；未部署。
