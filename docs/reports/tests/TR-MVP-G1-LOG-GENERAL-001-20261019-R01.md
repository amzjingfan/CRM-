---
record_id: TR-MVP-G1-LOG-GENERAL-001-20261019-R01
record_type: test
revision: R01
status: PASS
task_id: MVP-G1-LOG-GENERAL-001
tested_sha: 91f1593d98db710da2febb29ff8686da3617accf
implementation_record: docs/records/implementation/IR-MVP-G1-LOG-GENERAL-001-20261019-R01.md
requirement_ids: [MVP-G1-LOG-GENERAL-001, G1-L]
acceptance_ids: [G1-L]
environment: Windows local backend Python 3.11; staging Rootless Docker real TikTok read-only probe; GitHub Actions unused
created_at: 2026-10-19T16:34:54+08:00
updated_at: 2026-10-19T16:34:54+08:00
supersedes: null
---

# 测试范围、环境与 TEST_LAYOUT

`TEST_LAYOUT=centralized`。本轮新增测试位于 `src/tests/backend/platform/test_tiktok_read.py`；现场证据来自 staging 已连接且具有 `seller.logistics` 的 TikTok 渠道。真实订单按用户 Seller Center FedEx 截图末 4 位在四页官方订单清单中唯一匹配，并用官方订单详情确认具有跟踪单号。只发一次通用跟踪 GET，禁用本次探针重试。现场不输出订单、运单、买家、店铺、Token、签名、平台正文或请求 ID。

# 命令和逐项结果

- `uv run python -m pytest ../tests/backend/platform/test_tiktok_read.py -q -k standard_tracking`：先因缺少方法而 5 个用例失败；实现后 6 passed。
- `uv run python -m pytest ../tests/backend/platform/test_tiktok_read.py -q`：39 passed。
- `uv run python -m pytest -q`：2168 passed、27 skipped、2 个依赖弃用警告，约 300.71 秒。
- `uv run ruff check . ../tests/backend ../tests/integration/postgres`：通过。
- `uv run ruff format --check . ../tests/backend ../tests/integration/postgres`：313 个文件格式通过。
- `uv run mypy app scripts`：184 个源码文件通过。
- staging 通用跟踪只读探针：官方搜索 4 页、末 4 位唯一匹配、订单详情一致、平台业务码 0、`data.tracking` 列表 11 条。见[机器证据](../../../release/evidence/staging/crm-staging-g1l-generic-fedex-20261019.json)。

# 验收映射与结论

用户确认“通用物流接口通过即 G1-L 放行”。上述真实响应满足该窄范围；通用客户端的固定路径、签名上下文、Scope、结构失败关闭和订单 ID 校验通过确定性测试。按此范围 G1-L **staging 通用 API 验收 PASS**。

现场探针使用原运行后端已有签名与请求逻辑，新增正式客户端还未发布/部署；因此不声称 CRM 页面或新镜像已运行通用物流。未逐条对比 Seller Center 时间与状态，USPS 未查；没有 CBT `202604` 成功证据。G2 完整异常投递、G6/G8 与 production 不因本项通过而关闭。
