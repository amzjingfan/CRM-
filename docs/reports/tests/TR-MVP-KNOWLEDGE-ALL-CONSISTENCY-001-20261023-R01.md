---
record_id: TR-MVP-KNOWLEDGE-ALL-CONSISTENCY-001-20261023-R01
record_type: test
revision: R01
status: PASS
task_id: MVP-KNOWLEDGE-ALL-CONSISTENCY-001
tested_sha: 662da11e4bad0785c7b1338bc7de0c8f22dd47d5
implementation_record: docs/records/implementation/IR-MVP-KNOWLEDGE-ALL-CONSISTENCY-001-20261023-R01.md
requirement_ids: [MVP-KNOWLEDGE-ALL-CONSISTENCY-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
environment: Windows local isolated PostgreSQL and Next production build; staging rootless Docker linux/amd64 at merged main c7f601fd
created_at: 2026-10-23T09:38:00Z
updated_at: 2026-10-23T09:38:00Z
supersedes: null
---

# 测试范围、环境与 TEST_LAYOUT

`TEST_LAYOUT: centralized`。回归源码位于 `src/tests/`；本地验证绑定源码 subject `662da11e4bad0785c7b1338bc7de0c8f22dd47d5`，它与合并主线 `c7f601fdf27655235449deb66e634a4e2ad27245` 的文件树一致。staging 只读冒烟使用已有 QA 账号，凭据及完整门禁输出仅存主机私有目录；仓库只保留[低敏聚合证据](../../../release/evidence/staging/crm-staging-knowledge-all-category-20261023.json)。

# 命令和逐项结果

- 回归先红后绿：旧页面在“全部知识”空态断言失败；修复后浏览器用例通过。PostgreSQL 集成用例旧接口对新参数报错，修复后验证未分类排除、同店有效分类纳入及总数/分页一致。
- `PYTHONUTF8=1` 后端完整套件：2380 passed、3 skipped、2 warnings；Ruff、格式与 mypy（208 源文件）通过。首次未设 UTF-8 的 Windows 运行因 Git 文件名 GBK 解码失败 1 项，定向确认后用 UTF-8 完整重跑通过。
- 前端契约 48/48，Next 生产浏览器 87/87，TypeScript 类型检查与生产构建通过；lint 为 0 error、5 条既有 warning。
- [PR #546](https://github.com/CP11-gh/CRM/pull/546) 的 backend/frontend GitHub Actions 均在零步骤失败，不能计为 CI 通过。本地门禁通过后 PR squash 合入主线；干净主线构建的 backend/frontend `linux/amd64` 镜像 OCI revision 为合并 SHA。
- staging 私有可读 PostgreSQL 备份、配置 `ValidateOnly=validated`、`Deploy=passed`；迁移头已应用、运行模式核对通过。运行前后端精确摘要一致，检索与解析器原摘要未变；前端、后端与检索健康，解析器运行中。公网 `/knowledge` 和 `/v1/health` 为 200。
- staging 数据库只读复核：通用文件 11 个，未分类 11、已分类 0；带认证 API 中分类数 0，`/files` 默认 total 11，`categorized_only=true` total 0；FAQ 默认及筛选 total 均为 0。两个列表均为 HTTP 200；没有删除或重新分类旧数据。

# REQ/AC 或门禁与证据映射

- AC-01：未分类历史文件在新页面筛选中 total 0；默认 API 仍为 11，数据保留。
- AC-02：集成测试覆盖同店有效分类计数及分页；前端浏览器覆盖分类角标、切换与合并列表。
- AC-03：浏览器用例验证未选择分类时手工新增 FAQ/文件不发起请求；旧表格导入保持已有流程。
- AC-04：API 参数默认兼容、完整本地回归、staging 精确部署及带认证只读冒烟完成。

# 缺陷、未执行项与残余风险

真实已登录 staging 页面未通过 UI 工具直接点击；页面行为由生产浏览器合成回归和已部署后端认证 API 共同覆盖，不能把它表述为真实页面视觉验收。没有创建真实分类或上传真实文件验证未来新增数据；集成与浏览器回归覆盖该路径。GitHub Actions 零步骤失败是 CI 证据缺口，不是本地测试通过。production 未部署，G8 No-Go。

# 结论和复测条件

对本任务既定 AC 与 staging 只读范围为 `PASS`。若后续要求真实已登录页面点击、新建分类或历史文件归类，应在受控店铺单独复核。任何分类定义、查询权限、上传契约或镜像变化均需重跑相应测试与门禁。
