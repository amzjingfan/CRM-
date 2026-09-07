# DeepSeek Provider 第八次测试缺陷修复实施记录

## 1. 基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase4 |
| 任务编号 | P4-00；专项任务 `REAL-AI-01` |
| 模块编号 | M04 |
| 主责 Agent | AIAgent开发工程师Agent |
| 协作 Agent | 架构师Agent、全栈开发工程师Agent、测试工程师Agent |
| 实施状态 | 部分完成 |
| 开始日期 | 2026-08-27 |
| 完成日期 | 2026-08-27 |
| 代码位置 | `CRM智能聊天系统/backend/` |

## 2. 需求与依据

- 产品需求：`共享记忆文档/智能客服平台 — 产品需求文档（PRD）V2.0.md` 的 AI 智能问答和响应速度要求。
- 接口依据：`共享记忆文档/智能客服平台 — 管理端接口文档.md` 第 11.11～11.12 节。
- 架构依据：`架构师/ADR-004-REAL-真实平台与DeepSeek生产接入边界-v1.0.md` 的最小化出境、结构化校验和分级放行边界。
- 任务依据：`AI agent 开发工程师/PLAN-002-REAL-DeepSeek与生产AI安全实施计划-v1.0.md` 的 `REAL-AI-01`。
- 权威缺陷依据：`测试工程师/Phase4-P4-00-AIAgent开发工程师Agent-M04-DeepSeekProvider生产加固-综合测试-008.md` 的 `DEF-REAL-AI01-007`。
- 代码规范：`共享记忆文档/代码编写手册.md`。
- 供应商契约：[DeepSeek 官方 JSON Output 文档](https://api-docs.deepseek.com/guides/json_mode/)要求启用 `json_object` 时 Prompt 包含 `json` 并提供输出格式示例。

## 3. 目标、范围与非目标

### 3.1 实施目标

- 使唯一可信工程控制信封同时满足本地安全注册和 DeepSeek JSON Output 契约。
- 保持 `DEF-REAL-AI01-001～006` 对应的隐私、日志、重复键和完整信封门禁不回退。
- 以无客户数据的真实 DeepSeek 最小请求验证正向链路。

### 3.2 实施范围

- 固定 Provider 工程 Prompt、Prompt/策略版本、DeepSeek 离线契约测试和交接文档。
- 默认与隔离 PostgreSQL 全量回归、迁移、固定安全评测和依赖审计。

### 3.3 非目标

- 不实现业务 Prompt 注册表、本地 PII/DLP、`REAL-AI-02～05` 或真实客户文本外发。
- 不开放公开回复、生产翻译、AI 营销、自动回复或任何平台写操作。
- 不修改公共 API、数据库、Provider 请求参数、用户控制 DTO 或依赖。

## 4. 实施前确认

- [x] 已读取共享记忆文档文件清单。
- [x] 已读取相关 PRD、接口、任务拆解和验收标准。
- [x] 已读取代码编写手册、全部适用 `AGENTS.md` 和 Agent/Python/TDD/安全/可观测性/独立验证 Skill。
- [x] 已确认 Phase、任务编号、模块编号和主责 Agent。
- [x] 已确认依赖、风险和验收方式。

## 5. 实施方案

### 5.1 方案说明

采用最小固定契约修复：保持 `response_format={"type":"json_object"}` 和所有现有门禁不变，仅将不可变工程 Prompt 升级为显式要求 `json` 对象并提供无业务数据示例。调用方仍不能修改系统 Prompt 或扩展控制 DTO，因此兼容性修复不会形成新的动态文本出境入口。

### 5.2 依赖关系

- 前置依赖：008 号权威报告、现有 `StructuredRequest` 完整信封门禁、服务端 DeepSeek 配置。
- 后续依赖：测试工程师第九次独立复测；架构师和产品负责人生产放行。

### 5.3 风险控制

| 风险 | 影响 | 应对措施 |
| --- | --- | --- |
| 为满足供应商契约而放宽 Prompt | 客户文本可能越过 DLP | 只修改精确注册常量，不增加字段、前缀或动态模板 |
| 真实调用携带敏感数据 | 数据泄漏 | 仅发送固定系统提示和固定控制 DTO，不记录 Prompt、Key 或原始响应 |
| 开发自测被误作正式关闭 | 生产门禁被绕过 | 实施状态保持部分完成，缺陷继续等待测试工程师独立复测 |

## 6. 实际变更

### 6.1 文件变更

| 文件路径 | 变更类型 | 变更说明 | 负责 Agent |
| --- | --- | --- | --- |
| `CRM智能聊天系统/backend/app/agent/security.py` | 修改 | 升级 `prompt-dlp-v1.3.0`，登记 `provider-contract-v1.1.0` 并补齐 JSON Output 固定指令 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/tests/test_agent_domain.py` | 修改 | 验证可信 Prompt 版本和 `json` 前置条件 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/tests/test_agent_providers.py` | 修改 | 验证启用 `json_object` 时最终 Provider 信封实际包含 `json` | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/agent/README.md` | 修改 | 同步策略、Prompt 版本和真实业务失败关闭边界 | AIAgent开发工程师Agent |
| `AI agent 开发工程师/PLAN-002-REAL-DeepSeek与生产AI安全实施计划-v1.0.md` | 修改 | 同步 008 结论、第八轮修复与第九次复测状态 | AIAgent开发工程师Agent |
| `共享记忆文档/智能客服平台 — 管理端接口文档.md` | 修改 | 新增 11.12 内部正向契约说明 | AIAgent开发工程师Agent |
| `共享记忆文档/实施记录索引.md` | 修改 | 登记本实施记录 | AIAgent开发工程师Agent |

### 6.2 接口、数据和配置变更

- API：无公开 API 变化；仅内部固定 Prompt 契约升级。
- 数据库：无迁移、表、字段或索引变化。
- 配置项：无新增或修改；真实 Key 继续仅由服务端现有配置注入。
- AI：安全策略 `prompt-dlp-v1.3.0`；固定工程 Prompt `provider-contract-v1.1.0`。

### 6.3 关键实现说明

修复位于三家 Provider 共用安全边界已经认可的固定常量，不在 DeepSeek Provider 中创建第二套 Prompt，也不让运行时 Schema、客户消息或调用方参数改变可信文本。DeepSeek 的 JSON Output 前置条件由固定系统 Prompt 满足，系统 Prompt 的任意换行、BOM、零宽字符、大小写或动态内容仍会因精确匹配失败而阻断 SDK 调用。

## 7. 验证记录

| 验证项 | 命令或方法 | 预期结果 | 实际结果 | 状态 |
| --- | --- | --- | --- | --- |
| TDD 红灯 | 两个新增定向用例 | 复现缺失 `json` | `2 failed` | 通过 |
| TDD 绿灯 | 两个新增定向用例 | 修复后通过 | `2 passed` | 通过 |
| Provider/安全聚焦 | `uv run pytest` 七个专项文件 | 无回退 | `267 passed`，1 个既有 warning | 通过 |
| Ruff | `uv run ruff check app scripts tests migrations` | 无问题 | All checks passed | 通过 |
| Ruff Format | `uv run ruff format --check app scripts tests migrations` | 格式一致 | 208 files already formatted | 通过 |
| mypy | `uv run mypy app scripts` | 无类型错误 | 155 个源文件无错误 | 通过 |
| compileall | `uv run python -m compileall -q app scripts` | 编译通过 | 通过 | 通过 |
| 默认后端全量 | `uv run pytest -q --basetemp <workspace-temp>` | 无产品失败 | `716 passed, 10 skipped`，2 个既有 warning | 通过 |
| 隔离 PostgreSQL 全量 | 设置隔离 `TEST_DATABASE_URL` 后执行全量 | 无跳过 | `726 passed`，2 个既有 warning | 通过 |
| 迁移 | 空库升级、`019→018→019` | 恢复 head | `019_tiktok_channel_unique (head)` | 通过 |
| 固定安全评测 | `python -m scripts.evaluate_phase4` | 234 条通过 | 准确率 100%，危险漏放 0 | 通过 |
| 锁文件 | `uv lock --check` | 可解析 | 125 个包解析成功 | 通过 |
| 依赖审计 | `uv audit --locked` | 无已知漏洞 | 124 个包无已知漏洞或不良状态 | 通过 |
| 真实 DeepSeek 冒烟 | 固定控制信封、非流式、无客户数据 | 返回可校验 JSON 对象 | `deepseek-v4-flash` 成功；输入 70、输出 5 Token；约 2001ms | 通过 |

默认全量首次执行时产品断言已完成，但 pytest 清理系统级 `pytest-current` 遭 Windows 权限拒绝并返回 1；改用本轮唯一工作区 `--basetemp` 后退出码 0。`ruff format --check .` 会扫描两个既有不可访问临时目录并触发 Ruff 自身 panic，因此最终按正式 Python 代码范围 `app scripts tests migrations` 验证。上述环境限制没有被记录为产品通过证据。

## 8. 实施结果

- 完成项：修复 DeepSeek JSON Output 正向契约、补充测试、完成真实无客户数据冒烟和全量门禁验证。
- 未完成项：测试工程师第九次独立复测、异模型/人类安全审批和生产放行。
- 与原方案差异：无公共契约、数据库或依赖变化；修复范围小于报告允许上限。
- 当前状态：开发修复与自测已完成；正式 `REAL-AI-01` 继续以 008 号报告“不通过”和 `DEF-REAL-AI01-007 Open` 为准。

## 9. 遗留问题与风险

| 编号 | 问题或风险 | 优先级 | 负责 Agent | 计划处理 Phase/任务 |
| --- | --- | --- | --- | --- |
| R-REAL-AI01-009-01 | 当前项目不是 Git 仓库，无法绑定不可变提交和 diff 哈希 | P1 | 架构师Agent、全栈开发工程师Agent | 生产发布基线 |
| R-REAL-AI01-009-02 | 开发自测不能关闭 `DEF-REAL-AI01-007` | P1 | 测试工程师Agent | REAL-AI-01 第九次独立复测 |
| R-REAL-AI01-009-03 | 真实客户业务 Prompt、本地 DLP 和 REAL-AI-02～05 仍未放行 | P1 | 架构师Agent、AIAgent开发工程师Agent | 后续专项任务 |

## 10. 交接事项

- 交接给：测试工程师Agent、架构师Agent。
- 后续任务：以新开放样例复验 `DEF-REAL-AI01-007`，重新确认 001～006 不回退，并执行无客户数据真实最小请求。
- 必须注意：不得通过放宽系统 Prompt 精确注册、允许动态前缀或扩展用户 DTO 字段实现正向链路；公开 AI 和平台写操作继续关闭。

## 11. 文档同步

- [x] 已同步接口变化。
- [x] 已同步架构决策：未产生新架构决策，仅按 ADR-004 落实固定 Prompt 版本。
- [x] 已同步任务状态。
- [x] 已通知测试工程师需要覆盖的范围。
- [x] 测试报告索引将在正式测试完成后由测试工程师更新。
