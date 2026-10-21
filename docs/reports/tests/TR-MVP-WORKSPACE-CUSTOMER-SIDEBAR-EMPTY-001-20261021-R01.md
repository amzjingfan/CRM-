---
record_id: TR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-EMPTY-001-20261021-R01
record_type: test
revision: R01
status: PARTIAL
task_id: MVP-WORKSPACE-CUSTOMER-SIDEBAR-EMPTY-001
tested_sha: 7cd8e43e27544036027f2b2d8be2a5fc411d97ca
implementation_record: docs/records/implementation/IR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-EMPTY-001-20261021-R01.md
requirement_ids: [MVP-WORKSPACE-CUSTOMER-SIDEBAR-EMPTY-001]
acceptance_ids: [AC-01, AC-02, AC-03]
environment: Windows PowerShell, CPython 3.11.15, uv frozen lock, staging read-only TikTok probe
created_at: 2026-10-21T01:05:00Z
updated_at: 2026-10-21T01:05:00Z
supersedes: null
---

# 测试范围、环境与 TEST_LAYOUT

测试源码位于集中布局 `src/tests/backend/platform/`；临时只读现场探针保留于已忽略的 `src/tests/.artifacts/`，不提交客户数据。现场只调用官方读取接口，不触发外发或订单写入。

# 命令和逐项结果

- 修复前对截图会话运行 staging 只读 `search_sidebar_orders`：复现 `THIRD_PARTY_ERROR` 与页面精确错误文案。分段探针确认官方会话身份成功，订单搜索返回 `data` 键 `next_page_token,total_count`、总数为零、无下一页，错误发生于 `orders` 缺失校验。
- 测试先行：`uv run --frozen python -m pytest ../tests/backend/platform/test_tiktok_read.py -q -k 'omitted_orders or missing_orders'`：修复前 1 failed / 4 passed；修复后 5 passed。
- 候选提交后：`uv run --frozen python -m pytest`：2217 passed / 29 skipped；PostgreSQL 环境依赖用例跳过。
- `uv run --frozen ruff check app/integrations/tiktok_read.py ../tests/backend/platform/test_tiktok_read.py`、`ruff format --check` 与 `mypy app/integrations/tiktok_read.py` 均通过；`git diff --check` 通过。

# REQ/AC 或门禁与证据映射

- AC-01：零订单省略列表的回归测试及现场响应结构对应。
- AC-02：总数非零、非空翻页、显式 `orders: null`、缺总数四种响应均维持结构异常。
- AC-03：本地回归通过；staging 新镜像部署与同一会话复测尚待执行。

# 缺陷、未执行项与残余风险

实际登录页面在本记录时仍运行旧 backend；不能宣称用户截图故障已在线修复。未执行真实买家消息与任何高风险写入，因为此任务仅涉及读取。

# 结论和复测条件

源码行为已验证；等待从合入主线构建 backend、staging 手动发布，再用同一授权会话只读确认从 502 变为零订单，方可把现场结论改为 PASS。
