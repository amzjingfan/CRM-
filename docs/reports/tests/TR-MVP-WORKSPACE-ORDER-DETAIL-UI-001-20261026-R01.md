---
record_id: TR-MVP-WORKSPACE-ORDER-DETAIL-UI-001-20261026-R01
record_type: test
revision: R01
status: PASS
task_id: MVP-WORKSPACE-ORDER-DETAIL-UI-001
tested_sha: 5ff30c11120344e7b65df568542eff7f32dd5b36
implementation_record: docs/records/implementation/IR-MVP-WORKSPACE-ORDER-DETAIL-UI-001-20261026-R01.md
requirement_ids: [MVP-WORKSPACE-ORDER-DETAIL-UI-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05]
environment: Windows isolated worktree; Python 3.11.15; Node 22; Next 16.4.2 production build; synthetic Playwright browser with intercepted /v1/
created_at: 2026-10-26T06:30:23Z
updated_at: 2026-10-26T06:30:23Z
supersedes: null
---

# 测试范围、环境与 TEST_LAYOUT

`TEST_LAYOUT: centralized`。新增行为用例只使用合成买家、订单及掩码收件信息，不访问真实平台或发送消息。生产模式浏览器使用本地 Next 构建与拦截的 `/v1/` 响应。

# 命令和逐项结果

- 候选提交后 `uv run python -m pytest -q --tb=short`：2374 passed、43 skipped、退出 0。此前同一任务工作树首轮为 2373 passed、43 skipped、1 failed；失败为既有 `test_prefetch_resumes_verified_images_after_a_failed_pull` 在 Windows 本机 30 秒子进程超时，定向首轮重试也超时。候选提交后的完整重跑通过；没有删改该测试或放宽阈值。
- 候选提交后 `uv run python -m pytest ../tests/backend/domain/test_workspace_sidebar_live_orders.py ../tests/backend/platform/test_tiktok_read.py -q`：69 passed。新增断言覆盖详情掩码字段原样返回、订单列表不返回收件字段，既有身份不符用例保持通过。
- `uv run mypy app scripts`：210 个源文件无问题；受影响文件 `ruff check` 与 `ruff format --check` 通过。
- 候选提交后 `npm run build`、`npm run typecheck` 通过，`npm test` 48 passed；`UI_CACHE_EXPECT_PRODUCTION=1; npm run test:ui` 113 passed、0 skipped。订单详情用例核对电话与地址、默认两条物流、展开/收起、规格与卖家 SKU；完整物流弹层与翻译原路径也通过。
- `npm run lint`：0 errors、8 warnings（既有图片和导航规则）；`git diff --check` 通过。

# REQ/AC 或门禁与证据映射

AC-01 由后端详情与列表投影测试、既有跨买家拒绝用例支持；AC-02～AC-04 由工作台浏览器定向用例与全量生产模式回归支持；AC-05 本地质量与构建完成，staging 部署和实际订单字段可用性仍需现场证据。

# 缺陷、未执行项与残余风险

首轮镜像预取测试超时如实保留；候选 SHA 的全套重跑已通过。平台收件信息可为空或脱敏，合成测试不证明真实 TikTok 授权给出明文地址。没有执行真实买家外发、退款、生产部署或 GitHub Actions。

# 结论和复测条件

候选提交的本地行为与构建 **PASS**。部署后须核对新前后端同源镜像、手动门禁、公网健康和已登录订单详情；若官方收件字段被掩码，按原值显示而非绕过平台保护。
