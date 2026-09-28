---
record_id: TR-MVP-READONLY-LOG-001-20260928-R01
record_type: test
revision: R01
status: PASS
task_id: MVP-READONLY-LOG-001
tested_sha: a2f4da8e12ae10efb27adea400f96b9e037cd6ea
implementation_record: docs/records/implementation/IR-MVP-READONLY-LOG-001-20260928-R01.md
requirement_ids: [MVP-READONLY-LOG-001]
acceptance_ids: [AC-01, AC-02, AC-03]
environment: Windows PowerShell; uv 0.12.3; Python 3.11.15; synthetic URL and isolated local tests; no real TikTok call
created_at: 2026-09-28T09:20:00+08:00
updated_at: 2026-09-28T09:33:00+08:00
supersedes: null
---

# 测试范围、环境与 TEST_LAYOUT

`centralized`：新增测试位于 `src/tests/backend/runtime_infrastructure/`；仅使用合成标识与本地解释器子进程。未读取真实凭证、业务数据或外部网络。

# 命令和逐项结果

- 旧脚本上两个新测试分别因合成签名 URL 可见、聚合 JSON 缺失而预期失败；首轮修复后 `uv run python -m pytest ../tests/backend/runtime_infrastructure/test_tiktok_readonly_script_logging.py -q` 为 2 passed。
- 初审发现默认 traceback 可泄漏异常链；新增失败路径测试先因本机子进程 stderr 编码差异报测试工具解码错误，调整测试解码后重跑，确因合成订单哨兵出现在 stderr 而失败；入口修复后同文件 3 passed，非零退出与固定低敏事件均得到断言。
- 最终提交 `a2f4da8` 后在 `src/backend/` 执行 `uv run python -m pytest -q`：1650 passed、18 skipped、2 warnings，耗时 73.74 秒；警告为既有 Starlette/httpx 与 passlib/argon2 的弃用提醒。
- `uv run ruff check . ../tests/backend ../tests/integration/postgres`：通过；`uv run ruff format --check . ../tests/backend ../tests/integration/postgres`：254 files already formatted；`uv run mypy app scripts`：168 source files 无问题；`uv lock --check`：通过。
- Windows Unicode 路径环境中直接 `uv run pytest ../tests/backend/platform/test_tiktok_read.py -q` 因 `ModuleNotFoundError: app` 在收集阶段失败；同目录改用 `uv run python -m pytest ../tests/backend/platform/test_tiktok_read.py -q` 为 26 passed。该环境差异未通过改产品代码绕过。
- `git diff --cached --check` 在 subject 提交前通过；最终证据提交前再运行 `git diff --check` 与记录链接/敏感内容核对。

# REQ/AC 与证据映射

- AC-01：进程级测试调用真实脚本入口安装日志出口，再发送合成 `httpx` INFO 事件，签名、店铺和订单哨兵不在 stdout/stderr；输出包含安全事件 `http_client_request`。另一进程级测试注入含合成店铺/订单哨兵的异常链，确认仅输出 `tiktok_readonly_smoke_failed` 与异常类型、退出码为 1。
- AC-02：`verify()` 使用隔离替身仅替换外部数据源，成功输出精确包含六项整数计数，无店铺、订单或消息正文。
- AC-03：全量后端、Ruff、格式、mypy、锁文件按最终 subject 复核；跳过与 warning 如上。

# 缺陷、未执行项与残余风险

本 TR 仅验证本地脚本日志安全与现有回归，不证明 staging 当前容器已包含修复，也不关闭 G1。没有再次调用真实 TikTok；此前现场只读预检显示基础店铺、订单、旧版物流、会话和消息读取成功，但增强物流 `202604` 返回 `11007009`，该码的含义未确认。Token 生命周期、店铺隔离与重复 OAuth 回调现场测试未完成；production 未部署。

# 结论和复测条件

本地日志安全测试为 `PASS`，不代表 PR/CI、现场部署或 G1 通过。如交付内容再变，需重新确定 subject 并重跑受影响验证。现场需合并后的不可变镜像单独部署 staging，再执行低敏真实冒烟。
