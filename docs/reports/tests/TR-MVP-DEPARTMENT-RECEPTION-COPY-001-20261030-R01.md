---
record_id: TR-MVP-DEPARTMENT-RECEPTION-COPY-001-20261030-R01
record_type: test
revision: R01
status: PASS
task_id: MVP-DEPARTMENT-RECEPTION-COPY-001
tested_sha: af29152e19ad252a5bb6f25c0b33b84a42cf511a
implementation_record: docs/records/implementation/IR-MVP-DEPARTMENT-RECEPTION-COPY-001-20261030-R01.md
requirement_ids: [MVP-DEPARTMENT-RECEPTION-COPY-001]
acceptance_ids: [AC-01, AC-02]
environment: Windows, Node local Next dev on 127.0.0.1:3103, Chrome Playwright, synthetic API routes
created_at: 2026-10-30T12:15:35Z
updated_at: 2026-10-30T12:15:35Z
supersedes: null
---

# 测试结果

TEST_LAYOUT: centralized。

- AC-01：两条部门派单浏览器用例在修改前因长段落存在而失败（断言 `1 !== 0`），修改后 2/2 通过。测试同时检查负责店铺标题、派单开关、待领取状态和管理员不合格提示仍可见。最初误连旧的本地 3101 构建产生超时，不计候选结果；改用独立 3103 服务完成红绿验证。
- AC-02：`npm run lint` 0 errors、8 条既有 warning；`npm run typecheck` 通过；`npm run test` 55/55；`npm run build` 通过；`git diff --check` 通过。

本次仅移除 UI 静态文案，未重跑后端、真实 TikTok 入站或真实买家消息。真实 staging 上线由独立发布记录验证。
