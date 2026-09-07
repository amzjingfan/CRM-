# Phase3-P3-00 全栈开发工程师 Agent 后端幂等契约加固实施记录

## 1. 基本信息

- Phase：Phase 3
- 任务编号：P3-00
- 主责 Agent：全栈开发工程师 Agent
- 协作 Agent：测试工程师 Agent、架构师 Agent
- 实施日期：2026-08-20
- 关联报告：`测试工程师/Phase3-P3-00-全栈开发工程师Agent-M03-知识库、业务工具与主动营销-综合测试-001.md`
- 前置记录：`共享记忆文档/实施记录/Phase3-P3-00-全栈开发工程师Agent-测试缺陷修复-002.md`
- 当前状态：代码修复和自动化回归完成，等待测试工程师独立复测

## 2. 实施目标和边界

针对测试报告复测门禁中“后端对副作用接口强制校验”和“OpenAPI 契约不完整”两项要求进行加固。未修改 AI Agent 工程师负责的 `backend/app/agent`、Prompt、模型适配、RAG 和 `agent_runs`。

## 3. 修改内容

| 文件路径 | 变更类型 | 变更说明 | 负责 Agent |
| --- | --- | --- | --- |
| `CRM智能聊天系统/backend/app/auth/dependencies.py` | 修改 | 新增统一 `require_idempotency_key` 依赖，服务端强制校验 1～200 字符幂等键 | 全栈开发工程师 Agent |
| `CRM智能聊天系统/backend/app/knowledge_base/router.py` | 修改 | 分类、FAQ、发布、归档、删除和导入接口统一接入幂等键依赖 | 全栈开发工程师 Agent |
| `CRM智能聊天系统/backend/app/marketing/router.py` | 修改 | 活动创建、编辑、删除、启停接口统一接入幂等键依赖 | 全栈开发工程师 Agent |
| `CRM智能聊天系统/backend/app/workspace/router.py` | 修改 | 地址修改接口接入统一幂等键依赖，并保留工具执行参数传递 | 全栈开发工程师 Agent |
| `CRM智能聊天系统/backend/tests/test_phase3_domain.py` | 修改 | 扩展 OpenAPI 回归测试，覆盖知识库、导入、营销和地址修改接口 | 全栈开发工程师 Agent |

## 4. 关键规则

- 缺少 `Idempotency-Key` 或长度超过 200 字符时，副作用接口在服务端拒绝请求，不能只依赖前端按钮或请求封装。
- 前端请求层继续自动生成幂等键；业务调用显式提供的键优先保留，用于刷新重试时复用同一请求身份。
- OpenAPI 现在展示幂等键为必填 Header，并在关键接口描述中记录权限、`store_id` 隔离、Mock 行为和异步任务语义。
- 工具层原有的 `(store_id, idempotency_key)` 幂等记录和 unknown 失败关闭逻辑保持不变。

## 5. 验证记录

| 验证项 | 命令 | 实际结果 | 状态 |
| --- | --- | --- | --- |
| 后端 Ruff | `backend/.venv/Scripts/ruff.exe check .` | All checks passed | 通过 |
| 后端格式 | `backend/.venv/Scripts/ruff.exe format --check .` | 146 files already formatted | 通过 |
| 后端类型 | `backend/.venv/Scripts/python.exe -m mypy app scripts` | 110 source files 无错误 | 通过 |
| 后端测试 | `backend/.venv/Scripts/python.exe -m pytest -q` | 66 passed, 2 skipped | 通过 |
| 前端 lint | `npm run lint` | 通过 | 通过 |
| 前端类型 | `npm run typecheck` | 通过 | 通过 |
| 前端测试 | `npm run test` | 10 passed | 通过 |
| 前端构建 | `npm run build` | Next.js 15.5.23 构建成功 | 通过 |
| OpenAPI 契约 | `test_phase3_openapi_documents_write_contract` | 5 类副作用接口均展示必填幂等键和权限描述 | 通过 |

## 6. 遗留风险

| 编号 | 风险 | 优先级 | 处理计划 |
| --- | --- | --- | --- |
| R-001 | 测试报告原文仍保留修复前结果，尚未由测试工程师重新执行数据库、Worker、浏览器和 Compose 独立复测 | P1 | 测试工程师复测 DEF-P3-001～DEF-P3-008 |
| R-002 | 当前环境的 Docker Compose/PostgreSQL 运行态能力需由测试环境重新确认 | P1 | 复测阶段执行 Compose 和营销 Worker 专项 |
| R-003 | 真实第三方平台写操作、真实 Embedding/RAG 和 AI 营销文案仍不属于 Phase 3 | P2 | 后续平台联调和 AI 阶段 |

## 7. 交接事项

- 交给测试工程师 Agent：重新验证缺少幂等键时知识库、导入、营销和地址修改接口的拒绝行为；验证 OpenAPI 必填 Header 和接口描述；重复执行营销 unknown、冷却和频控专项。
- 交给架构师 Agent：确认当前通过统一依赖强制声明幂等边界，工具写操作仍由工具层持久化幂等结果的设计符合 Phase 3 契约。
- 正式测试结论仍只允许由测试工程师写入 `测试工程师/` 权威报告。
