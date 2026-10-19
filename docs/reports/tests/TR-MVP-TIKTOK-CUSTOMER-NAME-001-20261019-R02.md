---
record_id: TR-MVP-TIKTOK-CUSTOMER-NAME-001-20261019-R02
record_type: test
revision: R02
status: PASS
task_id: MVP-TIKTOK-CUSTOMER-NAME-001
tested_sha: f48779af3779ef7804703feb1c6f1ff4755bbe36
implementation_record: docs/records/implementation/IR-MVP-TIKTOK-CUSTOMER-NAME-001-20261019-R02.md
requirement_ids: [MVP-TIKTOK-CUSTOMER-NAME-001]
acceptance_ids: [AC-01, AC-02, AC-03]
environment: Windows Python 3.11/uv；Rootless staging 单店人工发送、Webhook 读取及工作台翻译
created_at: 2026-10-19T10:02:00+08:00
updated_at: 2026-10-19T10:02:00+08:00
supersedes: docs/reports/tests/TR-MVP-TIKTOK-CUSTOMER-NAME-001-20261019-R01.md
---

# 验证范围与结果

`TEST_LAYOUT=centralized`。[R01](TR-MVP-TIKTOK-CUSTOMER-NAME-001-20261019-R01.md)的缺昵称/新昵称行为回归、完整后端 **2146 passed、3 skipped**、合入 SHA 的相关 **35 passed** 和静态检查保持有效。本次再次运行 `uv run python -m pytest -c pyproject.toml ../tests/backend/platform/test_tiktok_customer_name.py -q` 为 **2 passed**。未改动源码或验收标准。

部署前：当前 main `1476253091b5e1e2fda7e1952dc5bd2fb9cb088a` 与候选镜像 OCI revision `6e1d24b3bf57674dafb5aabe4f7dc1335f13aa28` 的后端构建输入一致，`f48779a` 为其祖先。旧 Rootless 后端镜像为 `sha256:8913c09c…83a958`。源码/目标 `CheckOnly` 和正式 `ValidateOnly` 均通过；已授权店铺未结清 `processing/unknown` 出站数为 0。

手动 `Deploy` 返回 `passed`；backend、worker、jobs、agent-worker、tiktok-egress 均运行新后端 `sha256:2dc92fe5…c2f258`。迁移头已应用，公网 `/healthz`、`/v1/health`、`/v1/health/ready` 均为 HTTP 200，固定出口 IP 匹配。门禁确认 Webhook 读取、原单店人工发送和工作台翻译开启；G5/LLM、自动回复和高风险写入关闭。前端、检索镜像未换，原后端镜像仍在本地。原私有门禁证据 SHA-256 为 `ca6f8edb5477863465bcc8e1ea116e63f87c27fd05e9b325f283ee66ac845012`；低敏[清单](../../../release/evidence/staging/crm-staging-tiktok-customer-name-20261019.json)保留审核字段。

部署后只读核对：目标会话关联客户名称非空；已登录工作台显示会话标题、客户信息侧栏及会话列表买家昵称，均未显示“匿名客户”。

# AC 与剩余边界

- AC-01/02：确定性回归通过，缺失昵称保留旧值，新昵称更新。
- AC-03：staging 运行镜像包含补丁、手动部署门禁及工作台三个位置的显示通过。

本次没有制造新的真实买家通知，因此尚未现场观察“补丁部署后新到的一条缺昵称 Webhook”；这一单次现场路径由回归测试、已核实的旧通知形态和运行镜像对应性覆盖。后续自然通知可持续只读观察，但不阻断本次缺陷验收。没有给买家发送消息、改写客户数据、执行回滚或 production 发布。
