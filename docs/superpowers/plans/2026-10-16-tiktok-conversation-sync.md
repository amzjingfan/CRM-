# TikTok 真实会话同步实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax.

**Goal:** 已授权 TikTok 店铺的真实会话及历史消息进入现有工作台，并持续补齐后续消息。

**Architecture:** 复用现有只读客户端，在现有 FastAPI 模块中实现按店铺幂等同步；首次全量分页回填，随后 Jobs Worker 周期扫描会话列表并按最新消息标识跳过未变化会话。工作台继续读取租户隔离的本地表，仅扩展角色和类型展示。

**Tech Stack:** Python/FastAPI、SQLAlchemy/PostgreSQL、Next.js、现有 Jobs Worker。

**Spec:** `docs/product/MVP.md` 的 TikTok 人工辅助流程与本会话中用户于 2026-10-16 批准的真实会话回填、增量同步、工作台展示方案。

## Global Constraints

- 只读取 TikTok 平台；不发送、不调用平台已读接口，不启用公开自动回复。
- 全部业务读写按内部店铺隔离；只处理已连接、具备 `seller.customer_service` 的渠道。
- 历史消息保留平台 UTC 时间，外部 ID 幂等，不能覆盖项目人工发送或已有 Webhook 消息。
- 不在日志、测试和证据中保存真实客户正文、Token 或完整第三方载荷。
- staging 的真实回填与部署独立复核；production 保持现有门禁。

## Review Focus

- 买家参与者缺失时失败关闭，避免把客服或机器人错误映射为客户。
- Webhook 与回填交错时消息不重复，且跨店铺 ID 冲突失败关闭。
- 隐藏消息不进入工作台，但仍可推进安全的同步水位。
- 翻页失败不标记会话同步完成，下次能重试且不重复。
- 平台最新消息与 CRM 已有人工发送相遇时，不覆盖待对账状态。

---

### Task 1: 历史与增量同步服务

**Files:** `src/backend/app/integrations/tiktok_read.py`, new `src/backend/app/integrations/conversation_sync.py`, new `src/tests/backend/platform/test_tiktok_conversation_sync.py`.

**Interfaces:** `sync_tiktok_channel(session: AsyncSession, channel: ChannelAccount, client: TikTokReadClient) -> SyncSummary` consumes the existing read client and local Customer/Conversation/Message tables; Task 2 invokes it.

- [ ] Write failing tests for all-page history, seller-only conversation, idempotence, visibility, page failure, cross-store collision, and latest-message skip.
- [ ] Run focused tests and confirm the failures are due to missing behavior.
- [ ] Implement minimal validated mapping and one-conversation-at-a-time commits; keep raw content out of logs.
- [ ] Run focused tests, then relevant existing integration and workspace tests.
- [ ] Commit the tested slice.

### Task 2: 运行入口与工作台呈现

**Files:** `src/backend/app/jobs/worker.py`, `src/backend/app/shared/config/settings.py`, `src/config/.env.example`, new `src/backend/scripts/sync_tiktok_conversations.py`, `src/backend/app/workspace/{schemas,service}.py`, `src/frontend/app/workspace/page.tsx`, relevant tests.

**Interfaces:** Jobs Worker and the one-time script call Task 1's `sync_tiktok_channel`; workspace keeps `/workspace/sessions` and detail endpoints.

- [ ] Write failing tests for opt-in periodic sync, one-time command safety, and buyer/agent/robot/system display behavior.
- [ ] Run focused tests and confirm red.
- [ ] Add disabled-by-default scheduler and one-time channel-scoped CLI; expose safe role/type fields to UI.
- [ ] Run focused tests, backend checks, frontend checks and build.
- [ ] Commit the tested slice.

### Task 3: staging 真实回填、验证与交付

**Files:** update current product/architecture/API/deployment/task documents and formal low-sensitivity IR/TR/RR evidence as required by governance.

**Interfaces:** consumes Task 1/2 runnable code and staging's existing encrypted OAuth channel; produces observable `/workspace` TikTok conversation history.

- [ ] Read-only preflight confirms exact staging deployment target, connected channel, scope, fixed egress, backup/recovery and current flags.
- [ ] Deploy tested backend and worker through the established staging path, run one scoped initial backfill, verify API and workbench show the screenshot conversation and expected history count.
- [ ] Rerun sync to prove no duplicates, check failures/metrics and confirm platform write flags remain disabled.
- [ ] Review send and receive paths against live evidence, record what is and is not proven.
- [ ] Finalize evidence, PR/CI/review and merge according to project governance; mark task DONE only after verified merge.
