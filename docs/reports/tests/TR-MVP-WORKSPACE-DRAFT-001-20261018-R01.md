---
record_id: TR-MVP-WORKSPACE-DRAFT-001-20261018-R01
record_type: test
revision: R01
status: PASS
task_id: MVP-WORKSPACE-DRAFT-001
tested_sha: 07dede246c793cf5252624f59e35938f0ae46244
implementation_record: docs/records/implementation/IR-MVP-WORKSPACE-DRAFT-001-20261018-R01.md
requirement_ids: [MVP-WORKSPACE-DRAFT-001]
acceptance_ids: [AC-01, AC-02, AC-03]
environment: Windows 本地 Node 24 与 Next.js 16.3.8；合成浏览器 API；staging 手动部署真实服务只读核验
created_at: 2026-10-18T11:13:00+08:00
updated_at: 2026-10-18T11:35:00+08:00
supersedes: null
---

# 范围和结果

`CANDIDATE_SUBJECT_SHA=07dede246c793cf5252624f59e35938f0ae46244`。在该合入后的干净 worktree 执行：

- `npm ci --no-audit --no-fund`：成功，安装 390 个包。
- `npm run test`：47/47 通过。
- `npm run lint`：0 错误，2 条既有 Next.js 内部导航警告。
- `npm run typecheck`：通过。
- `npm run build`：通过。
- 本地生产构建服务上 `npm run test:ui`：29 通过、1 条仅因未设置生产缓存检查变量而跳过；补设 `UI_CACHE_EXPECT_PRODUCTION=1` 后缓存文件的 2/2 检查通过。30 条浏览器用例无失败，包括 903×787、1440×768、390×768 视口下长 AI 建议、100 条历史、草稿输入及按钮启用，网络发送调用为零。
- `git diff --check`：通过。源码 PR #355 已合并；未运行 GitHub Actions。

# staging 交付和只读检查

- 前端镜像 OCI revision 精确为合入 SHA，单一 `linux/amd64` 运行清单，GHCR index 与 Rootless Docker RepoDigest 同为 `sha256:1addb6c82f9a76d27ec59e999e8dea172bc49f06227808ecee00e28a892db795`。
- 已审核 Git bundle SHA-256 为 `ef91d74d255de71a97eace8a761449ef51d78d7f4a1d3e60ef6f8a1b70642e8e`；服务器干净 checkout HEAD 精确匹配合入 SHA。
- 六个新旧镜像角色预取和 staging validate/deploy 门禁通过。原后端 `sha256:8913c09ceffd0ea637a7f3b5d982521e2dd9980d507006a2157ac0a9bc83a958`、检索 `sha256:feeee5a3327bc7d18e49bf534dad431adcb12a3089b025bb068a687662523059` 未改变；新前端运行健康。三个公网健康端点 `/healthz`、`/v1/health`、`/v1/health/ready` 均为 200，`/workspace` HTML 为 200。
- 公网 Next.js CSS 含 `.ai-suggestion>div:first-child{...max-height:min(20vh,140px);overflow-y:auto}` 和 `.composer{...flex-shrink:0}`；新资源已可获取。
- 运行时 `REAL_TIKTOK_READ_ENABLED`、webhook、店铺限定人工发送及工作台翻译仍为 true；高风险写入、LLM、自动回复仍为 false。没有调用消息发送 API。
- 正式低敏证据：[预取](../../../release/evidence/staging/crm-staging-workspace-composer-prefetch-20261018-r01.json)、[验证](../../../release/evidence/staging/crm-staging-workspace-composer-validate-20261018-r01.json)、[部署](../../../release/evidence/staging/crm-staging-workspace-composer-deploy-20261018-r01.json)。现场原件 SHA-256 依次为 `b5a2184c7a21866d59c180ba6fb06432a34ce51ec57b0389bc9cca015a9aa611`、`a4e0a7b2f5fd991f8ca16498432428547f18ef0236acafcb29e97cbab4578d7f`、`28b5e10c006a89920c05c50da54c8c3dad8cc19f58ca1a371b6002b7652ede94`。

# AC 映射与现场验收

AC-01、AC-02：合成浏览器中三种视口下，输入框与按钮保持在视口内、草稿输入成功、按钮启用且无自动发送。AC-03：合入提交的静态检查、构建和 staging 手动门禁通过；浏览器控制恢复后，已登录 in-app browser 的真实会话 `jesus00147` 显示“真实 TikTok 发送”，输入区在 597×894 视口内可见。输入 11 字“草稿输入验证（不发送）”后，AX 显示 11/2000 且“确认并发送”由禁用变为可用；截图保留在本任务工具结果。随后清除测试草稿，AX 恢复 0/2000 和按钮禁用；没有点击发送按钮，消息列表未新增。此前短暂的浏览器接口超时为 `UI_UNAVAILABLE`，已在同一轮现场复测中解除。

# 残余风险与恢复

本次现场只验证草稿输入和按钮状态，没有再次向真实买家发送消息；此前受控双向发送验收为独立任务证据。本报告的后端与权限核对仅对应本次前端部署及草稿验收窗口；随后独立 G5 窗口临时切换后端并关闭真实发送，须在该窗口恢复后复核当前模式。若新前端现场异常，可按私有恢复快照中的旧前端不可变摘要，通过同一受审 staging 门禁恢复。production 未发布。
