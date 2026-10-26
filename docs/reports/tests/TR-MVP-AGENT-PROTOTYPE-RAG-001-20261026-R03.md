---
record_id: TR-MVP-AGENT-PROTOTYPE-RAG-001-20261026-R03
record_type: test
revision: R03
status: PARTIAL
task_id: MVP-AGENT-PROTOTYPE-RAG-001
tested_sha: 09455b510f1e8f2281d1ad4f0fb8911fc8ae6ae0
implementation_record: docs/records/implementation/IR-MVP-AGENT-PROTOTYPE-RAG-001-20261026-R01.md
requirement_ids: [MVP-AGENT-PROTOTYPE-RAG-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05, AC-06]
environment: GitHub PR #556; isolated local PostgreSQL and production browser evidence in R01
created_at: 2026-10-26T02:48:46Z
updated_at: 2026-10-26T02:48:46Z
supersedes: docs/reports/tests/TR-MVP-AGENT-PROTOTYPE-RAG-001-20261026-R02.md
---

# 测试范围、环境与 TEST_LAYOUT

`TEST_LAYOUT: centralized`。R01 的本地行为验证仍为 PASS，本修订记录远端 CI 未运行和用户针对本次 PR 的替代门禁决定，不将远端作业标作通过。

# 命令和逐项结果

- 本地完整结果见 [R01](TR-MVP-AGENT-PROTOTYPE-RAG-001-20261026-R01.md)：后端 2413 passed/3 skipped，前端契约 48 passed、生产浏览器 110 passed、迁移 033 升降升、Ruff/mypy/类型/构建通过。
- [CI run 40260512287](https://github.com/CP11-gh/CRM/actions/runs/40260512287) 和最终证据提交 `272146356b23eb272032d0b17fce8fe3ce6c57c5` 的 [run 40260850473](https://github.com/CP11-gh/CRM/actions/runs/40260850473) 均为前后端作业零步骤失败；后者的两项 `steps=[]` 已复核。没有 GitHub runner 测试结果。
- 用户于 2026-10-26 明确批准 **PR #556 本次**使用已记录的本地验证替代未启动的 CI，并合并到 `main`。该决定不改变 CI 真实状态，也不适用于其他 PR 或生产发布。

# REQ/AC 或门禁与证据映射

AC-01～AC-06 的功能证据仍在 R01；远端 CI 项为未执行，经本次明确决定以本地完整门禁替代合并前验证。

# 缺陷、未执行项与残余风险

GitHub Actions 原因在可读取作业数据中不明。后续代码变化仍需重新验证；staging 与 production 尚未部署，真实数据量下索引构建和模型质量未验。

# 结论和复测条件

本地验证 **PASS**，远端 CI **未执行**，综合记录为 **PARTIAL**；针对 PR #556 的合并替代门禁已有用户明确决定。合并前仍需确认 PR head、目标分支、安全审查和证据路径一致。
