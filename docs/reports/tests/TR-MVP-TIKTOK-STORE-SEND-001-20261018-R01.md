---
record_id: TR-MVP-TIKTOK-STORE-SEND-001-20261018-R01
record_type: test
revision: R01
status: PASS
task_id: MVP-TIKTOK-STORE-SEND-001
tested_sha: 6394282897abdb89349dee7399bb05629220ca2e
implementation_record: docs/records/implementation/IR-MVP-TIKTOK-STORE-SEND-001-20261018-R01.md
requirement_ids: [MVP-TIKTOK-STORE-SEND-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
environment: Windows Python 3.11/uv；staging Rootless Docker；已登录真实 TikTok 工作台
created_at: 2026-10-18T12:14:00+08:00
updated_at: 2026-10-18T12:14:00+08:00
supersedes: null
---

# 测试范围、环境与 TEST_LAYOUT

`TEST_LAYOUT=centralized`。最终 subject `6394282897abdb89349dee7399bb05629220ca2e` 已由 PR #348/#350 合入。此次定向测试运行于其后代 main `1edd0a9e5bd7d9899d6670662ee52503130c6007`；`git diff --name-only 6394282..HEAD` 对本任务的生产代码、门禁脚本及定向测试路径为空。后代的独立 G5 改动不作为本任务测试结果。

# 命令和逐项结果

- 首次从 `src/backend` 指定外部测试路径运行 `uv run pytest ... -q` 时，pytest 未加载本项目 `pyproject.toml`，五个文件均在收集阶段因 `app`/`_support` 导入失败；没有执行测试用例。明确加 `-c pyproject.toml` 后，同五个文件共 **318 passed**（121.46 秒）：工作台发送范围、TikTok 写客户端、真实运行配置、G5 恢复快照和 staging 门禁。另运行 `uv run pytest -c pyproject.toml ../tests/backend/agent/test_tool_executor.py -q`，**19 passed**，覆盖工具执行层。合计 337 项定向用例通过；不是完整后端回归。
- `uv run ruff check . ../tests/backend ../tests/integration/postgres`：退出码 0，`All checks passed!`；本机 `.ruff_cache` 写入被拒并产生缓存警告，不影响检查结论。
- `uv run ruff format --check . ../tests/backend ../tests/integration/postgres`：305 个文件已格式化；`uv run mypy app scripts`：183 个源文件无问题。
- 三份手动 staging 低敏原件 JSON 可解析：validate=`validated`、deploy=`passed`，Rootless 镜像摘要/运行模式与三健康 HTTP 200 在门禁证据内。运行检查为一个已审核店铺，单会话范围为空、店铺范围精确、人工写入与 Webhook 启用、自动回复/高风险写入/LLM 关闭、未结清出站 0；180 个现有会话的 `send_mode` 均为 `real`，抽查两个为 `real`。原件 SHA-256：validate `98f3bcac6bfd52d9881e6e112bc306a9df52dbbff73336759e04fa24b3a1c1b0`，deploy `744a5b7cbc6f7d1a59d74d03985ccd7cbfa97a0e7f2b762dafd5e26efb0682bd`，runtime `e64ea198c582b6e0bb73ef848295339d3571ebe39a1eafc0764cc3bae6754ba4`。
- 独立 G5 R70 临时窗口结束后，其正式记录确认原后端、修复前端、G3 单店人工发送、三健康与固定出口恢复。本轮已登录工作台又打开同店铺两个不同真实会话，均显示“真实 TikTok 发送”和回复框；原测试会话的空草稿 0/2000 按钮禁用、输入 11 字后启用、清空后禁用。截图及 AX 状态在本任务工具结果。
- 本轮没有点击发送、调用真实消息写接口或运行 GitHub Actions；production 未发布。此前受控单会话真实双向链路以 `MVP-004` R04 为独立证据，不把它冒充本次每个会话的外发结果。

# REQ/AC 与证据映射

AC-01：互斥/空范围配置和门禁测试；AC-02：同店铺 180 个会话运行汇总与两个真实会话现场核对，跨店禁用由定向测试证明；AC-03：工具层和平台客户端双重校验、G5 旧快照与恢复测试及 R70 恢复记录；AC-04：337 项定向回归、格式/类型、手动 staging validate/deploy、已登录 UI。原件为[验证](../../../release/evidence/staging/crm-staging-store-send-validate-20261018.json)、[部署](../../../release/evidence/staging/crm-staging-store-send-deploy-20261018.json)、[运行汇总](../../../release/evidence/staging/crm-staging-store-send-runtime-20261018.json)。

# 缺陷、未执行项与残余风险

未对第二位或全部 180 位买家逐一发送真实消息，不能据 `send_mode=real` 推断每条都被平台接受。staging 当前只审核一个店铺，跨店禁用没有第二个真实店铺现场核对，依赖确定性权限测试。未运行完整后端集成/前端回归或 production 门禁；前端草稿交互由独立 `MVP-WORKSPACE-DRAFT-001` R02 验证。真实 `unknown` 故障未制造，继续按原人工对账流程处理。

# 结论和复测条件

本任务 AC-01～AC-04 对 staging 单店人工发送范围通过，production 不放行。更换店铺列表、渠道授权或 G5 临时恢复模式后必须重跑门禁并核对工作台；出现平台拒绝、`processing/unknown` 时先对账，不能自动重发。
