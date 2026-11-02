# 测试入口与执行约定

五类 Agent 本地候选的快速回归：`backend/agent/test_five_agent_template_manifest.py` 检查四个新增共享模板的七段提示词与工具清单；`backend/agent/test_fallback_sequence.py` 和 `test_dynamic_run_coordinator.py` 检查普通问题排除事件/兜底及第三轮固定话术；`backend/agent/test_auto_reply_preview_*.py` 检查逐店策略、只读后台预演和工作台读取；`backend/agent/test_agent_business_tools.py`、`backend/domain/test_workspace_catalog_availability.py` 检查有货商品投影。真实迁移、JWT/CSRF、权限与版本锁仍须由隔离 PostgreSQL 脚本运行，前端交互用 `frontend/browser/agent-prototype.test.mjs` 和 `reply-review.test.mjs`。这些合成用例不等于 TikTok US 现场工具、RAG 或零外发验收。

本目录是项目唯一跟踪的测试资产根。项目整体采用 `TEST_LAYOUT: centralized` 布局，测试策略见 [`../../docs/quality/TEST-STRATEGY.md`](../../docs/quality/TEST-STRATEGY.md)。

## 权威路径与发现规则

| 路径 | 发现规则 | 说明 |
|---|---|---|
| `src/tests/backend/` | `test_*.py`，由 `src/backend/pyproject.toml` 的 `../tests/backend` 发现 | 按 `agent`、`auth_security`、`domain`、`platform` 和 `runtime_infrastructure` 分类的后端测试 |
| `src/tests/integration/postgres/` | `test_*.py`，由同一 pytest 配置的 `../tests/integration/postgres` 发现 | 真实 PostgreSQL/pgvector 跨模块集成测试 |
| `src/tests/frontend/contract/` | `*.test.mjs`，由 `src/frontend/package.json` 的 `npm run test` 执行 | 前端组合、API 使用与安全契约 |
| `src/tests/frontend/browser/` | `*.test.mjs`，在本地 Next 服务和 Chrome 就绪时由 `npm run test:ui` 执行 | 拦截外部请求、使用合成数据的交互回归；不代表真实平台验收 |
| `src/tests/frontend/helpers/` | 由前端契约测试显式导入 | 统一提供仓库、`src/`、前端和测试 URL 根 |
| `src/tests/ai/datasets/` | 版本化 JSONL/manifest | AI/RAG 评测输入，不由普通 pytest 自动执行 |
| `src/tests/ai/results/` | 经审查的版本化普通 eval 结果 | 保留已登记、低敏、可追踪的普通评测结果 |
| `src/tests/.artifacts/` | 已忽略，按命令需要生成 | 唯一项目内临时测试输出根 |
| `release/evidence/` | 发布基线显式引用 | 低敏冻结机器证据，不是普通测试输出目录 |

更具体的 PostgreSQL 集成测试边界见 [`integration/postgres/README.md`](integration/postgres/README.md)。

## 后端质量命令

从仓库根执行：

```powershell
Set-Location src/backend
uv sync --frozen --all-groups
uv lock --check
uv run ruff check . ../tests/backend ../tests/integration/postgres
uv run ruff format --check . ../tests/backend ../tests/integration/postgres
uv run mypy app scripts
uv run pytest
Set-Location ../..
```

从 `src/backend/` 执行 `uv run pytest`，会按 `src/backend/pyproject.toml` 同时发现 `src/tests/backend/` 和 `src/tests/integration/postgres/`。如果只运行相关用例，必须在测试记录中写出精确路径和未运行范围，不能把局部结果描述为完整后端回归。

GitHub 托管 Linux runner 的后端 CI 在运行测试前创建仅 runner 可写的 `/run/user/1004` 目录，供隔离 Compose 门禁测试使用与正式 staging 相同的锁路径；这不改变正式机器的 UID 1004、锁或 Docker 校验。手动 G5 入口的负例在 Windows 应停于 Linux 宿主机检查，在 Linux runner 应停于 `crmdeploy` UID 检查；两者都不能进入真实部署。

## 前端质量命令

从仓库根执行：

```powershell
Set-Location src/frontend
npm ci
npm run lint
npm run typecheck
npm run test
npm run build
Set-Location ../..
```

隔离浏览器交互回归另需本机 Chrome 与本地 Next 服务。先在 `src/frontend/` 运行 `npm run dev -- --hostname 127.0.0.1 --port 3101`，再在同目录的另一个终端执行 `npm run test:ui`；默认目标为 `http://127.0.0.1:3101`，需要其他地址时用 `UI_BASE_URL` 环境变量指定。测试拦截 `/v1/` 请求并只使用合成数据，不访问真实店铺、TikTok 或 staging；该命令不替代 `npm run test` 与真实平台门禁。

验证跨版本 HTML 缓存时必须改用**生产构建**：先 `npm run build`，停止占用 3101 的开发服务，再在 `src/frontend/` 启动 `node node_modules/next/dist/bin/next start -H 127.0.0.1 -p 3101`；另一个 PowerShell 终端执行 `$env:UI_CACHE_EXPECT_PRODUCTION='1'; npm run test:ui`。此模式不会跳过带指纹 JS 的 `immutable` 断言，同时在生产构建上检查营销页无店铺引导。普通开发模式的 `test:ui` 会明确跳过该生产专用断言，不能作为发布缓存验收证据。

依赖已由可信缓存或当前工作区完整提供时，可按任务风险跳过重复安装，但必须记录实际环境。生产构建只证明前端构建成功，不替代浏览器、真实网络或 staging 验收。

## 隔离 PostgreSQL/pgvector 集成测试

从仓库根执行：

```powershell
.\src\scripts\run-postgres-integration-tests.ps1
```

脚本使用 Compose `test` profile 的隔离 `postgres-test` 服务、执行迁移和完整 pytest，并在结束后清理测试服务。不要使用会抢占正式后端端口的一次性容器方式代替该入口。

## 冒烟、真实平台与 AI eval

`ai/agent_automation_full_chain_live.py` 为显式启用的 staging 正式认证验收：`--phase inventory|prepare|run|cleanup --enable-live --manifest <src/tests/.artifacts/...json>`，可按 `--store us|xbm`、`--entry debug|suggest`、`--case <冻结用例>` 分批执行。仅在双自动化开关关闭时运行，不含发送/开启能力；使用既有有效管理员会话派生的内存凭证，保留 CSRF 与逐店授权。其精确合成入站、协作记录及会话记忆恢复由 controller 私有备份和清理批次处理，不能仅凭文件软删除宣称已清空。

`ai/logistics_event_model_live.py --enable-live --output <src/tests/.artifacts/agent-automation-20261102/新文件.json>` 仅限白名单 loopback 隔离测试库、test/integration 环境及全部平台能力关闭。它以声明的两段合成知识、模拟已核实物流节点调用实际 DeepSeek、BGE、PostgreSQL 检索和重排；逐条核对冻结引用原文与真实命中、独立复核和零投递。其组件结果不能替代正式 API、真实平台或买家送达证据；旧失败结果保留，新判据必须版本化并重新执行。

`ai/agent_reply_preferences_live.py` 是显式启用的合成表达偏好验收，不由普通 pytest 发现。仅在受控非生产进程中、使用当前已配置模型凭证运行：从 `src/backend/` 执行 `python ../tests/ai/agent_reply_preferences_live.py --enable-live`（可重复 `--case <名称>` 选择案例）。它用合成快照与物流事实调用实际 Worker、模型路由、流式汇总和独立复核；拒绝数据库访问，不读取真实买家或创建消息。输出含合成答复及独立模型语义评审，评审意见需要结合正文人工核对，不能将模型评分当作绝对事实；它不替代保存/发布/权限的隔离数据库测试或真实 TikTok 验收。输出只保存到 `src/tests/.artifacts/`。

- `src/tests/backend/runtime_infrastructure/test_health.py` 是确定性健康检查入口。
- `src/backend/scripts/verify_*.py` 只在其 README、任务或门禁明确要求的环境运行；脚本存在不代表真实环境已验收。
- `src/backend/scripts/verify_tiktok_readonly.py` 在真实只读冒烟成功时只向标准输出写入店铺、Webhook、订单、物流、会话和消息的聚合计数 JSON；第三方 HTTP 日志通过项目低敏结构化日志出口，不输出带签名的请求 URL。调用失败仍是非零退出，不得把部分成功计为 G1 通过。
- 真实 TikTok、真实 DeepSeek、50 客户端 SSE、本期 G6 连续 48 小时稳定性、备份和回滚需要隔离 integration/staging、精确授权、低敏数据和对应门禁记录。
- `backend/runtime_infrastructure/test_staging_g6_observer.py` 验证 G6 分钟槽位、缺口计数、低敏探针、告警持久化及固定资源/队列峰值汇总；真实 48 小时由 staging 主机私有采集器留证，本地测试不替代现场观察。已启动的原始采集器原计划 72 小时，本期报告截取同一原件前 48 小时。
- `src/tests/ai/datasets/` 中的数据集和 `src/tests/ai/results/` 中的版本化结果受版本、摘要、Provider、环境和数据用途约束。普通测试不得静默替换数据集、阈值或模型。
- 生产环境不运行真实模型离线评测或破坏性测试。

Phase 4 确定性回归从 `src/backend/` 执行，输入使用版本化数据集，未审查的新结果只写入临时输出根：

```powershell
uv run python -m scripts.evaluate_phase4 --dataset ../tests/ai/datasets/agent-phase4-v1.0.0.jsonl --output ../tests/.artifacts/ai/agent-phase4-deterministic.json
```

## fixture、helper 与测试数据

- 当前前端契约测试使用 `src/tests/frontend/helpers/paths.mjs`；没有独立共享 `src/tests/fixtures/`。只有出现真实跨测试复用时才创建其他 fixture/helper，禁止空目录占位。
- 测试数据必须固定、脱敏、可追踪；不得使用真实密钥、Token、生产数据或未经脱敏的客户消息。
- 本地管理员密码、OAuth/会话凭证和性能凭证池只能通过环境变量或仓库外安全文件注入，命令结束后按批准策略清理。
- 测试不得绕过店铺隔离、权限、CSRF、幂等、审计、DLP、真实平台开关或失败关闭。

## 输出、报告与证据

- 项目内临时日志、截图、覆盖率、浏览器结果、eval 输出和缓存只写入已忽略的 `src/tests/.artifacts/`。现有通用忽略规则仅为工具兼容保留，不是可新增的项目内输出根；敏感或大体积输出使用仓库外安全路径。
- 当前格式的正式 TR 只在产生真实测试事实时创建于 `docs/reports/tests/`，不得用计划或空模板代替。
- `release/evidence/` 只保存发布基线必须长期存在且通过低敏检查的机器证据。
- 每次交付列出真实命令、结果、环境、测试 SHA、覆盖的需求/门禁、未执行项和残余风险。历史结果不能冒充本次运行结果。

动态 Agent 本地协议边界评测（不代表真实模型路由质量）从 `src/backend/` 执行：

```powershell
uv run python -m scripts.evaluate_dynamic_agents --dataset ../tests/ai/datasets/agent-dynamic-contract-v1.0.0.jsonl --output ../tests/.artifacts/ai/agent-dynamic-contract.json
```

16 条版本化样例只用合成模型协议/工具结果验证边界；跨轮工具数量、绑定文件联合回答、会话记忆与真实数据库行为由后端和 PostgreSQL 测试验证。真实模型质量/时延需单独现场验收。

Agent 工具分类浏览器测试使用 `frontend/browser/fixtures/agent-tool-catalog.json` 的合成目录，其名称、描述、分类与参数来源为后端 agents/tools/metadata.py；不含真实店铺或 scope 授权。目录更新时同步此测试资产，浏览器用例核对搜索、绑定、知识计数、迟到响应与内部协作显示。工具与业务参数、返回值、迁移和隔离的后端验收入口为 test_agent_tool_suite.py、test_agent_business_tools.py、test_agent_product_details.py 与 integration/postgres/test_agent_collaboration.py。

2026-10-31：统一 PostgreSQL 入口将 AGENT_TEMPLATE_RUNTIME_TEST_DATABASE_URL 显式绑定到本轮隔离库，模板运行验收仍要求 DATABASE_URL、TEST_DATABASE_URL 与专用目标完全一致；不再强制统一入口访问旧任务的固定端口/库。未提供覆盖时保留原专库目标，不允许改指向业务库。

多个任务并行验收时，统一脚本支持 `-TestPort 56875` 并通过 POSTGRES_TEST_PORT 只绑定本机回环。默认仍为5433；每轮使用独立 COMPOSE_PROJECT_NAME，不停止占用其他端口的现有测试容器。

统一数据库脚本也支持 `-ProjectName`，默认按本次 PowerShell PID 生成独立项目名，并在 up/stop/rm 使用同一值。测试 URL 必须无 query，避免 asyncpg 通过 query 覆盖已校验的主机或账号。

脚本使用明确 IPv4 回环 `127.0.0.1`，避免 Windows 的 localhost 解析/连接回退拖延短生命周期验收。`-PytestArgs` 可传精确用例路径进行复现，固定加载后端 pyproject.toml；不传时仍执行完整回归，局部结果不能替代全量门禁。
