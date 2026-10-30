---
record_id: TR-MVP-WORKSPACE-TIKTOK-RICH-MESSAGES-001-20261030-R01
record_type: test
revision: R01
status: PARTIAL
task_id: MVP-WORKSPACE-TIKTOK-RICH-MESSAGES-001
tested_sha: 60265d6566fca45ef1196ac777ea281be0662016
implementation_record: docs/records/implementation/IR-MVP-WORKSPACE-TIKTOK-RICH-MESSAGES-001-20261030-R01.md
requirement_ids: [MVP-WORKSPACE-TIKTOK-RICH-MESSAGES-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
environment: Windows local, CPython 3.11.15, isolated PostgreSQL pgvector:pg16, Node 24.19.0, Next 16.4.2
created_at: 2026-10-30T15:58:12Z
updated_at: 2026-10-30T15:58:12Z
supersedes: null
---

# 测试范围、环境与 TEST_LAYOUT

`TEST_LAYOUT: centralized`。使用合成消息，不读取买家正文到测试报告，不发 TikTok 写请求。只读 staging 探查确认实际占位类型含 image、video、emoticons、product_card、order_card、logistics_card、buyer_enter_from_order；实际只读平台样本确认图片 URL/尺寸、视频 URL/封面/到期、卡片 data 字段存在。探查只输出类型、字段名和聚合数量。

# 命令和逐项结果

- 红测：新增富消息用例先复现 Webhook 没有类型字段和 `[TikTok IMAGE]`、`[TikTok PRODUCT_CARD]` 占位，2 项失败；修复后本组 5 项通过。
- `uv run python -m pytest -c pyproject.toml ../tests/backend -q --tb=short`：`2707 passed, 4 skipped`，最终 subject 后重跑。首次全量运行发现旧合成夹具缺少新增字段，补齐并验证持久化卡片元数据后全绿。
- 隔离 PostgreSQL：`docker compose ... --profile test up -d --wait postgres-test`、`uv run --frozen alembic upgrade head`、`TEST_DATABASE_URL=... uv run python -m pytest -c pyproject.toml ../tests/integration/postgres/test_tiktok_conversation_sync_postgres.py -q`：`5 passed`，随后停止并移除测试容器。旧占位按原 ID 修复且不重复消息。
- `uv run ruff check . ../tests/backend ../tests/integration/postgres`：通过；`uv run ruff format --check . ../tests/backend ../tests/integration/postgres`：568 文件已格式化；`uv run mypy app scripts`：303 源文件无错误。
- `npm run typecheck`、`npm run lint -- --quiet`、`npm run build`：通过；`npm run test`：74/74。
- 开发构建、串行浏览器全套：209 passed、1 skipped；生产构建专属 HTML 缓存 2/2、富消息浏览器 1/1。生产构建全套另有 Agent 模板归档搜索用例 1 项失败，该测试和 Agent 页面均未由本提交改动；此故障不作为本任务消息链路通过证据。

# REQ/AC 或门禁与证据映射

AC-01：Webhook/只读解析单元与富消息浏览器；AC-02：隔离 PostgreSQL 回填测试及平台消息 ID 幂等；AC-03：全量后端、前端类型/构建/合同、静态检查与安全 URL 单元；AC-04：待 staging 发布与现场补录。

# 缺陷、未执行项与残余风险

生产构建全套 Agent 模板搜索用例在归档后立即检查过滤数量时得到 0 而期望 1；开发构建全套通过，富消息及缓存生产用例通过。由于该用例和页面在本 subject 未改动，另行处理其稳定性，不把该失败写成通过。尚未用真实买家消息做发送测试，staging 旧消息补录和视觉验收未执行；短期媒体 URL 过期只能显示封面/提示。

# 结论和复测条件

源码 AC-01～03 的适用验证通过，AC-04 保持待验，故本记录为 PARTIAL。staging 精确受审镜像、私有备份、ValidateOnly、Deploy 和旧消息只读补录完成后另定 R02。
