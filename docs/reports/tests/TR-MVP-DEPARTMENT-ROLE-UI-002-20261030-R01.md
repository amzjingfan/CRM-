---
record_id: TR-MVP-DEPARTMENT-ROLE-UI-002-20261030-R01
record_type: test
revision: R01
status: PASS
task_id: MVP-DEPARTMENT-ROLE-UI-002
tested_sha: 0fb8202f5b39b77e085228b3dd6acc64ecf88c35
implementation_record: docs/records/implementation/IR-MVP-DEPARTMENT-ROLE-UI-002-20261030-R01.md
requirement_ids: [MVP-DEPARTMENT-ROLE-UI-002]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05]
environment: local frontend production build on 127.0.0.1:3101; staging connected TikTok US test store transaction rollback
created_at: 2026-10-30T14:09:20+08:00
updated_at: 2026-10-30T14:09:20+08:00
supersedes: null
---

# 测试范围、环境与 TEST_LAYOUT

`TEST_LAYOUT=centralized`，浏览器用例位于 `src/tests/frontend/browser/ui-regressions.test.mjs`。本地生产构建和浏览器检验 UI；staging 后端容器内仅用可回滚事务测试已连接的 `TikTok US 测试店铺`，不向买家发送。

# 命令和逐项结果

- `npm ci`、`npm run typecheck`、`npm run lint`、`npm run test`、`npm run build`：依次通过；单元测试 55/55；lint 有 8 条既有 warning。
- 本地生产服务 `next start -H 127.0.0.1 -p 3101`，`node --test ../tests/frontend/browser/ui-regressions.test.mjs`：56/56 通过，含角色摘要、逐店派单、新账号部门选择及菜单视口边界与实际点击命中。
- 在 `src/backend` 执行 `$env:PYTHONPATH=(Get-Location).Path; uv run pytest ../tests/backend/domain/test_departments.py ../tests/backend/domain/test_reception_assignment_rules.py -q`：7/7 通过、1 条 warning。此前同环境的部门/权限定向测试另有 14 项通过。
- staging 只读核验：管理员拥有三家现存店铺的 `workspace.view/reply/transfer` 与 `settings.team`；主管、客服角色矩阵符合现有服务端配置。
- staging 已连接测试店事务回滚：默认关闭进入待领取，开启后合成消息分配给有回复权限的客服而非无回复权限的主管，重复消息幂等；真实平台外发数为 0；回滚后合成账号、会话、消息和接待配置残留均为 0。

# REQ/AC 或门禁与证据映射

- AC-01/02：浏览器角色和派单页用例；服务端角色矩阵只读核验。
- AC-03：浏览器新建账号店铺及部门选项用例。
- AC-04：浏览器菜单边界与 `elementFromPoint` 点击命中用例。
- AC-05：前述 staging 事务回滚、14 项后端测试和 56 项前端浏览器回归。

# 缺陷、未执行项与残余风险

一次全量 `npm run test:ui` 在其他套件所需本地端口未启动时失败；本次受影响的 `ui-regressions.test.mjs` 已在生产构建上完整复跑通过。一次从仓库根目录运行的后端测试因该位置缺少 `pgvector` 而在收集阶段失败；改用 `src/backend` 的锁定环境后通过。未发送真实买家消息，未验证真实 TikTok webhook 到达；该项须单独安排平台侧证据。

# 结论和复测条件

本次受影响行为通过。部署 staging 后仍需核对页面实际呈现与版本，生产发布不在本任务范围。
