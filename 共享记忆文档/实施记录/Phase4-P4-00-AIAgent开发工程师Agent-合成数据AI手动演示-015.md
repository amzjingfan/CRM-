# 合成数据 AI 手动演示实施记录

## 1. 基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase4 |
| 任务编号 | P4-00；关联 REAL-AI-03、P2-09 |
| 模块编号 | M04 |
| 主责 Agent | AIAgent开发工程师Agent |
| 协作 Agent | 全栈开发工程师Agent、测试工程师Agent |
| 实施状态 | 已完成 |
| 开始日期 | 2026-08-28 |
| 完成日期 | 2026-08-28 |
| 代码位置 | `CRM智能聊天系统/` |

## 2. 需求与依据

- 产品需求：`共享记忆文档/智能客服平台 — 产品需求文档（PRD）V2.0.md` 中 AI 回复建议和人工接管要求。
- 接口依据：`共享记忆文档/智能客服平台 — 管理端接口文档.md` 中 11.6、11.8～11.14。
- 架构依据：`架构师/ADR-004-REAL-真实平台与DeepSeek生产接入边界-v1.0.md`。
- 任务依据：`AIAgent开发工程师/PLAN-002-REAL-DeepSeek与生产AI安全实施计划-v1.0.md` 中 REAL-AI-03。
- 验收依据：`共享记忆文档/MVP范围与验收标准.md` 中工作台 AI 建议、人工采用和失败关闭要求。
- 代码规范：`共享记忆文档/代码编写手册.md`。

## 3. 目标、范围与非目标

### 3.1 实施目标

- 在不接入真实店铺的情况下，通过现有客服工作台手动体验真实 DeepSeek 回复建议。
- 使用固定合成证据验证正常 FAQ、物流和高风险承诺兜底。
- 所有结果仅供人工采用，不触发平台写操作。

### 3.2 实施范围

- 六个固定合成场景、幂等种子脚本和公开建议接口复用。
- 真实 Provider 结构化回复、Agent 低敏运行追踪、SSE 和前端演示标识。
- 开发环境配置、自动化测试、冒烟脚本和手动页面验证。

### 3.3 非目标

- 不接入真实 TikTok 店铺、OAuth、Webhook 或平台发送。
- 不启用真实 pgvector/BGE RAG，不执行业务工具。
- 不开放自动回复、营销发送或生产模型质量门禁。

## 4. 实施前确认

- [x] 已读取共享记忆文档文件清单。
- [x] 已读取相关 PRD、接口、任务拆解和验收标准。
- [x] 涉及代码时已读取代码编写手册和适用 Skill。
- [x] 已确认 Phase、任务编号、模块编号和主责 Agent。
- [x] 已确认依赖、风险和验收方式。

## 5. 实施方案

### 5.1 方案说明

种子脚本创建独立 `ai-demo-store`、启用 Agent 配置和六条虚构会话。建议接口在开发演示开关开启后，只对该店铺及逐字匹配的固定消息走合成演示分支。该分支通过现有 Provider 工厂调用真实 DeepSeek，以固定结构化证据生成草稿；结果写入低敏 `agent_runs` 后通过现有 JSON/SSE 接口返回。前端显示演示标识，“使用”只写入输入框。

### 5.2 依赖关系

- 前置依赖：PostgreSQL、Redis、现有认证/RBAC、工作台、SSE、DeepSeek Provider 和服务端 Key。
- 后续依赖：测试工程师独立验证六场景质量、失败路径与无平台写操作。

### 5.3 风险控制

| 风险 | 影响 | 应对措施 |
| --- | --- | --- |
| 演示数据被误认为真实店铺数据 | 演示结论失真 | 独立店铺代码、客户名称前缀、响应字段和页面标识共同区分 |
| 任意客户文本通过演示入口外发 | 数据边界被绕过 | 系统 Prompt、场景 ID、消息和证据均精确匹配固定常量，修改后失败关闭 |
| 模型输出被自动发送 | 触发外部副作用 | 固定 `human_review/HUMAN_REVIEW`，不调用工具、不创建消息 |
| 模型输出不符合 JSON 契约 | 页面请求失败 | Prompt 明确字段、枚举和 JSON 结构，Provider/Pydantic 双重校验 |

## 6. 实际变更

### 6.1 文件变更

| 文件路径 | 变更类型 | 变更说明 | 负责 Agent |
| --- | --- | --- | --- |
| `backend/app/agent/security.py` | 修改 | 登记固定合成演示信封与 Prompt 版本 | AIAgent开发工程师Agent |
| `backend/app/agent/synthetic_demo.py` | 新增 | 实现固定场景解析和真实 Provider 结构化生成 | AIAgent开发工程师Agent |
| `backend/app/shared/config/settings.py` | 修改 | 增加仅开发/测试可用的演示开关 | AIAgent开发工程师Agent |
| `backend/app/chat/schemas.py` | 修改 | 建议响应增加演示标识 | 全栈开发工程师Agent |
| `backend/app/chat/service.py` | 修改 | 接入演示分支并记录低敏 AgentRun | AIAgent开发工程师Agent |
| `backend/scripts/seed_ai_demo.py` | 新增 | 幂等创建六条演示会话和一条物流订单 | AIAgent开发工程师Agent |
| `backend/scripts/run_ai_demo_smoke.py` | 新增 | 验证 JSON 与 SSE 真实模型链路 | AIAgent开发工程师Agent |
| `backend/tests/test_agent_synthetic_demo.py` | 新增 | 覆盖固定信封、篡改拒绝和生产开关 | AIAgent开发工程师Agent |
| `frontend/lib/api.ts` | 修改 | 同步建议响应类型 | 全栈开发工程师Agent |
| `frontend/app/workspace/page.tsx` | 修改 | 显示“合成数据演示” | 全栈开发工程师Agent |
| `.env.example`、`README.md` | 修改 | 增加配置和人工演示说明 | AIAgent开发工程师Agent |

### 6.2 接口、数据和配置变更

- API：建议 JSON 和 SSE `result` 增加 `demo_mode`、`demo_scenario`；请求保持兼容。
- 数据库：无迁移；种子脚本使用现有店铺、客户、会话、消息、订单、Agent 配置和运行表。
- 配置项：新增 `AI_SYNTHETIC_DEMO_ENABLED=false`，不记录真实 Key。
- AI：新增 `synthetic-crm-demo-v1.0.1` 固定 Prompt；仍复用当前 Provider 和模型配置。

### 6.3 关键实现说明

演示输入不是浏览器自由文本，而是服务端固定 JSON 信封。任何新增字段、内容修改、错误店铺或生产环境都会失败关闭。即使模型返回高置信度，服务端仍固定为人工复核；`agent_runs` 只保存场景、原因码、模型、Token、耗时和 trace ID。

## 7. 验证记录

| 验证项 | 命令或方法 | 预期结果 | 实际结果 | 状态 |
| --- | --- | --- | --- | --- |
| 聚焦后端测试 | `uv --cache-dir ..\\.uv-cache run pytest tests/test_agent_synthetic_demo.py tests/test_agent_providers.py tests/test_phase4_domain.py -q` | 安全和 Provider 回归通过 | 82 项通过 | 通过 |
| 静态检查 | `uv --cache-dir ..\\.uv-cache run ruff check ...`、`mypy app scripts` | 无静态错误 | Ruff 通过；mypy 158 个源文件通过 | 通过 |
| 前端检查 | `npm run lint`、`npm run typecheck`、`npm run test` | 无回归 | lint/typecheck 通过；24 项测试通过 | 通过 |
| 后端全量回归 | `uv --cache-dir ..\\.uv-cache run pytest -q --basetemp=.pytest-tmp/full-run` | 既有功能无回归 | 755 项通过，10 项按环境条件跳过 | 通过 |
| 前端生产构建 | `npm run build` | Next.js 所有管理路由构建成功 | 14 个静态页面生成成功 | 通过 |
| Compose 配置 | `docker-compose config --services` | 基础服务清单可解析 | 7 个服务解析成功；Docker 用户配置文件存在本机权限警告，不影响项目配置 | 通过 |
| JSON 与 SSE 冒烟 | `docker-compose exec -T backend python -m scripts.run_ai_demo_smoke` | 真实 DeepSeek 返回可用建议且 SSE 带演示标识 | `intent=general, confidence=0.95, action=human_review` | 通过 |
| 页面普通 FAQ | 工作台选择 `演示客户·return-policy` 后点击“生成/使用” | 显示建议、演示标识并只填充输入框 | 建议返回，标识正确，未发送 | 通过 |
| 页面高风险兜底 | 工作台选择 `演示客户·high-risk` 后点击“生成” | 不承诺退款或赔偿并要求人工复核 | `confidence=0`、`需人工复核`，未执行写操作 | 通过 |

## 8. 实施结果

- 完成项：六条演示数据、真实 DeepSeek 调用、JSON/SSE、页面生成与使用、演示标识和失败关闭。
- 未完成项：测试工程师独立质量评测；真实 RAG、真实店铺和平台写操作不在本任务范围。
- 与原方案差异：为满足当前无店铺手测需求，新增开发环境专用的固定合成入口，不放宽生产 DLP。
- 当前状态：已完成开发与运行冒烟，可供用户本地手动体验。

## 9. 遗留问题与风险

| 编号 | 问题或风险 | 优先级 | 负责 Agent | 计划处理 Phase/任务 |
| --- | --- | --- | --- | --- |
| R-DEMO-001 | 合成证据不代表真实 RAG 检索质量 | P2 | AIAgent开发工程师Agent、测试工程师Agent | REAL-AI-05 |
| R-DEMO-002 | 单次回复质量不能替代版本化真实模型评测 | P2 | 测试工程师Agent | REAL-AI-05 |
| R-DEMO-003 | 高风险样本可安全转人工，但模型意图分类仍可能偏差 | P2 | AIAgent开发工程师Agent | REAL-AI-03/05 |

## 10. 交接事项

- 交接给：测试工程师Agent。
- 后续任务：按六场景执行独立人工质量评测，并确认无工具调用、无平台消息和无真实客户数据。
- 必须注意：页面“使用”后不要点击“发送”；正式 RAG、真实店铺和生产放行结论必须单独测试。

## 11. 文档同步

- [x] 已同步接口变化。
- [x] 架构边界未改变，无新增 ADR。
- [x] 已同步任务状态。
- [x] 已通知测试工程师需要覆盖的范围。
- [x] 测试报告索引将在正式测试完成后更新。
