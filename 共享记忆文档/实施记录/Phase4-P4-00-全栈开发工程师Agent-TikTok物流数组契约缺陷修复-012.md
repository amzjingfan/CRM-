# TikTok 物流数组契约缺陷修复实施记录

## 1. 基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase4 |
| 任务编号 | P4-00；专项任务 REAL-FS-03 |
| 模块编号 | M00 |
| 主责 Agent | 全栈开发工程师Agent |
| 协作 Agent | 架构师Agent、测试工程师Agent |
| 实施状态 | 已完成（开发修复和确定性验证完成；正式缺陷待测试工程师独立复测关闭） |
| 开始日期 | 2026-08-31 |
| 完成日期 | 2026-08-31 |
| 代码位置 | `CRM智能聊天系统/` |

## 2. 需求与依据

- 产品需求：`共享记忆文档/智能客服平台 — 产品需求文档（PRD）V2.0.md` 中订单物流查询与平台接入边界。
- 接口依据：`共享记忆文档/智能客服平台 — 管理端接口文档.md` 第 11.15 节。
- 架构依据：`架构师/ADR-004-REAL-真实平台与DeepSeek生产接入边界-v1.0.md`、`架构师/ARCH-001-SYS-系统总体架构设计-v1.4.md`。
- 任务依据：`全栈开发工程师/PLAN-002-REAL-真实TikTok与DeepSeek运行面实施计划-v1.0.md` 的 REAL-FS-03。
- 缺陷依据：`测试工程师/Phase4-P4-00-全栈开发工程师Agent-M00-TikTok只读API与Webhook-综合测试-002.md` 的 `DEF-REAL-FS03-003`。
- 官方依据：[Get Logistics Tracking 202604](https://partner.tiktokshop.com/docv2/page/get-logistics-tracking-202604)、[物流 202604 升级公告](https://partner.tiktokshop.com/docv2/page/8syhoy40)。
- 验收依据：关键数组缺失失败关闭、显式空数组合法、既有 202604/Scope/重试场景无回归。
- 代码规范：`共享记忆文档/代码编写手册.md`。

## 3. 目标、范围与非目标

### 3.1 实施目标

- 区分 TikTok 明确返回空物流数组和完全省略关键数组字段两种语义。
- 关键字段缺失时返回稳定第三方错误且不重试，不把平台契约漂移伪装为空业务结果。
- 为缺失和显式空数组提供成对自动化证据。

### 3.2 实施范围

- `TikTokLogisticsData.logistics_details` 的必填语义。
- `TikTokLogisticsDetail.track_list` 的必填语义。
- REAL-FS-03 定向测试、全量回归、接口文档、计划状态和实施记录。

### 3.3 非目标

- 不改变 202604 路径、Scope、请求签名、重试白名单或 Webhook 实现。
- 不新增业务 API、配置项、依赖、数据库字段或 Alembic 迁移。
- 不调用真实店铺，不打开真实读取、Webhook 或任何平台写入开关。
- 不由全栈开发工程师修改测试报告中的正式缺陷状态。

## 4. 实施前确认

- [x] 已读取共享记忆文档文件清单。
- [x] 已读取相关 PRD、接口、任务拆解、MVP、团队职责和验收标准。
- [x] 已读取代码编写手册、全部适用 `AGENTS.md`、TikTok OpenAPI Skill 和当前官方 202604 契约。
- [x] 已确认 Phase、任务编号、模块编号和主责 Agent。
- [x] 已追踪 `TikTokLogisticsData`、`TikTokLogisticsDetail` 和 `get_tracking()` 的全部正式调用方。
- [x] 已确认本轮不需要迁移、真实凭证或平台写操作。

## 5. 实施方案

### 5.1 方案说明

缺陷根因是两个关键数组使用 `default_factory=list`。Pydantic 在字段完全缺失时自动构造空列表，使以下两类输入得到同一结果：

```text
{"order_id": "..."}
{"order_id": "...", "logistics_details": []}
```

修复直接落在共享 DTO 根部：移除两个数组的默认值并保留 `list[...]` 类型与最大长度约束。这样字段缺失触发 `ValidationError` 并由 `get_tracking()` 转换为 `THIRD_PARTY_ERROR`，字段明确存在且为 `[]` 时仍能正常通过。调用链不需要增加重复的手工 `if key not in data` 校验。

### 5.2 依赖关系

- 前置依赖：011 号实施记录中的 202604 物流、`seller.logistics` 和重试分类修复；迁移 head `019_tiktok_channel_unique`。
- 后续依赖：测试工程师独立复测 `DEF-REAL-FS03-003`；通过后由架构师核准单店铺真实只读冒烟。

### 5.3 风险控制

| 风险 | 影响 | 应对措施 |
| --- | --- | --- |
| 平台省略关键数组 | 误显示“暂无物流”并掩盖契约漂移 | DTO 字段必填，缺失统一失败关闭 |
| 合法空数组被误拒绝 | 无物流订单无法正常展示空状态 | 保留数组允许长度为 0，并增加正向测试 |
| 修复扩散到其他平台模型 | 引入无关回归 | 只修改 TikTok 202604 两个 DTO 字段 |
| 正式缺陷被开发侧提前关闭 | 破坏测试权威边界 | 记录为开发修复完成，等待测试工程师复测 |

## 6. 实际变更

### 6.1 文件变更

| 文件路径 | 变更类型 | 变更说明 | 负责 Agent |
| --- | --- | --- | --- |
| `CRM智能聊天系统/backend/app/integrations/tiktok_read.py` | 修改 | 将 `logistics_details` 和 `track_list` 改为必填且允许显式空数组 | 全栈开发工程师Agent |
| `CRM智能聊天系统/backend/tests/test_tiktok_read.py` | 修改 | 增加两类字段缺失失败和两类显式空数组成功测试 | 全栈开发工程师Agent |
| `共享记忆文档/智能客服平台 — 管理端接口文档.md` | 修改 | 明确关键数组的缺失/显式空语义 | 全栈开发工程师Agent |
| `全栈开发工程师/PLAN-002-REAL-真实TikTok与DeepSeek运行面实施计划-v1.0.md` | 修改 | 同步 002 号报告结论、003 开发修复和复测门禁 | 全栈开发工程师Agent |
| `共享记忆文档/实施记录索引.md` | 修改 | 登记本实施记录 | 全栈开发工程师Agent |

### 6.2 接口、数据和配置变更

- API：不新增或改变公共 HTTP API；内部 TikTok 物流成功响应的关键数组字段由可省略改为必填。
- 数据库：不适用；无迁移、表、字段或数据写入变化。
- 配置项：不适用；无环境变量变化。
- AI：不适用；未修改 AI Agent、Prompt、RAG、模型或工具决策。

### 6.3 关键实现说明

- `Field(max_length=...)` 不提供默认值，使数组字段在 Pydantic v2 中保持必填。
- 数组值为 `[]` 符合 `list` 和最大长度约束，继续表达平台明确返回的合法空结果。
- 字段缺失、类型错误或子项字段漂移统一进入既有 `ValidationError → THIRD_PARTY_ERROR` 路径，不重试、不记录原始响应。
- 本次没有增加手工字段检查、辅助类或第三方依赖，避免与模型校验产生第二套契约。

## 7. 验证记录

| 验证项 | 命令或方法 | 预期结果 | 实际结果 | 状态 |
| --- | --- | --- | --- | --- |
| 锁文件 | `uv lock --check --offline` | 锁文件一致 | 125 个包解析完成 | 通过 |
| Ruff | `uv run ruff check app tests scripts migrations` | 无静态问题 | All checks passed | 通过 |
| Ruff 格式 | `uv run ruff format --check app tests scripts migrations` | 正式 Python 文件无格式差异 | 215 个文件已格式化 | 通过 |
| mypy | `uv run mypy app scripts` | 严格类型通过 | 160 个源文件无类型错误 | 通过 |
| REAL-FS-03 聚焦 | 五个 REAL-FS-03/平台/健康测试文件 | 缺失失败、显式空成功且历史场景无回归 | 105 passed、1 个既有弃用警告 | 通过 |
| 默认后端全量 | `uv run pytest -q --basetemp ...` | 历史回归无退化 | 786 passed、10 skipped、2 个既有依赖弃用警告 | 通过 |
| PostgreSQL 迁移 | `upgrade head`、`downgrade 018_ai_observability`、`upgrade head` | 001→019、019→018→019 可执行 | 最终 `019_tiktok_channel_unique (head)` | 通过 |
| PostgreSQL 全量 | 隔离 `postgres-test` + `uv run --frozen pytest -q -rs` | 数据库测试无跳过 | 796 passed、2 个既有依赖弃用警告 | 通过 |
| 前端 | `npm run lint`、`typecheck`、`test`、`build` | 无跨模块回归 | 29 tests passed，14 个静态页面构建成功 | 通过 |
| Compose | 开发配置和非秘密占位生产叠加配置 | 配置可解析 | 均通过；Docker 用户配置不可读警告不影响解析 | 通过 |
| 运行态 | `/v1/health`、`/v1/health/ready` | ok/ready | `code=0`，状态 ok/ready | 通过 |
| 冒烟脚本入口 | `python -m scripts.verify_tiktok_readonly --help` | 入口可执行 | 帮助输出正常 | 通过 |
| Python 依赖审计 | `uv audit --locked` | 无已知漏洞 | 124 个锁定依赖无已知漏洞或不利项目状态 | 通过 |
| 真实店铺只读/Webhook | 真实环境执行 | 当前契约通过真实载荷验证 | 开关关闭，未读取凭证或调用平台 | 未执行 |

## 8. 实施结果

- 完成项：`DEF-REAL-FS03-003` 对应根因、成对测试、全量回归和文档同步。
- 未完成项：测试工程师独立复测、真实店铺授权核对、真实只读冒烟和 Partner Center Webhook 投递。
- 与原方案差异：无；严格按复测报告要求将关键数组改为必填且允许显式空。
- 当前状态：开发修复和工程验证完成；正式缺陷仍为 P2/Open，REAL-FS-03 和生产接入仍未放行。

## 9. 遗留问题与风险

| 编号 | 问题或风险 | 优先级 | 负责 Agent | 计划处理 Phase/任务 |
| --- | --- | --- | --- | --- |
| R-FS03-003-001 | 开发修复尚未由测试工程师独立复测 | P1 | 测试工程师Agent | REAL-FS-03 第三次复测 |
| R-FS03-003-002 | 真实店铺 `seller.logistics`、202604 载荷和限流尚未实测 | P1 | 全栈开发工程师Agent、测试工程师Agent、架构师Agent | REAL-FS-03 真实联调 |
| R-FS03-003-003 | 真实 Partner Center Webhook 签名、重试和 Worker 恢复尚未验证 | P1 | 全栈开发工程师Agent、测试工程师Agent | REAL-FS-03 真实联调 |
| R-FS03-003-004 | 当前主机 Node.js 24.19.0 与计划 Node.js 20 LTS 不一致 | P3 | 全栈开发工程师Agent | 生产镜像验收 |
| R-FS03-003-005 | 当前主机仅有独立 `docker-compose`，无 `docker compose` 插件 | P3 | 全栈开发工程师Agent | 部署工具链统一任务 |
| R-FS03-003-006 | 最新测试报告索引显示 REAL-FS-01 的 `DEF-REAL-FS01-005/006` 仍 Open，且索引引用的 005 号报告文件当前缺失 | P1 | 测试工程师Agent、架构师Agent、全栈开发工程师Agent | REAL-FS-01 生产门禁复核 |

## 10. 交接事项

- 交接给：测试工程师Agent、架构师Agent。
- 后续任务：先独立复测缺失/显式空数组四个场景和全量回归；通过后按单店铺、只读、一次一个能力的顺序执行真实店铺冒烟和 Webhook 验收。
- 必须注意：不得用 MockTransport 结果替代真实平台结论；所有平台写入、公开 AI、营销和自动回复继续关闭。

## 11. 文档同步

- [x] 已同步接口变化。
- [x] 已同步架构边界（无需新增 ADR）。
- [x] 已同步任务状态。
- [x] 已通知测试工程师覆盖字段缺失/显式空数组成对场景。
- [ ] 测试报告索引将在测试工程师正式复测完成后更新。
