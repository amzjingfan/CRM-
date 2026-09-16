# 项目任务状态

本文件是 CRM 智能聊天系统任务状态的唯一事实源。产品范围与验收原则见 `../product/PRODUCT.md`，生产门禁状态见 `../operations/RELEASE-GATES.md`，治理流程与证据格式见 `../governance/GOVERNANCE.md`。README、项目恢复摘要、报告和 Codex 侧栏只能引用本表，不维护第二套任务状态。

## 状态规则

```text
BACKLOG → READY → DOING → VERIFYING → DONE
DOING/VERIFYING → BLOCKED
未完成状态 → CANCELLED
```

- `BACKLOG`：事项有业务价值，但范围、验收、依赖、资源或授权尚未全部具备。
- `READY`：可验证结果、验收或门禁、依赖、授权边界和验证方法完整。
- `DOING`：已经记录短期分支、`BASE_SHA` 和实际执行范围。
- `VERIFYING`：实现已完成，正在执行验证、审查、文档同步和证据定稿。
- `DONE`：验收通过，最终 IR/TR 已定稿，需要的 RR 已关闭，文档已同步，“最终 SHA”为真实 `CANDIDATE_SUBJECT_SHA`，证据尾区间只包含允许路径。`DONE` 不接受 `WORKTREE`。
- `BLOCKED`：阻塞原因、已尝试措施和解除条件明确；解除后回到 `DOING` 或 `VERIFYING`。
- `CANCELLED`：记录取消原因和恢复/清理需要，不等同于完成。

空白证据或 SHA 表示尚未产生，不表示 `N/A`。只有经过风险判断确认不需要审查时，RR 才可写 `N/A` 并在任务说明中给出理由。

## P0：关闭 TikTok 人工辅助 v0.1 门禁

以下事项均保持 `BACKLOG`。只有补齐精确范围、环境、验收步骤、资源和授权后，才可以逐项转为 `READY`。

| ID | 可验证结果 | 需求/验收或门禁 | 状态 | 分支 | 依赖 | IR | TR | RR | 最终 SHA |
|---|---|---|---|---|---|---|---|---|---|
| MVP-001 | 轮换并通过密钥管理安全注入 v0.1 所需凭证，确认日志与响应无泄漏 | G0 | BACKLOG | | none | | | required | |
| MVP-002 | 专用真实店铺完成 TikTok OAuth、Scope、Token 生命周期、只读能力与店铺隔离验收 | G1 | BACKLOG | | MVP-001 | | | required | |
| MVP-003 | Partner Center 完成真实 Webhook 投递、签名、幂等、重试、乱序与审计验收 | G2 | BACKLOG | | MVP-001, MVP-002 | | | required | |
| MVP-004 | 低风险会话完成一次人工确认普通文本发送，并验证成功、`unknown` 对账和禁止盲重试 | G3 | BACKLOG | | MVP-002 | | | required | |
| MVP-005 | 用冻结低敏数据完成 DeepSeek 建议质量、DLP、结构化声明、引用与转人工复测 | G4 | BACKLOG | | MVP-001 | | | required | |
| MVP-006 | 完成 50 客户端 SSE 容量门禁并记录延迟、错误、断连、队列和资源证据 | G5 | BACKLOG | | MVP-005 | | | required | |
| MVP-007 | 连续运行五日并达到 99.5% 可用性，验证告警、积压、资源和故障恢复 | G6 | BACKLOG | | MVP-002, MVP-003, MVP-004, MVP-005, MVP-006 | | | required | |
| MVP-008 | 完成数据库、对象存储恢复与上一版本实际回滚演练 | G0 | BACKLOG | | MVP-001 | | | required | |
| MVP-009 | 汇总 G0～G6 证据并取得最终 Go/No-Go 决定 | G8 | BACKLOG | | MVP-001～MVP-008 | | | required | |

## P1：v0.1 之后

这些主题明确不属于当前 v0.1 放行范围。开始前必须建立独立需求、验收、安全边界和门禁，不能复用 v0.1 的限定结论。

| ID | 可验证结果 | 需求/验收或门禁 | 状态 | 分支 | 依赖 | IR | TR | RR | 最终 SHA |
|---|---|---|---|---|---|---|---|---|---|
| MVP-010 | 建立 Shopee 与 Amazon 真实授权、消息和订单/物流适配的独立产品与技术基线 | 新需求与门禁 | BACKLOG | | MVP-009 | | | required | |
| MVP-011 | 建立生产翻译质量、多语言安全和数据边界的独立验收 | 新需求与门禁 | BACKLOG | | MVP-009 | | | required | |
| MVP-012 | 建立公开自动回复、主动营销与高风险写入的审批、频控、幂等、审计、容量和回滚基线 | G7；新需求与门禁 | BACKLOG | | MVP-009 | | | required | |
| MVP-013 | 根据真实流量复核 BGE/DeepSeek 容量与成本并形成后续容量决定 | 新需求与门禁 | BACKLOG | | MVP-006, MVP-007 | | | required | |

## P2：仓库与文档维护

| ID | 可验证结果 | 需求/验收或门禁 | 状态 | 分支 | 依赖 | IR | TR | RR | 最终 SHA |
|---|---|---|---|---|---|---|---|---|---|
| DOCS-001 | 按职责域分类 `docs/` 当前文档并修复活动引用，不改变项目事实 | 本设计规格的 7 项验收标准；`BASE_SHA=318d0e0272a580e0eb36f17e6188944276d2c9be` | DONE | codex/docs-classify-documentation | none | N/A | N/A | N/A（纯文档路径重组） | 35e41ee641e15ce124e3ad09a27f3d8bef1caeec |

## 维护规则

1. 开始任务时只选择依赖已满足的最高优先级 `READY` 项，并在同一次更新中写入分支和基线。
2. 范围或验收改变时先更新 `docs/product/PRODUCT.md` 或相关当前事实文档，再更新本表。
3. 失败验证回到同一任务和分支修复，不新建重复任务制造“通过”。
4. 实际清理使用 `MAINT-CLEANUP-YYYYMMDD-NNN`，并链接精确 `CLEANUP-YYYYMMDD-NNN` 批次。
5. 超过约 20 个活动任务或进入多人长期协作后，才评估独立任务文件或外部任务平台；在此之前不扩展状态系统。
