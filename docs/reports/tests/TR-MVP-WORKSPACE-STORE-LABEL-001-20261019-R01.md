---
record_id: TR-MVP-WORKSPACE-STORE-LABEL-001-20261019-R01
record_type: test
revision: R01
status: PASS
task_id: MVP-WORKSPACE-STORE-LABEL-001
tested_sha: 6a3c5abc7ca8e07fdb52c6006e290e2076c38d5b
implementation_record: docs/records/implementation/IR-MVP-WORKSPACE-STORE-LABEL-001-20261019-R01.md
requirement_ids: [MVP-WORKSPACE-STORE-LABEL-001]
acceptance_ids: [AC-01, AC-02, AC-03]
environment: Windows Node 24 与 Next.js 16.3.8；本地合成 Chrome；staging Rootless Docker 与已登录工作台
created_at: 2026-10-19T10:48:37+08:00
updated_at: 2026-10-19T11:43:27+08:00
supersedes: null
---

# 测试范围、环境与 TEST_LAYOUT

集中式前端测试位于 `src/tests/frontend/`。合成浏览器拦截全部 `/v1/` 请求，无真实消息写入。行为 subject 为已合入 `main` 的 `6a3c5abc7ca8e07fdb52c6006e290e2076c38d5b`；镜像构建基线 `e82b8ddba4297cabbc443311bb852952bb61d765` 与 subject 的前端输入一致。运行环境为 staging Rootless Docker，实际页面核验沿用用户已登录的浏览器会话，只读读取筛选项。

# 命令和逐项结果

- 修复前，定向 `node --test --test-name-pattern='workspace store filter shows authorized names' ../tests/frontend/browser/ui-regressions.test.mjs` 失败：实际 `[全部店铺, 00000000]`，预期两个店铺名称。
- 修复后同一浏览器测试通过，选择第二店铺使筛选结果为空时，两个名称选项仍存在。
- 在合入 SHA 上 `npm run lint`：0 错误，2 条原有内部跳转警告；`npm run typecheck`：通过；`npm run test`：47/47；`npm run build`：通过。
- 以合入 SHA 的生产构建运行 `UI_CACHE_EXPECT_PRODUCTION=1`、`npm run test:ui`：31/31，通过缓存和店铺筛选回归。早先开发模式下缓存用例失败是运行模式不符；生产构建复测通过。
- `git diff --check`：通过。源码 PR #417 的三个文件范围和合并 SHA 已复核。
- `docker buildx build --platform linux/amd64 --load`：通过；原始合入 SHA 镜像 RepoDigest 为 `sha256:e3c8f57b433b614b3773685ddcfa26a574532f6e2cdac510af5d986beef6f641`，GHCR 读回为单一 OCI manifest、9 层、压缩层合计 63,997,424 字节。独立 G5 后端提交使 main 前进后，`git diff --quiet 6a3c5abc..e82b8ddb -- src/frontend src/docker/Dockerfile.frontend.prod` 通过；从新 main 重建并推送前端镜像，linux/amd64、OCI revision=`e82b8ddba4297cabbc443311bb852952bb61d765`、RepoDigest=`sha256:77a710880ea63a804de53f57b421c75ebed96a56c87c7efbd86a8e2877344051`。
- staging 前置只读快照确认原前端 `sha256:1addb6c8…2db795`、后端 `sha256:2dc92fe5…c2f258`、检索 `sha256:feeee5a3…623059` 和 G3 单店人工发送、Webhook 读、翻译模式。`Test-StagingProductionGates.ps1 -ValidateOnly` 通过，见[预检证据](../../../release/evidence/staging/crm-staging-store-label-validate-20261019.json)，SHA-256 `c6a7621757d4780eb95209de40f7cbc76cef00824811251e324c155d6820bce4`。
- 首次直接 GHCR 拉取停在首个 1 MiB 数据块；取消后核对原前端仍健康、部署锁已释放、运行摘要未变。候选为单平台 OCI manifest，现有可续传脚本只接受 OCI index；一次性导入脚本复用其鉴权、分段下载、逐层 SHA-256 校验和 Rootless containerd 导入，15/15 分段完成，Docker `RepoDigests` 精确等于候选摘要。脚本没有切换容器，临时 GHCR 登录已注销且认证项为 0。
- 重跑同一 staging 部署门禁通过，[低敏部署证据](../../../release/evidence/staging/crm-staging-store-label-deploy-20261019.json) SHA-256 `493482bcddb777f744634df315814a414a3d48effa0c5f18740834aaa98d89a4`：新前端摘要准确；后端/检索摘要不变；迁移头 `024_tiktok_oauth_jobs`；11 个服务正常、前端/后端/代理/检索健康；三个公网健康接口 200，固定出口与配置一致，原单店人工发送、Webhook 读取和工作台翻译保持开启，LLM/SSE 与自动回复保持关闭，`production_release=false`。
- 从本机独立请求 `/healthz`、`/v1/health`、`/v1/health/ready`、`/workspace` 和 `/settings/stores` 均返回 200。用户已登录工作台只读 DOM 实测 `<select aria-label="店铺">` 的选项为“全部店铺”及三个授权店铺名称，不再显示 `74bd2ebb` 截断 ID。没有触发发送按钮。下载期间 main 仅添加 G5 证据与文档；`git diff --quiet e82b8ddb..7d0a131 -- src/frontend src/docker/Dockerfile.frontend.prod` 通过。

# REQ/AC 或门禁与证据映射

AC-01 与 AC-02：合成浏览器真实渲染 `<select>`，确认名称、筛选 ID 和空列表后的选项保留；登录 staging 页面显示真实店铺名称。AC-03：本地质量、生产构建、staging 手动部署、健康、模式和实际界面复核均通过。

# 缺陷、未执行项与残余风险

GitHub PR 自动 Actions 两个作业在步骤开始前失败，未产生可用测试日志；本轮没有主动运行 Actions。浏览器 UI 控制在一次返回会话列表操作中超时，但直接读取真实 `<select>` 选项成功；未保存可展示截图。未向 TikTok 买家发送消息，未部署 production。

# 结论和复测条件

`PASS`：AC-01～AC-03 已有本轮源码测试、staging 门禁与登录页面只读证据。此结论只覆盖店铺筛选文字和选项稳定性；不声称生产发布或真实消息发送验收。
