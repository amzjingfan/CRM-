---
record_id: TR-MVP-TIKTOK-CUSTOMER-NAME-001-20261019-R01
record_type: test
revision: R01
status: PARTIAL
task_id: MVP-TIKTOK-CUSTOMER-NAME-001
tested_sha: f48779af3779ef7804703feb1c6f1ff4755bbe36
implementation_record: docs/records/implementation/IR-MVP-TIKTOK-CUSTOMER-NAME-001-20261019-R01.md
requirement_ids: [MVP-TIKTOK-CUSTOMER-NAME-001]
acceptance_ids: [AC-01, AC-02, AC-03]
environment: Windows Python 3.11/uv；staging 已登录工作台及只读数据库检查
created_at: 2026-10-19T09:35:00+08:00
updated_at: 2026-10-19T09:35:00+08:00
supersedes: null
---

# 测试范围与结果

`TEST_LAYOUT=centralized`。新增回归先在缺昵称通知上失败：现有名称被覆盖为 `None`；修复后两项通过，平台提供新昵称时正常更新。完整后端 `uv run python -m pytest -c pyproject.toml ../tests/backend -q` 在源码提交 `5838ce87e0b9689314ae1f7ff1667344446d63e7` 上为 **2146 passed、3 skipped**。该提交与 squash 合入的 `f48779a` 在服务代码、回归测试及架构文档路径内容一致；合入 SHA 上重新运行两份相关平台测试 **35 passed**，Ruff check/format 与 `mypy app` 通过。第一次未显式指定 pytest 配置的完整收集因 `_support` 导入错误中断，改用 `-c pyproject.toml` 后完整执行，不计为测试失败。

staging 只读核对：目标会话已有名称存在，成功处理的 3 条 TikTok 新消息通知均未提供昵称；已登录工作台此后恢复显示平台昵称。运行后端 OCI revision 仍为旧源码 `6394282897abdb89349dee7399bb05629220ca2e`，因此现场恢复只能证明定时同步可补回名称，不能证明新补丁已生效。

# AC 与限制

AC-01/02 的确定性回归、完整后端和静态检查通过；AC-03 的只读现场原因核对完成，部署后持续显示的验收仍待共享 G5 窗口结束。没有向真实买家发送消息、制造新通知、改写真实客户数据、运行 GitHub Actions 或发布 production。正式结论保持 `PARTIAL`；部署后需核对不可变后端摘要、健康、已登录工作台名称，并以新通知缺昵称的受控复测或等价只读证据定稿。
