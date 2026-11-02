---
record_id: TR-MVP-WORKSPACE-ORDER-TRACKING-CONSISTENCY-001-20261102-R03
record_type: test
revision: R03
status: PARTIAL
task_id: MVP-WORKSPACE-ORDER-TRACKING-CONSISTENCY-001
tested_sha: b98b955b962df638d9a899fc17c2396cbcb2ad54
implementation_record: docs/records/implementation/IR-MVP-WORKSPACE-ORDER-TRACKING-CONSISTENCY-001-20261102-R02.md
requirement_ids: [MVP-WORKSPACE-ORDER-TRACKING-CONSISTENCY-001]
acceptance_ids: [AC-03, AC-05, AC-06]
environment: Windows local; Next.js production build and local browser with synthetic TikTok responses
created_at: 2026-11-02T18:28:37+08:00
updated_at: 2026-11-02T18:28:37+08:00
supersedes: docs/reports/tests/TR-MVP-WORKSPACE-ORDER-TRACKING-CONSISTENCY-001-20261102-R02.md
---

# 测试范围、环境与 TEST_LAYOUT

`TEST_LAYOUT: centralized`。针对可见订单卡、提前打开详情、增强读取期间打开弹窗、已有实际承运商的店铺及增强翻译回归。浏览器用例拦截全部业务 API，只使用合成数据，不触达买家或真实 TikTok。

# 命令和逐项结果

- 在旧实现新增“打开详情前显示 SwiftX”用例，执行 `node --test --test-name-pattern "cross-border carrier appears" ../tests/frontend/browser/workspace-experience.test.mjs`，按预期超时失败；修复后同用例通过。
- `npm run lint`：退出 0，0 errors、12 条既有 warnings；`npm run typecheck`：通过。
- `npm run test`：81/81 通过，包含增强读取判断契约。
- `npm run build`：最终 subject 上生产构建成功。
- `UI_CACHE_EXPECT_PRODUCTION=1`，`node --test ../tests/frontend/browser/workspace-experience.test.mjs`：最终 subject 上 68/68 通过。期间发现弹窗接收增强结果后重置翻译来源的回归，修复后全套重跑通过。
- `git diff --check`：无空白错误。未执行后端全量、数据库迁移与 AI eval：本次未改这些层。

# REQ/AC 与证据映射

AC-03/AC-06：合成跨境店订单无需打开弹窗即显示 SwiftX；详情先开仍可补齐；增强预取期间打开弹窗仅请求一次且保留增强翻译来源。已有 USPS 的卡片不触发自动增强；无增强资格的店铺保持通用物流。AC-05 的本地质量部分通过，staging 已登录 UI 与部署证据尚未取得。

# 缺陷、未执行项与残余风险

首次完整工作台运行发现 1 项弹窗翻译回归，修复并在最终 subject 上 68/68 重跑。真实平台可能因每单八小时冷却或官方字段缺失仍无法给出实际承运商；界面继续显示未知值。真实 staging 页面验收待部署后完成，不能以合成测试替代。

# 结论和复测条件

本地修复验证 PASS；任务整体仍 PARTIAL，需从已合并源码部署 staging 并重新打开 Codex 内置浏览器，只读核对各店订单卡、订单详情及物流弹窗的承运商一致性。
