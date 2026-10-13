# G4 Policy Draft Validation and Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 G4 离线真实模型评测中依据本次可信证据校验政策草稿，最多修复一次，保留首轮与最终判分且失败关闭。

**Architecture:** 独立纯函数校验政策条件和引用，不读取冻结答案；已验证数据集为修复请求生成一次性 DLP 摘要授权。评测器在内存中处理首轮和可选修复，再用原评分器各自判分；报告只保存低敏原因、哈希、调用数与用量。

**Tech Stack:** Python 3.11、Pydantic v2、pytest、ruff、mypy、PowerShell GitHub Actions。

**Spec:** `docs/superpowers/specs/2026-10-13-g4-policy-draft-validation-repair-design.md`

## Global Constraints

- 仅接入 G4 离线评测；正式 FAQ/工具工作流、公开 API、发送开关与 production 不变。
- 冻结数据/摘要、`grade_real_model_evaluation_output`、85% 门槛、逐项失败复核和两条本地故障注入保持不变。
- 修复只可读取白名单消息、目标语言、合成证据、类型/引用、可信主体、首轮草稿与通用原因码；不读取或发送期望标签、必含/禁用词、`sample_id`、数据集版本、类别或分数。
- 每条真实样本至多两次 Provider 调用；34 条样本至多 68 次；两条故障注入调用数为零。Token 预算达到上限后不再启动调用。
- 任一输出未经完整 DLP/Schema/证据/政策检查不得展示；失败终态隐藏正文、清空声明，`send_performed=false`。
- 报告、日志、工作流产物不得含模型正文、客户正文、修复 Prompt 或凭据。

## Review Focus

- 攻击者把标签字段塞进修复载荷：修复 DLP 拒绝额外字段，Provider 不被调用（Task 2）。
- 首轮草稿含凭据或地址：修复载荷阻断且不记录原文（Task 2）。
- 修复输出产生新的无依据审批承诺：第二次全量校验后转人工（Task 3）。
- 模型修复时拒绝或超时：保留首轮独立判分，最终转人工并正确记 Provider 失败（Task 3）。
- 旧低敏报告载入新模型：标识为旧单轮口径，不虚构首轮/修复指标（Task 3）。

---

### Task 1: 通用政策草稿校验器

**Files:**
- Create: `src/backend/app/agent/policy_draft_validation.py`
- Test: `src/tests/backend/agent/test_policy_draft_validation.py`

**Interfaces:**
- Produces: `validate_policy_draft(*, evidence: str | None, content: str | None, language: str, claim_evidence_type: str | None, claim_evidence_id: str | None, expected_evidence_type: str, expected_evidence_id: str | None) -> PolicyDraftValidation`；结果含 `disposition: Literal["pass", "repair", "block"]` 和稳定 `reason_codes`。
- Consumes: 仅本次合成证据与草稿，绝不接收 `RealModelEvaluationCase` 全对象。

- [ ] **Step 1: Write failing tests** for independent English/Chinese conditional approval and review evidence, missing condition/review, unsupported approved-instance wording, unrelated safe policy, citation mismatch, uncertain evidence, and paraphrases outside frozen fixtures.
- [ ] **Step 2: Run** `uv run pytest -c pyproject.toml ../tests/backend/agent/test_policy_draft_validation.py -q` from `src/backend`; expected new behavior tests fail before implementation.
- [ ] **Step 3: Implement** the interface using versioned deterministic policy concepts and conservative block on unknown evidence; do not implement frozen term matching.
- [ ] **Step 4: Run** the same pytest command; expected exit 0 and no failures.
- [ ] **Step 5: Commit** `feat: validate grounded policy drafts`.

### Task 2: 一次性修复请求的 DLP 授权

**Files:**
- Modify: `src/backend/app/agent/security.py`
- Modify: `src/backend/app/agent/real_model_evaluation.py`
- Test: `src/tests/backend/agent/test_real_model_evaluation_repair_safety.py`

**Interfaces:**
- Produces: `build_real_model_repair_request(case, dataset, first_output, reason_codes, *, run_id) -> StructuredRequest`；其上下文只授权这个修复载荷摘要，并绑定已有冻结输入摘要。
- Consumes: Task 1 的通用原因码；`RealModelEvaluationSafetyContext` 的原始冻结授权保持有效。

- [ ] **Step 1: Write failing tests** for exact repair allowlist, valid synthetic payload, unknown source/digest, injected expected labels, nested PII/secret/address, and the system prompt allowlist.
- [ ] **Step 2: Run** `uv run pytest -c pyproject.toml ../tests/backend/agent/test_real_model_evaluation_repair_safety.py -q`; expected new behavior tests fail.
- [ ] **Step 3: Implement** a distinct `real_model_evaluation_repair` schema, one-payload hash grant, original-source binding, nested DLP scan and fixed repair system prompt; no generic dynamic-text bypass.
- [ ] **Step 4: Run** the same pytest command; expected exit 0 and no failures.
- [ ] **Step 5: Commit** `feat: authorize bounded G4 repair prompts`.

### Task 3: 评测编排与双阶段低敏报告

**Files:**
- Modify: `src/backend/app/agent/real_model_evaluation.py`
- Test: `src/tests/backend/agent/test_real_model_evaluation_repair.py`
- Test: `src/tests/backend/agent/test_real_model_evaluation.py`

**Interfaces:**
- Consumes: Task 1 `validate_policy_draft` and Task 2 `build_real_model_repair_request`。
- Produces: 新报告口径 `policy-repair-v1`；旧报告默认 `single-pass-v1`；每条样本包含首轮/最终哈希与评分、修复状态、Provider 调用数、分阶段 Token/延迟，汇总含首轮准确率、修复数与总调用数。

- [ ] **Step 1: Write failing tests** for pass-without-repair, one successful repair, repair still unsafe, first-call and repair-call failure, local injection, 68-call bound, Token budget stop, first/final score separation, old-report compatibility and low-sensitive JSON.
- [ ] **Step 2: Run** `uv run pytest -c pyproject.toml ../tests/backend/agent/test_real_model_evaluation_repair.py -q`; expected new behavior tests fail.
- [ ] **Step 3: Implement** single repair in `run_real_model_evaluation`, revalidate whole repaired output, fail closed, aggregate both calls and keep `grade_real_model_evaluation_output` unchanged.
- [ ] **Step 4: Run** targeted repair, existing evaluation and diagnostics tests; expected exit 0 and no failures.
- [ ] **Step 5: Commit** `feat: score first and repaired G4 drafts separately`.

### Task 4: 工作流限额、文档和交付证据

**Files:**
- Modify: `.github/workflows/evaluate-staging-deepseek.yml`
- Modify: `docs/architecture/AI.md`, `docs/quality/TEST-STRATEGY.md`, `docs/operations/RELEASE-GATES.md`, `docs/tasks/TASKS.md`, `docs/memory/PROJECT-STATE.md`
- Test: `src/tests/backend/runtime_infrastructure/test_staging_deepseek_workflow_contract.py` (or existing workflow contract test if present)
- Create after verification: `docs/records/implementation/IR-MVP-005-20261013-R16.md`, `docs/reports/tests/TR-MVP-005-20261013-R16.md`, `docs/reports/reviews/RR-MVP-005-20261013-R16.md`

**Interfaces:**
- Consumes: Task 3 report fields and flow version.
- Produces: workflow exact low-sensitive key allowlist and hard 68-call evidence check; records explicitly say no new DeepSeek/staging execution and G4 remains PARTIAL.

- [ ] **Step 1: Write failing workflow contract tests** for new report keys, 68-call ceiling, 34+2 provenance, and rejection of raw draft/prompt fields.
- [ ] **Step 2: Run** the focused pytest command; expected contract tests fail before workflow change.
- [ ] **Step 3: Update** workflow, current docs and machine indexes; preserve the existing `prepare` zero-call gate and `live` explicit paid authorization.
- [ ] **Step 4: Run** `uv run ruff check . ../tests/backend ../tests/integration/postgres`, `uv run ruff format --check . ../tests/backend ../tests/integration/postgres`, `uv run mypy app scripts`, `uv run pytest -c pyproject.toml`, plus index validation from repo docs; expected exits 0. Record unavailable integration resources precisely.
- [ ] **Step 5: Write** R16 IR/TR/RR using this run's commands and subject SHA, then commit `docs: record bounded G4 repair verification`.

### Final integration

- [ ] Review branch diff against this plan and spec, including the no-label-leak property and exact remote target.
- [ ] Push the single-topic branch, open PR referencing `MVP-005`, verify applicable CI and review gate, squash merge into recorded `origin/main` when the repository's completion gate is satisfied.
- [ ] Verify merged main SHA, update task/release status only from actual evidence; mirror the final record indexes if the squash SHA changes them.
- [ ] Do not publish a private image, deploy staging, invoke DeepSeek, send TikTok messages or mark G4 DONE under this plan.
