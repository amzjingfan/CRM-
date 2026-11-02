---
record_id: TR-MVP-WORKSPACE-ORDER-TRACKING-CONSISTENCY-001-20261102-R04
record_type: test
revision: R04
status: PARTIAL
task_id: MVP-WORKSPACE-ORDER-TRACKING-CONSISTENCY-001
tested_sha: b98b955b962df638d9a899fc17c2396cbcb2ad54
implementation_record: docs/records/implementation/IR-MVP-WORKSPACE-ORDER-TRACKING-CONSISTENCY-001-20261102-R02.md
requirement_ids: [MVP-WORKSPACE-ORDER-TRACKING-CONSISTENCY-001]
acceptance_ids: [AC-03, AC-05, AC-06]
environment: staging read-only runtime inspection and Codex in-app browser, 2026-11-02
created_at: 2026-11-02T20:41:42+08:00
updated_at: 2026-11-02T20:41:42+08:00
supersedes: docs/reports/tests/TR-MVP-WORKSPACE-ORDER-TRACKING-CONSISTENCY-001-20261102-R03.md
---

# 测试范围、环境与 TEST_LAYOUT

`TEST_LAYOUT: centralized`。本次只读核对已合并源码、staging 实际镜像和公开健康路径，并尝试在 Codex 内置浏览器验收已登录订单。未发送买家消息、未退款、未改生产。

# 命令和逐项结果

- PR #717 已 squash 合入 `694c52219f6d00fe17e29bc970f414c229c6d8ea`。`git merge-base --is-ancestor 694c5221 a38f9751` 为 0；已部署前端的源码修订 `a38f97516ac0750f064c16fb8738345863acea82` 包含该提交。三个承运商展示文件在两修订间无差异。
- SSH 只读 `docker ps` 和 `docker image inspect`：staging 前端为 `ghcr.io/cp11-gh/crm-frontend@sha256:2e6fb84d78d9cc9f98260a7d4a4b306bb90a6219892ebab6306f30ae94d22651`，后端为 `ghcr.io/cp11-gh/crm-backend@sha256:71237e8cb0aac215891ee08e0d0933e6db8a0fb689d07abf20cbc1fe54f0f4af`，12 个容器运行。当前运行镜像由另一项已合并发布切换；本任务旧候选 `sha256:fd23461c...` 未部署，避免覆盖较新的 Agent 代码。
- 公网 `/healthz`、`/v1/health`、`/v1/health/ready`、`/workspace` 本次各返回 200。旧候选完成私有备份和 `ValidateOnly`，但其 `Deploy` 中断且无发布成功证据；不能把旧候选预检当作当前运行镜像的部署门禁。
- 重新打开 Codex 内置浏览器 staging 标签后，`cua.getTab` 连续绑定超时。原生应用可访问性树可读到订单行 `物流商 —`，但截图和点击超时，不能证明可见性、增强请求是否发起、平台响应或最终回显。已登录 UI 结论为 `UI_UNAVAILABLE`，不计作验收通过。
- R03 中的 81/81 契约、68/68 合成生产浏览器、lint/typecheck/build 是源码候选上的历史验证，不冒充本次 staging 现场测试。

# REQ/AC 与证据映射

AC-03/AC-06 的共享代码和部署源码包含关系已证实。所有未来连接的 TikTok 店铺按会话 `store_id` 获取对应 `ChannelAccount` 后进入同一 `TikTokReadClient`、侧栏服务和前端承运商规则；授权、店铺类型、平台字段和增强资格仍逐店不同。AC-05 的已登录现场订单回显未完成。

# 缺陷、未执行项与残余风险

浏览器工具绑定和截图不可用；可访问性树的 `—` 不能判定是卡片未进入可见区域、请求未完成、平台缺承运商，还是回显缺陷。不能据此标记 PASS 或 DONE。旧候选中断后未继续部署，当前新镜像和四条健康路径正常；未发现可归因于本任务的运行故障。

# 结论和复测条件

`PARTIAL`。浏览器恢复后在已登录工作台只读核对 TikTok US 和 XBM 至少各一笔符合增强条件的订单：无需打开物流详情，订单卡与详情先出现同一实际承运商；再打开弹层核对承运商和轨迹；平台明确无承运商时保留 `—`。核对请求结果和冷却提示，不向买家发送消息。
