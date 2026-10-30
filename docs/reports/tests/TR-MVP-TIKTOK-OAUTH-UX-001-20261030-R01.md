---
record_id: TR-MVP-TIKTOK-OAUTH-UX-001-20261030-R01
record_type: test
revision: R01
status: PASS
task_id: MVP-TIKTOK-OAUTH-UX-001
tested_sha: be936358bdce4f633a51fe599a5e5a7bbc1e074b
implementation_record: docs/records/implementation/IR-MVP-TIKTOK-OAUTH-UX-001-20261030-R01.md
requirement_ids: [MVP-TIKTOK-OAUTH-UX-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
environment: Windows local worktree; Node/Next 16.4.2; Python 3.11/uv; local 127.0.0.1:3101 production build; synthetic browser API responses
created_at: 2026-10-30T03:20:11Z
updated_at: 2026-10-30T03:20:11Z
supersedes: null
---

# 测试范围、环境与 TEST_LAYOUT

`TEST_LAYOUT: centralized`。在独立工作树对最终源码提交运行合成前后端测试；浏览器只拦截本地 `/v1/`，没有访问 TikTok、staging 或真实店铺。

# 命令和逐项结果

- `src/frontend`: `npm run test`：55/55 通过；`npm run typecheck`：通过；`npm run lint`：退出 0，0 error、8 条既有其他文件 warning；`npm run build`：通过。
- `src/frontend`: 生产构建本地服务下，`node --test --test-name-pattern='store list renders|channel page has no duplicate|disconnected channel|legacy channel OAuth|completed OAuth job|multi-shop OAuth|expired store reauthorization' ../tests/frontend/browser/ui-regressions.test.mjs`：9/9 通过。
- `src/backend`: `uv run python -m pytest ../tests/backend/platform/test_tiktok_oauth.py -q`：53/53 通过；`uv run mypy app/integrations/oauth_service.py app/integrations/oauth_schemas.py`：通过；受影响文件 `ruff check` 与 `ruff format --check`：通过。
- `git diff --check origin/main...HEAD`：通过；主线同步冲突仅 `TASKS.md` 两条任务行，保留双方后重放成功。

# REQ/AC 或门禁与证据映射

- AC-01：既有添加店铺直达 OAuth 与多店选择浏览器用例通过。
- AC-02：已连接行无重新授权；断开行发起请求的 `store_id` 与回跳路径准确；截图所示卡片与全局按钮消失。
- AC-03：旧回跳转店铺页；完成任务但未查见已连接行时不报成功；稳定失败码显示原因和具体店铺重试按钮。
- AC-04：上述前后端、类型、lint、构建和差异检查通过。

# 缺陷、未执行项与残余风险

首次尝试 `npm run test:ui` 全文件集合时，回复预演测试依赖的本地端口 3124 未启动，同时对 3101 进行并行构建引发少数无关页面超时；该次全量命令退出 1，不计为通过。之后停止并行构建，在最终候选的生产构建上重跑本任务相关 9 项，全部通过。未执行真实平台 OAuth 或 staging 现场回归；本报告不代表发布验收。

# 结论和复测条件

本任务适用的本地验收通过。若合并前源码或 OAuth 接口变更，需重跑受影响测试；部署时另做真实店铺现场确认。
