# MVP/生产门禁收口实施计划

> 分支：`fix/mvp-production-gates`。按测试驱动方式逐项实施；每个阶段验证通过后再提交。

**目标：** 关闭前端 3 个 High，发布并固定容器摘要，交付 staging/回滚门禁工具，同时保持生产不放行。

**架构：** 前端使用上游支持的 Next.js 16 修复线；GitHub Actions 负责 GHCR 构建发布；生产 Compose 只消费不可变镜像；PowerShell 脚本在专用 staging runner 上完成预检、候选部署、紧急关闭和镜像回滚。

**技术栈：** Next.js/Node/npm、Docker Buildx/Compose、GHCR、GitHub Actions、PowerShell 5.1/7、Node 内置测试与 pytest。

## Task 1：建立门禁失败测试

**文件：**
- 修改：`CRM智能聊天系统/frontend/tests/compose.test.mjs`
- 新增：`CRM智能聊天系统/backend/tests/test_production_gate_scripts.py`

1. 增加断言：Next.js 必须为安全版本、生产外部镜像必须带完整 digest、生产应用服务不得本机构建、Node 基础镜像必须固定 digest。
2. 增加脚本契约测试：拒绝 production、拒绝浮动镜像、拒绝缺失环境文件，dry-run 不泄露秘密。
3. 运行定向测试并确认因实现尚不存在而失败。

## Task 2：升级前端安全依赖

**文件：**
- 修改：`CRM智能聊天系统/frontend/package.json`
- 修改：`CRM智能聊天系统/frontend/package-lock.json`
- 按构建结果最小修改：`CRM智能聊天系统/frontend/next.config.ts` 或页面类型

1. 固定 `next`、`eslint-config-next` 为 `16.3.4` 并刷新 lockfile。
2. 运行 lint、typecheck、测试、build 和高危审计。
3. 只修复 Next.js 16 真实暴露的兼容问题，不做无关重构。

## Task 3：固定外部镜像和生产消费契约

**文件：**
- 修改：`CRM智能聊天系统/Dockerfile.frontend.prod`
- 修改：`CRM智能聊天系统/Dockerfile.model-service`
- 修改：`CRM智能聊天系统/docker-compose.prod.yml`
- 修改：`CRM智能聊天系统/.env.example`
- 修改：相应契约测试

1. 固定 Node、uv 多架构摘要和四个运行时外部镜像摘要。
2. 生产后端/Worker/Jobs/Agent Worker/前端/检索模型服务只接受 `repository@sha256:...`。
3. 重置生产应用服务继承的 `build`，避免目标主机构建。
4. 运行 Compose 契约测试和 `docker compose config --services`。

## Task 4：实现 GHCR 发布工作流并取得真实摘要

**文件：**
- 新增：`.github/workflows/publish-images.yml`
- 新增：`release/images/mvp-production-gates.json`

1. 添加仅需 `contents: read`、`packages: write` 的 Buildx 工作流；固定第三方 Action 版本。
2. 首次加入受限分支触发器，推送已通过本地验证的候选提交。
3. 从成功运行的输出/制品取得应用 RepoDigest；bootstrap 先记录后端和前端，最终 main 再补齐检索模型服务并写回证据。
4. 删除一次性分支触发器，正式保留 `workflow_dispatch`。

## Task 5：实现 staging 预检与回滚演练

**文件：**
- 新增：`CRM智能聊天系统/scripts/Test-StagingProductionGates.ps1`
- 新增：`CRM智能聊天系统/scripts/Invoke-StagingRollbackDrill.ps1`
- 新增：`.github/workflows/staging-gates.yml`
- 修改：`CRM智能聊天系统/deploy/production/README.md`

1. 让 Task 1 的失败测试覆盖输入校验和秘密不回显。
2. 实现 staging-only 参数、严格仓库白名单、合并 Compose image/build 结构检查、低敏健康检查和 JSON 证据。
3. 实现先关闭能力再切换三类上一版本摘要的回滚顺序；WhatIf/拒绝确认只允许 `not_executed`。
4. 通过 Windows PowerShell 5.1 与 PowerShell 7 语法检查和 dry-run 测试。

## Task 6：同步项目证据并走 GitHub Flow

**文件：**
- 修改：`架构师/验收-001-CROSS-真实环境生产放行检查表-v1.1.md`
- 修改：`release/baselines/v0.1.0-mvp.20260907.json`（只追加后续门禁关系，不改历史标签绑定）或新增门禁证据文件
- 新增：`共享记忆文档/实施记录/PhaseX-PX-00-全栈开发工程师Agent-MVP生产门禁收口-001.md`
- 修改：`共享记忆文档/实施记录索引.md`

1. 记录已关闭的工程门禁及仍未执行的真实门禁，不伪造测试工程师结论。
2. 运行完整后端、前端、审计、Compose 和文档一致性验证。
3. 提交、推送、创建 PR；等待 CI 与独立人工审阅。
4. squash merge 后再从 `main` 手工触发正式 GHCR 发布；如最终 digest 与候选不同，使用独立证据 PR 固定最终值。
