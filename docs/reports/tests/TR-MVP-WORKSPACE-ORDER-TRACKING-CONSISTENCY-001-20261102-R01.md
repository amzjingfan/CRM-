---
record_id: TR-MVP-WORKSPACE-ORDER-TRACKING-CONSISTENCY-001-20261102-R01
record_type: test
revision: R01
status: PASS
task_id: MVP-WORKSPACE-ORDER-TRACKING-CONSISTENCY-001
tested_sha: 248fc487a07388ac7392339bfc262459e4ac7596
implementation_record: docs/records/implementation/IR-MVP-WORKSPACE-ORDER-TRACKING-CONSISTENCY-001-20261102-R01.md
requirement_ids: [MVP-WORKSPACE-ORDER-TRACKING-CONSISTENCY-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05]
environment: Windows PowerShell, Next.js 16.4.2, localhost 127.0.0.1:3101, Chrome Playwright with synthetic /v1 fixtures
created_at: 2026-11-02T12:07:15+08:00
updated_at: 2026-11-02T12:07:15+08:00
supersedes: null
---

# 测试范围、环境与 TEST_LAYOUT

`TEST_LAYOUT: centralized`。最终源码提交 `248fc487a07388ac7392339bfc262459e4ac7596`，测试位于 `src/tests/frontend/`。浏览器所有 `/v1/` 响应均为合成 fixture；不向 TikTok 买家发送、不调用退款。

# 命令和逐项结果

| 命令 | 结果 |
|---|---|
| `npm run test` | PASS：80/80 契约 |
| `node --test ../tests/frontend/browser/workspace-experience.test.mjs` | PASS：65/65 浏览器；含九种订单状态、通用与增强轨迹、翻译和只读草稿 |
| `npm run typecheck` | PASS |
| `npm run lint` | PASS：0 错误、12 条既有图片/导航警告 |
| `npm run build` | PASS：Next 生产构建 |
| `git diff --cached --check` | PASS：源码提交前 |

# REQ/AC 与证据映射

- AC-01：契约覆盖 `DELIVERED`、`COMPLETED` 均为“已完成”，浏览器覆盖订单卡、出货状态与原生订单草稿；包裹送达仍显示“已送达”。
- AC-02：契约覆盖 `Package has been delivered!`、未知节点不猜测、明确运输中阶段优先；浏览器覆盖常见送达和其他阶段描述。
- AC-03：契约覆盖包裹 ID 匹配、不同承运商多包裹及平台揽收方式；浏览器覆盖 SwiftX 增强结果回写订单卡/详情与翻译。
- AC-04：浏览器分别覆盖有通用节点时隐藏增强失败，以及没有通用节点时保留增强失败。
- AC-05：上述合成、静态检查和构建通过；staging 现场验收与部署另记发布证据，不能由本地测试替代。

# 缺陷、未执行项与残余风险

首次完整浏览器运行 63/64：物流阶段优先级回归导致现有“运输中”断言失败；修正优先级并重跑最终 subject，65/65 通过。未对真实 TikTok 店铺制造订单或发送消息。未运行后端和迁移测试：本 subject 无后端、接口、迁移变化。staging 真数据与镜像发布尚未在本 TR 验证。

# 结论和复测条件

本地候选 PASS。合并后部署 staging 时只读检查已完成订单标签、SwiftX/USPS 等承运商、通用及增强轨迹回退；若平台返回新的结构或状态，保留原始字段并另行补充样本和测试。
