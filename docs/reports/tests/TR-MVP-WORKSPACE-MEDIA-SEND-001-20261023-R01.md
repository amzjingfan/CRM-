---
record_id: TR-MVP-WORKSPACE-MEDIA-SEND-001-20261023-R01
record_type: test
revision: R01
status: PARTIAL
task_id: MVP-WORKSPACE-MEDIA-SEND-001
tested_sha: b457da5f6e72f6a63aeced994beaf4ab40da8712
implementation_record: docs/records/implementation/IR-MVP-WORKSPACE-MEDIA-SEND-001-20261023-R01.md
requirement_ids: [MVP-WORKSPACE-MEDIA-SEND-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
environment: Windows 11, Python 3.11, PYTHONUTF8=1, Next.js 16.4.2, isolated worktree, synthetic browser and HTTP fixtures
created_at: 2026-10-23T10:45:00Z
updated_at: 2026-10-23T10:45:00Z
supersedes: null
---

# 测试范围、环境与 TEST_LAYOUT

`TEST_LAYOUT: centralized`。源码 subject `b457da5f6e72f6a63aeced994beaf4ab40da8712`。后端平台请求使用 `httpx.MockTransport`，浏览器使用本地生产 Next 服务和合成 API 响应；所有媒体发送测试均没有连接真实 TikTok 买家。

# 命令和逐项结果

- `$env:PYTHONUTF8='1'; uv run pytest -q`（`src/backend`）：2349 passed、42 skipped、2 个第三方弃用警告，0 failed。
- `uv run pytest -q ../tests/backend/platform/test_tiktok_write.py ../tests/backend/platform/test_workspace_media.py`（`PYTHONPATH=.`）：25 passed，覆盖图片 multipart、视频初始化及顺序分片、官方上传域限制、消息载荷、媒体类型/大小和上传凭据身份/幂等键绑定。
- `uv run mypy app scripts`：209 个源码文件通过；`uv run ruff check . ../tests/backend ../tests/integration/postgres` 与 `uv run ruff format --check . ../tests/backend ../tests/integration/postgres`：通过，373 个文件格式合格。
- `npm test`：48 passed；`npm run typecheck` 与 `npm run build`：通过；`npm run lint`：0 error、7 warning，其中 5 条既有、2 条为动态媒体图片的 `no-img-element` 提示。
- `node --test ../tests/frontend/browser/*.test.mjs`：90 passed、1 skipped（生产缓存断言要求专用线上开关），0 failed。媒体浏览器用例验证审阅前零请求、确认后一次上传和一次发送、相同幂等键、取消零请求及小视频拒绝。
- 使用本地 `nginx:1.27.5-alpine` 镜像对 `nginx-tunnel.conf` 执行 `nginx -t`：语法通过。三份配置均静态核对媒体精确路径 105 MiB 和 720 秒，普通路径保持 10 MiB。
- `git diff --cached --check` 和后续差异检查通过。

# REQ/AC 或门禁与证据映射

AC-01 由前后端文件门禁和浏览器小视频案例验证。AC-02 由浏览器取消/确认请求计数验证。AC-03 由工具层既有发送状态测试、媒体凭据及协议定向测试验证。AC-04 由全量回归、类型/格式/构建和 Nginx 语法及配置静态核对验证。

# 缺陷、未执行项与残余风险

第一次直接运行 `uv run pytest -q` 得到 2348 passed、1 failed、42 skipped；失败发生在仓库布局测试用 Windows 默认 GBK 解码 `git ls-files` 的中文路径。按项目既有 UTF-8 测试环境重跑后全量通过，没有修改测试或降低断言。公网 staging Nginx 和 TLS Nginx 配置未在目标服务器上执行 `nginx -t`；只验证了内层隧道配置和三份文件的精确规则。未做真实 TikTok 媒体外发、staging 登录态验收或 production 发布。GitHub CI 仍需在账户账单限制解除后实际执行，不以本地结果替代。

# 结论和复测条件

本地候选行为与静态门禁通过；由于父分支合并、GitHub CI 和 staging 现场门禁未完成，本记录为 `PARTIAL`。部署前须在目标两层代理执行语法检查，再按批准范围完成已登录验收；真实买家外发另需明确测试窗口和授权。
