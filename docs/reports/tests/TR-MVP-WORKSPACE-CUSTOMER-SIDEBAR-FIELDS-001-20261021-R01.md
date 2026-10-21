---
record_id: TR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-FIELDS-001-20261021-R01
record_type: test
revision: R01
status: PASS
task_id: MVP-WORKSPACE-CUSTOMER-SIDEBAR-FIELDS-001
tested_sha: 736c214ed457332ac9316301ea7a6b8976433fe3
implementation_record: docs/records/implementation/IR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-FIELDS-001-20261021-R01.md
requirement_ids: [MVP-WORKSPACE-CUSTOMER-SIDEBAR-FIELDS-001]
acceptance_ids: [AC-01, AC-02, AC-03]
environment: Windows, CPython 3.11.15, Node 24.19.0, Chrome headless, local production Next build with intercepted API
created_at: 2026-10-21T02:07:22Z
updated_at: 2026-10-21T02:07:22Z
supersedes: null
---

# 测试范围、环境与 TEST_LAYOUT

项目 `src/tests/` 集中测试布局。后端平台和投影采用固定合成数据；浏览器拦截 `/v1/` 请求，生产 Next 构建运行于本机隔离端口。三张用户截图作为 staging 现状资料，不能替代新版本的真实 UI 验收。

# 命令和逐项结果

- `uv sync --frozen --all-groups`、`npm ci --no-audit --no-fund`：本工作树依赖安装成功。
- 首次 `uv run pytest ../tests/backend` 因 Windows `PYTHONPATH` 未包含测试公共目录，22 个模块收集失败；补齐 backend 与 `src/tests/backend` 路径后原命令重跑：`2220 passed, 3 skipped`，2 项第三方弃用 warning。受影响单文件另有 `13 passed`。
- `uv run ruff check app ../tests/backend`、`uv run ruff format --check app ../tests/backend`、`uv run mypy app scripts`：通过，mypy 188 个源码文件无问题。
- `npm run typecheck`、`npm run lint`、`npm run test`：通过；lint 0 error、4 个既有 warning，前端契约 47/47。
- `npm run build`：最终源码的生产构建和 TypeScript 检查通过。
- `npm run test:ui`：最后一次物流空值细化前，全套合成浏览器 43 passed/1 production-cache 专项 skipped；细化后订单受影响 2/2、商品与优惠券 1/1 重新通过。合成订单、商品、优惠券截图保存在忽略的 `src/tests/.artifacts/customer-sidebar-real-fields/`，未提交真实买家资料。
- `git diff --check` 与针对凭证标记的源码/文档扫描无异常；未调用 TikTok 外发、退款或发券接口。

# REQ/AC 或门禁与证据映射

- AC-01：后端真实支付时间投影用例；浏览器四种订单状态、详情按需加载和缺值显示用例。
- AC-02：后端金额对象解析与未知结构用例；浏览器商品状态、SKU、优惠券金额/状态/展示渠道用例。
- AC-03：完整后端、前端契约、静态检查、生产构建及受影响浏览器回归。

# 缺陷、未执行项与残余风险

未运行隔离 PostgreSQL 集成门禁：本变更无迁移或新数据库查询，现有本地订单 `paid_at` 只增加只读投影。未在本记录执行 staging 新版本发布或真实页面验收；由独立部署任务验证。GitHub Actions 不作为本次门禁。

# 结论和复测条件

源码验收通过；若真实 TikTok 优惠券金额结构、产品状态或订单时间字段与本次证据不符，必须只读定位后修订，不输出原始对象或伪造金额。
