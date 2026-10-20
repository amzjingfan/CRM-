---
record_id: TR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-001-20261020-R01
record_type: test
revision: R01
status: PASS
task_id: MVP-WORKSPACE-CUSTOMER-SIDEBAR-001
tested_sha: 9cd859d637c9852d7780e929c0e8818d781bfa59
implementation_record: docs/records/implementation/IR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-001-20261020-R01.md
requirement_ids: [MVP-WORKSPACE-CUSTOMER-SIDEBAR-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05]
environment: Windows 11; isolated Docker PostgreSQL test profile; local Next.js 16.3.4 webpack production build; synthetic Chrome browser; staging scope check read-only
created_at: 2026-10-20T14:53:40Z
updated_at: 2026-10-20T14:53:40Z
supersedes: null
---

# 测试范围、环境与 TEST_LAYOUT

`TEST_LAYOUT: centralized`。后端从本任务隔离工作树运行项目标准 PostgreSQL 测试脚本，自动创建和移除 `postgres-test`；浏览器测试只用合成 API 拦截，不访问真实买家。staging 仅从现有运行后端读取一个渠道的连接状态与 Scope 布尔值，没有读取 Token、订单正文或执行平台写入。

# 命令和逐项结果

| 命令或核对 | 本次结果 |
|---|---|
| `src/scripts/run-postgres-integration-tests.ps1` | 2226 passed，3 skipped（POSIX bash 专用），测试容器已移除 |
| `ruff check app ../tests/backend ../tests/integration/postgres`；`ruff format --check ...` | 全部通过，262 个文件已格式化 |
| `mypy app scripts` | 188 个源文件通过 |
| `npm run lint`；`npm run typecheck`；`npm run test` | lint 0 error、4 warning（其中侧栏远程图片 2 项）；类型通过；契约 47/47 通过 |
| `npm run build -- --webpack` | 生产构建通过；普通 `npm run build` 因本地 worktree 的 `node_modules` 目录链接触发 Turbopack 文件根限制而失败，Docker 正式构建使用独立安装 |
| `node --test --test-concurrency=1 src/tests/frontend/browser/*.test.mjs`，本地生产模式、`UI_CACHE_EXPECT_PRODUCTION=1` | 42/42 通过，包括订单筛选、金额拆分、商品 SKU、优惠券草稿、原消息工作台回归 |
| staging 运行后端只读查询 TikTok 渠道连接状态和授权 Scope | 1 个已连接渠道；`seller.product.basic=true`、优惠券读取 Scope=true；未验证新端点的真实返回 |

# REQ/AC 或门禁与证据映射

- AC-01、AC-05：隔离 PostgreSQL 集成测试覆盖同店订单筛选和跨店拒绝；订单字段只展示真实同步值。
- AC-02：平台客户端契约测试覆盖 Product Basic 缺权先于 HTTP 失败、固定签名路径；浏览器覆盖分页商品卡和 SKU 展开。
- AC-03、AC-04：浏览器核对优惠券搜索、填入草稿而无消息外发；旧工作台筛选、翻译和发送审阅继续通过。

# 缺陷、未执行项与残余风险

旧浏览器 Mock 拦截器对新增侧栏 POST 返回错误形状，并将该只读 POST 误计为消息发送；已按新接口契约修正拦截器。订单旧记录缺新字段；商品标题和券编码搜索按平台页继续加载。尚未部署新后端/前端或调用真实商品、优惠券目录，现场验证属部署任务。没有运行 GitHub Actions，也没有向 TikTok 买家发送消息。

# 结论和复测条件

源码任务 AC-01～05 的本地验证通过。合并后从精确主线构建镜像，staging 手动发布与真实只读目录验证必须另行完成；此 PASS 不代表 staging 或 production 已发布。
