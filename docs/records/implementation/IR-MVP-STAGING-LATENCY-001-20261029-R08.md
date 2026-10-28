---
record_id: IR-MVP-STAGING-LATENCY-001-20261029-R08
record_type: implementation
revision: R08
status: FINAL
task_id: MVP-STAGING-LATENCY-001
base_sha: 4142423def38f9e3a25563008db4b8586f416c83
final_sha: c1fcc1c74dbb073b2d560c178499b2ac5ec99f2e
requirement_ids: [MVP-STAGING-LATENCY-001]
acceptance_ids: [AC-05, AC-06]
test_record: docs/reports/tests/TR-MVP-STAGING-LATENCY-001-20261029-R08.md
review_record: docs/reports/reviews/RR-MVP-STAGING-LATENCY-001-20261029-R08.md
created_at: 2026-10-29T00:48:00+08:00
updated_at: 2026-10-29T00:48:00+08:00
supersedes: docs/records/implementation/IR-MVP-STAGING-LATENCY-001-20261028-R07.md
---

# 实施目标与范围

门店设置页原先同时请求店铺和渠道，等待两条请求全部完成才显示；公网链路抖动时，任一路延迟或失败都会阻塞整表。`c1fcc1c7` 增加一次性读取当前用户可见的 TikTok 店铺授权接口，页面仅发起该请求。该接口重用已有店铺授权范围与 `settings.channels` 权限，并在服务端只聚合相同店铺的渠道；没有迁移、写入、缓存或发送行为。

# 变更及回显

页面首次加载仍显示加载态；后续刷新保留最近一次已验证的行，标记刷新状态。503 时保留这些行并提示错误和重试，401/403 时清空行。重叠请求只采用最新响应。别名 PATCH 成功后立即更新本地行，授权 DELETE 成功后立即移除行，再发起核对请求。上述行为均有生产浏览器回归。API 契约已同步至 `docs/architecture/API.md`。

# 发布边界与限制

用户要求 staging 只部署当前性能修复。从当前运行的性能专用 release `f9bfc109` 摘取本次提交，形成 release `18cea7f2`，相对旧 release 只增加同一接口、页面、客户端方法、测试和 API 文档。当前运行后端 `e64ef52c` 是 release 基线的祖先，其后端构建输入差异仅为本次三份 stores 文件；动态 Agent 的新主线改写不在该 release。前后端 linux/amd64 镜像已本机构建，OCI revision 为 `18cea7f2`。GHCR 临时登录被自动策略拒绝，已有 Docker 凭据推送返回 `unauthorized`；**没有发布镜像或部署 staging**。保留旧镜像和全部运行开关，待可用的受控私有镜像发布方式后继续备份、ValidateOnly、Deploy 和现场验收。
