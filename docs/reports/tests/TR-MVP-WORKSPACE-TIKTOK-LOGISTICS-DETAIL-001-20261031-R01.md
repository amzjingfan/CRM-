---
record_id: TR-MVP-WORKSPACE-TIKTOK-LOGISTICS-DETAIL-001-20261031-R01
record_type: test
revision: R01
status: PASS
task_id: MVP-WORKSPACE-TIKTOK-LOGISTICS-DETAIL-001
tested_sha: 8247cd5658b6c73824ebe3b85551b358fc485c18
implementation_record: docs/records/implementation/IR-MVP-WORKSPACE-TIKTOK-LOGISTICS-DETAIL-001-20261031-R01.md
requirement_ids: [MVP-WORKSPACE-TIKTOK-LOGISTICS-DETAIL-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
environment: Windows, Node 22, Next.js 16.4.2, Chrome headless, local 127.0.0.1:3101 with mocked /v1 requests
created_at: 2026-10-31T03:27:07Z
updated_at: 2026-10-31T03:27:07Z
supersedes: null
---

# 测试范围、环境与 TEST_LAYOUT

`TEST_LAYOUT: centralized`。测试源码位于 `src/tests/frontend/browser/workspace-experience.test.mjs`，只使用合成消息、订单与被拦截的 `/v1/` 请求。无真实平台发送或退款。

# 命令和逐项结果

从 `src/frontend` 运行：

| 命令 | 本次结果 |
|---|---|
| `node --test --test-name-pattern="a synced TikTok logistics card" ../tests/frontend/browser/workspace-experience.test.mjs`（实现前） | FAIL：30 秒找不到聊天物流卡片的“查看详情”按钮 |
| 同一命令（实现后及增强断言后） | PASS：1/1 |
| `node --test ../tests/frontend/browser/workspace-experience.test.mjs` | PASS：57/57 |
| `npm run test` | PASS：78/78 契约 |
| `npm run typecheck` | PASS |
| `npm run lint` | PASS：0 错误、11 条既有图片及导航警告 |
| `npm run build` | PASS：Next 生产构建 |
| `git diff --check` | PASS |

# REQ/AC 或门禁与证据映射

- AC-01：合成聊天 `logistics_card` 带订单 ID，点击“查看详情”后加载轨迹节点；测试确认点击后发生额外订单详情读取。
- AC-02：缺订单 ID 的另一张卡片没有详情按钮。
- AC-03：工作台 57 项、契约 78 项、类型、lint 和构建均通过。
- AC-04：合成浏览器断言未调用文本或卡片发送；本轮未向真实买家外发、未退款、未部署 production。

# 缺陷、未执行项与残余风险

未执行真实 staging 登录态交互或 TikTok 新 `OTHER` 卡片还原；前者需发布后核对，后者因接口缺可核对的订单标识单列阻塞任务。未重复运行无关后端全量测试，因为后端、接口和数据库均未更改。

# 结论和复测条件

本地代码验收 PASS。发布 staging 后应在同一会话的原生物流卡片核对入口、弹窗轨迹及现有人工发送安全开关。
