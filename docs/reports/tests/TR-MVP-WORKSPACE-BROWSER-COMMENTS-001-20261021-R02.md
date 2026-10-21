---
record_id: TR-MVP-WORKSPACE-BROWSER-COMMENTS-001-20261021-R02
record_type: test
revision: R02
status: PARTIAL
task_id: MVP-WORKSPACE-BROWSER-COMMENTS-001
tested_sha: 975430475a03d04d91ccc6142eecfb8e0e70aaa7
implementation_record: docs/records/implementation/IR-MVP-WORKSPACE-BROWSER-COMMENTS-001-20261021-R02.md
requirement_ids: [MVP-WORKSPACE-BROWSER-COMMENTS-001]
acceptance_ids: [AC-01, AC-02, AC-03]
environment: Windows local tests; staging Rootless Docker and public HTTPS; synthetic Chrome browser against deployed staging page
created_at: 2026-10-21T09:00:19Z
updated_at: 2026-10-21T09:25:33Z
supersedes: docs/reports/tests/TR-MVP-WORKSPACE-BROWSER-COMMENTS-001-20261021-R01.md
---

# 测试范围、环境与 TEST_LAYOUT

沿用 R01 的集中测试布局。发布页面浏览器测试拦截 `/v1/` 使用合成数据，只核对 staging 实际交付的 HTML/JS 与交互，不访问真实买家 API，也不执行发送、退款或发券。

# 命令和逐项结果

- 最终源码上完整后端 `PYTHONPATH='.;../tests/backend' uv run python -m pytest ../tests/backend -q`：2221 passed、3 skipped、2 个依赖弃用 warning；修正 R01 中“最终提交未重跑完整后端”的历史缺口。定向后端 6/6、Ruff、mypy 及前端 47/47 契约、类型、lint 0 error/4 既有 warning、生产构建、49/49 本地生产浏览器结果沿用 R01。
- 受审主线及镜像 revision 核对、私有备份、六摘要预取、`ValidateOnly` 和 `Deploy` 全部通过。独立复核运行镜像摘要、11 个 CRM 容器、迁移头 `025_workspace_actions`、现有能力开关及公网 `/healthz`、`/v1/health`、`/v1/health/ready` 200。低敏与私有原件摘要见部署 JSON。
- `UI_BASE_URL=https://staging.overselfx.com node --test ../tests/frontend/browser/workspace-experience.test.mjs`：18/18 通过，涵盖十条注释的受影响交互；全部平台 API 请求由测试拦截。
- 内置浏览器读取原标签与新标签连续超时；桌面窗口截图亦超时，记录 `UI_UNAVAILABLE`。用户随后提供的真实已登录订单卡截图确认页面可用，同时发现“物流状态”把英文 `Delivered` 原样显示；此项现场验收失败并进入同任务返修。
- GitHub Actions 两个作业均在零步骤失败，没有测试日志，不计为 CI 通过。

# REQ/AC 或门禁与证据映射

- AC-01、AC-02：本地 49/49 与已部署页面 18/18 合成浏览器用例通过；后端未读汇总和店铺范围测试通过。
- AC-03：受影响后端、前端、构建、六摘要、staging 门禁与健康完成。真实登录态页面反馈揭示中文物流状态缺陷，须以修正后的 staging 版本复测。

# 缺陷、未执行项与残余风险

真实店铺数据未逐项登录态截图验收；已确认“物流状态”英文回退缺陷。TikTok 无值或上游延迟时显示空值/加载态。无 production 发布。staging 临时 GHCR 登录已注销，原业务容器配置保持。

# 结论和复测条件

源码、本地与已部署合成页面验证通过；真实登录态截图发现中文状态缺陷，因此整体为 `PARTIAL`，任务回到 `DOING` 返修。修正结果由后续修订记录。
