# Phase 3 知识库、业务工具与主动营销修复后独立复测报告

## 1. 测试基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase3 |
| 任务编号 | P3-00（阶段汇总） |
| 模块编号 | M03 |
| 模块名称 | 知识库、业务工具与主动营销 |
| 被测主责 Agent | 全栈开发工程师 Agent |
| 被测协作 Agent | 架构师 Agent、AIAgent开发工程师 Agent |
| 测试执行 Agent | 测试工程师 Agent |
| 关联上一份报告 | `测试工程师/Phase3-P3-00-全栈开发工程师Agent-M03-知识库、业务工具与主动营销-综合测试-001.md` |
| 关联实施记录 | `共享记忆文档/实施记录/Phase3-P3-00-全栈开发工程师Agent-测试缺陷修复-002.md`；`共享记忆文档/实施记录/Phase3-P3-00-全栈开发工程师Agent-后端幂等契约加固-003.md` |
| 测试类型 | 综合测试、回归测试、数据库测试、接口测试、安全测试、页面交互测试、兼容性测试 |
| 执行日期 | 2026-08-20 |
| 测试结论 | **不通过；3 个 P1、1 个 P2 未关闭，不建议 Phase 3 验收** |

## 2. 测试结论

本次对上一份报告的 `DEF-P3-001`～`DEF-P3-008` 及修复后运行态进行了独立复测。营销 `unknown` 失败关闭、同轮冷却、前端幂等请求、管理页主要 CRUD、`.next` 隔离、中英文正文、`html lang` 和 URL 状态已获得运行证据。

但当前仍不满足 Phase 3 验收门禁：

1. `DEF-P3-004` 仅部分关闭。分类编辑/删除入口已存在，但页面不能创建或修改 `parent_id`，无法由运营人员建立计划要求的父子分类树。
2. 新增 `DEF-P3-009`：项目交付的 `scripts/verify_phase3_runtime.py` 未随服务端强制 `Idempotency-Key` 更新，真实运行在知识分类创建处返回 422。
3. 新增 `DEF-P3-010`：375px 下知识库真实分类数据的操作行横向溢出，删除按钮右边界达到 452px，而文档可视宽度为 360px。
4. `DEF-P3-008` 仅部分关闭。全局 OpenAPI 已补充隔离、错误码、Mock 和异步规则，但多数资源级写接口描述仍未声明具体权限与店铺隔离要求。

因此正式结论为：**不通过；不建议将 Phase 3 M03 标记为已验收，也不建议以当前运行验收脚本作为发布门禁。**

## 3. 测试范围与边界

### 3.1 覆盖范围

- 后端锁文件、静态检查、格式、类型、单元与回归测试、依赖审计。
- 前端 lint、类型、测试、生产构建和 Compose 开发运行隔离。
- 独立临时数据库执行 `009 → 013 → 009 → 013`。
- 真实 PostgreSQL 营销 `unknown`、冷却和工具状态专项。
- 知识库、营销与工作台写接口幂等头契约。
- 知识库和营销页面 CRUD、国际化、URL 状态与响应式。
- OpenAPI 的权限、隔离、错误码、Mock、异步和幂等说明。
- 测试数据、临时数据库、临时脚本和测试账号清理。

### 3.2 非目标

- 真实 TikTok Shop、Shopee、Amazon 写操作联调。
- 真实 Embedding/RAG、AI 自动回复、AI 营销文案和 Agent 工具选择。
- 生产部署、正式性能压测和真实模型质量门禁。

## 4. 测试环境

| 项目 | 实际环境 |
| --- | --- |
| 操作系统 | Windows，PowerShell |
| Python | 项目当前 3.11 基线，`uv` 管理 |
| 前端 | Next.js 15.5.23，Node.js 20 基线 |
| 数据库 | Docker PostgreSQL 16 + pgvector |
| 缓存/对象存储 | Redis 7、MinIO |
| 容器服务 | backend、frontend、postgres、redis、minio、worker、jobs |
| Alembic 最终版本 | `013_marketing (head)` |
| 浏览器 | Codex In-app Browser，本地实际页面 |

宿主机直接执行 Alembic 时曾发生连接重置；容器内连接、隔离数据库迁移和应用健康均通过，因此记录为宿主网络环境现象，不判定为数据库迁移失败。

## 5. 全量质量门禁

| 验证项 | 实际结果 | 状态 |
| --- | --- | --- |
| `uv lock --check` | 退出码 0 | 通过 |
| Ruff | All checks passed | 通过 |
| Ruff format | 146 files already formatted | 通过 |
| mypy | 110 个源文件无错误 | 通过 |
| 后端 pytest | 66 passed，2 skipped，2 warnings | 通过（有环境说明） |
| `uv audit` | 85 个包无已知漏洞或不良状态 | 通过 |
| 前端 lint | 退出码 0 | 通过 |
| 前端 typecheck | 退出码 0 | 通过 |
| 前端 test | 10 passed，0 failed | 通过 |
| 前端 build | 连续两次 Next.js 生产构建成功 | 通过 |
| Compose config | 配置解析成功 | 通过 |
| Compose 服务 | 7 个服务运行；声明健康检查的服务健康 | 通过 |
| 后端健康 | `/v1/health` HTTP 200，`code=0` | 通过 |
| 前端健康 | `/login` HTTP 200，frontend healthy | 通过 |
| 运行验收脚本 | 知识分类创建返回 422 | **失败** |

2 项跳过仍为缺少隔离 PostgreSQL 测试库的 AI RAG 集成测试；本轮另用一次性数据库完成迁移和 Phase 3 全栈专项，不把它们计为本模块新增失败。

## 6. 原缺陷复测结果

| 缺陷 | 结果 | 独立证据 | 状态 |
| --- | --- | --- | --- |
| DEF-P3-001 unknown 误标成功 | 第二次执行仍为 `failed/PLATFORM_RESULT_UNKNOWN`，适配器总调用 1 次，工具保持 `unknown` | 真实 PostgreSQL 临时夹具专项 | 已关闭 |
| DEF-P3-002 同轮冷却绕过 | 同客户两笔弃单只创建 1 个事件 | 真实 PostgreSQL `_discover_events` 专项 | 已关闭 |
| DEF-P3-003 写请求缺少幂等键 | 15 个 Phase 3 写接口 OpenAPI 均要求 Header；浏览器创建分类成功；缺头请求返回 422 | OpenAPI 矩阵、真实浏览器和 API | 已关闭 |
| DEF-P3-004 管理页范围不完整 | FAQ、营销、分类编辑/删除入口已补齐；分类父子关系仍不能在 UI 建立 | 浏览器 DOM、源码与 API 类型对照 | **部分关闭** |
| DEF-P3-005 `.next` 共享 | 宿主 build 后 `/login` 200、容器 healthy；`crm_frontend_next_cache` 挂载 `/app/.next` | build、Docker inspect、HTTP 与日志 | 已关闭 |
| DEF-P3-006 国际化不完整 | 知识库/营销正文可切换，`html lang` 在 `en`/`zh-CN` 间同步 | 全新浏览器标签页交互 | 已关闭 |
| DEF-P3-007 URL 状态缺失 | 知识库保存 `store_id/page/search/status`；营销保存 `store_id/page`，刷新后保持 | 浏览器 URL 与刷新专项 | 已关闭 |
| DEF-P3-008 OpenAPI 不完整 | 全局契约和幂等 Header 已补；资源级具体权限/隔离描述仍不完整 | `/openapi.json` 全路径检查 | **部分关闭** |

## 7. 营销可靠性专项

### 7.1 unknown 失败关闭

真实数据库结果：

```json
{
  "first_unknown_status": "failed",
  "second_unknown_status": "failed",
  "second_unknown_error": "PLATFORM_RESULT_UNKNOWN",
  "unknown_attempt_count": 2,
  "adapter_send_calls": 1,
  "tool_status": "unknown"
}
```

结论：第二轮只重放审计终态，没有再次调用外部适配器，也没有伪装成功。

### 7.2 同轮冷却

同一客户创建两笔超过触发时间的未支付订单，执行一次事件发现后：

```json
{
  "cooldown_events": 1
}
```

结论：本轮第二来源已被刚创建的 `pending` 事件阻止，原重复发券缺陷关闭。

## 8. 数据库与构建隔离

### 8.1 迁移

在名称受限的一次性临时数据库执行：

```text
upgrade 009_agent_runs
upgrade 013_marketing
downgrade 009_agent_runs
upgrade 013_marketing
```

四个版本检查依次为 `009_agent_runs`、`013_marketing`、`009_agent_runs`、`013_marketing`，全部成功；临时数据库已删除，主数据库保持 `013_marketing (head)`。

### 8.2 前端构建隔离

- frontend 容器挂载 `crm_frontend_next_cache -> /app/.next`。
- 容器运行期间宿主执行 `npm run build` 成功。
- 构建后 `/login` HTTP 200，容器为 healthy。
- 最近日志未出现 `Cannot find module` 或缺失 chunk 错误。

## 9. 页面交互与兼容性

### 9.1 已通过

- 知识库真实分类和 FAQ 可显示，分类/FAQ 均有编辑、删除入口，FAQ 编辑进入保存/取消状态。
- 前端真实创建分类成功，证明浏览器 Cookie、CSRF 和自动幂等头链路可用。
- 营销活动显示编辑、启停、删除；编辑后进入保存/取消状态。
- 知识库搜索、状态和页码写入 URL，刷新后保持。
- 营销页码写入 URL，刷新后保持。
- 知识库、营销正文中英文切换成功，`html lang` 同步。
- 可见按钮最小高度 44px。

### 9.2 响应式结果

| 页面/宽度 | 结果 |
| --- | --- |
| 知识库 375px | **失败**：`clientWidth=360`、`scrollWidth=452`；分类“删除”按钮右边界 452px |
| 知识库 768/1024/1440px | 无应用元素越界 |
| 营销 768/1440px | 无应用元素越界 |
| 营销 375/1024px | Next.js 开发覆盖层使文档宽度存在噪声；应用元素边界扫描未发现越界，不据此报产品缺陷 |

## 10. 未关闭缺陷

### DEF-P3-004：分类树管理仍不完整

| 项目 | 内容 |
| --- | --- |
| 优先级 | P1 |
| 模块 | 前端知识库 |
| 状态 | 部分修复 |
| 影响 | 运营人员只能创建根分类和修改名称，不能通过管理端建立父子分类树 |

复现与证据：

1. 打开 `/knowledge`。
2. 分类创建表单只有名称和编码；分类编辑使用名称 Prompt。
3. 前端 `createKnowledgeCategory` 类型不接受 `parent_id`，编辑入口也不提供父分类选择。
4. 页面只能对数据库已有 `parent_id` 做固定缩进，不能完成层级维护。

预期：创建和编辑分类时可选择父分类，树形展示与数据层父子关系一致，并阻止循环父子关系。

### DEF-P3-008：OpenAPI 资源级权限与隔离描述仍不完整

| 项目 | 内容 |
| --- | --- |
| 优先级 | P2 |
| 模块 | OpenAPI / 接口契约 |
| 状态 | 部分修复 |

全局描述已包含 `store_id`、40401、40901、Mock、异步和统一错误码；15 个副作用接口也均公开必填 `Idempotency-Key`。但分类/FAQ 更新、删除、发布、归档及营销更新、删除、启停等操作描述仍只有“更新/删除/启用”等通用文字，没有声明具体权限码和资源级店铺隔离规则。

### DEF-P3-009：Phase 3 运行验收脚本与幂等契约不兼容

| 项目 | 内容 |
| --- | --- |
| 优先级 | P1 |
| 模块 | `backend/scripts/verify_phase3_runtime.py` |
| 状态 | 新增 |
| 影响 | 项目交付的知识库/工具/营销运行验收命令稳定失败，不能作为 CI 或交接门禁 |

复现：

```text
docker-compose exec -T -e PHASE3_TEST_PASSWORD=<临时密码> backend python scripts/verify_phase3_runtime.py
```

实际：`POST /v1/knowledge/categories` 返回 HTTP 422。脚本在分类、FAQ、发布、导入、营销创建/启停/删除请求中仍只使用认证 Header，没有提供新增的必填 `Idempotency-Key`。

预期：运行脚本为每个写动作生成稳定且互不冲突的幂等键，并完整通过后自动清理夹具。

### DEF-P3-010：375px 知识库分类操作横向溢出

| 项目 | 内容 |
| --- | --- |
| 优先级 | P1 |
| 模块 | 前端知识库响应式布局 |
| 状态 | 新增 |
| 影响 | 移动端分类删除操作位于可视区外，页面产生横向滚动，不符合 375px 验收要求 |

复现：

1. 创建至少一个名称较长的分类。
2. 在 375×900 视口打开 `/knowledge`。
3. 检查文档宽度和分类操作按钮边界。

实际：`clientWidth=360`、`scrollWidth=452`，删除按钮位于 `left=368/right=452`。

预期：分类名称截断或换行，操作区可换行/收缩，页面无横向滚动且按钮可直接操作。

## 11. 验收建议

- 当前不建议 Phase 3 M03 验收。
- 修复 `DEF-P3-004`、`DEF-P3-009`、`DEF-P3-010` 后必须重新执行浏览器、运行脚本和全量前端测试。
- `DEF-P3-008` 至少在下次复测前补齐全部资源级权限码与店铺隔离说明。
- 建议把本次真实营销专项加入自动化集成测试，避免现有测试只检查常量而未执行状态机。
- 建议把 375px 有数据分类操作加入前端组件或浏览器回归，避免空页面响应式测试假阳性。

## 12. 测试数据与环境恢复

- 临时营销客户、订单、会话、渠道、事件、消息、工具调用和优惠券记录均已清理。
- 临时 FAQ、分类、营销活动和两个测试账号均已清理，核验计数均为 0。
- 一次性迁移数据库已删除。
- 临时专项 Python 文件已删除。
- 浏览器视口已恢复，测试标签页已关闭。
- 主数据库保持 `013_marketing (head)`。
- backend、frontend、postgres、redis、minio、worker、jobs 均运行；后端健康为 `ok`，前端 `/login` 为 200。
- 测试工程师未修改产品代码。
