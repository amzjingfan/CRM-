---
record_id: TR-MVP-CONV-SYNC-001-20261016-R01
record_type: test
revision: R01
status: PARTIAL
task_id: MVP-CONV-SYNC-001
tested_sha: 9c9e805f25fee45d51dbd0e96a60a07baab8b326
implementation_record: docs/records/implementation/IR-MVP-CONV-SYNC-001-20261016-R01.md
requirement_ids: [MVP-CONV-SYNC-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
environment: isolated local PostgreSQL 16, Python 3.11, Next.js 16.3.4, staging read-only preflight
created_at: 2026-10-16T17:54:00+08:00
updated_at: 2026-10-16T17:54:00+08:00
supersedes: null
---

# 本地与只读平台预检

`TEST_LAYOUT=centralized`。候选 SHA 的后端 `uv run python -m pytest ../tests/backend ../tests/integration/postgres -q` 使用隔离 PostgreSQL，结果 **1882 passed, 3 skipped, 2 warnings**；集成测试覆盖全页回填、隐藏消息、消息角色、幂等、工作台查询与首店失败后第二店继续。Ruff check/format 与全量 mypy 通过。前端 44 项契约测试通过，Next.js 生产构建通过；lint 无错误，有两处既有跳转警告。

staging 发布前只读预检确认一个已连接 TikTok 渠道具备 `seller.customer_service`，运行中的真实读取与 Webhook 开启、真实普通消息写入关闭；本地库当时真实 TikTok 会话与消息均为 0。平台只读抽样返回首 20 个会话、188 条消息，其中 160 条可见，覆盖买家、人工客服、机器人、店铺及系统角色；抽样消息正文未写入报告，内容解析无错误。截图目标会话的历史共 29 条、跨三页。抽样不等于项目中已经显示。

AC-01/02 的隔离测试和前端契约已通过。AC-03 须在 PR 合并后发布不可变 staging 镜像、运行只读回填、核对工作台接口与页面；AC-04 须按部署后开关和现场证据明确双向发送状态。因此本版结论为 **PARTIAL**，不得宣称 staging 已完成或 G2/G3 已通过。
