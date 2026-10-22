---
record_id: IR-MVP-KNOWLEDGE-PROTOTYPE-UI-001-20261022-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-KNOWLEDGE-PROTOTYPE-UI-001
base_sha: 83e8c605acdf7567017ca6b4ebac882188712b13
final_sha: 64e41b62c476ec97020dd9edc5a6b6d574dbf711
requirement_ids: [MVP-KNOWLEDGE-PROTOTYPE-UI-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
test_record: docs/reports/tests/TR-MVP-KNOWLEDGE-PROTOTYPE-UI-001-20261022-R01.md
review_record: null
created_at: 2026-10-22T10:42:16Z
updated_at: 2026-10-22T10:42:16Z
supersedes: null
---

# 实施目标与范围

只将知识库管理页调整为用户提供的 v4 知识库原型布局和交互；Agent 管理页源文件未修改。用户确认尚未支持的上传格式及检索参数保存仅作页面内演示，不落库。

# 实际变更及原因

- 知识库页使用原型的顶部操作区、分类侧栏、范围卡、搜索筛选、列表、参数抽屉、详情抽屉及新增弹窗。导航图标和品牌仅在知识库路由切换为原型样式。
- 店铺、分类、FAQ 草稿、审批、归档、删除、向量化重试及 CSV/XLSX 异步导入沿用现有接口；保留知识层级查询、URL 状态和旧响应保护。分类编辑与删除收纳在分类弹窗内。
- PDF/Word 等非现有导入格式只加入浏览器内存列表；分块、重叠、召回、阈值、重排和解析选择只在当前页面展示，刷新后复位。页面提示明确说明真实配置与知识数据未被这些演示操作改变。
- 产品范围文档同步写明演示与真实接口的界线。

# 关键决定与偏差

参考原型中的固定示例数据改为当前授权店铺的真实知识数据。项目已配置的索引模型从现有向量化状态读取；现阶段仅有一个可列出的模型。原型未展示的知识层级入口折叠放在分类侧栏，以保留现有 URL 查询能力。

# 数据、配置、接口、迁移或 Prompt 影响

无新增接口、迁移、生产配置或 Prompt。演示文件保留在浏览器内存，不发送到服务端。原有权限、审批和人工发送边界继续由服务端校验。

# 验证交接

见同任务 TR R01。前端生产构建、契约、浏览器交互、类型和 lint 已在最终 subject 上重跑。

# 限制、风险与回滚

真实登录态和 staging 页面未在本任务中部署验收；本地浏览器使用合成 API 响应。需回滚时撤销 subject 提交，不改数据库或模型配置。
