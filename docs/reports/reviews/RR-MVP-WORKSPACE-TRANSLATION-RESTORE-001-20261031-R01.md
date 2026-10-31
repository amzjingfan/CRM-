---
record_id: RR-MVP-WORKSPACE-TRANSLATION-RESTORE-001-20261031-R01
record_type: review
revision: R01
status: APPROVE
task_id: MVP-WORKSPACE-TRANSLATION-RESTORE-001
reviewed_sha: 1e7e15fba356877876e71f7d70cafcd1235d571e
implementation_record: docs/records/implementation/IR-MVP-WORKSPACE-TRANSLATION-RESTORE-001-20261031-R01.md
test_record: docs/reports/tests/TR-MVP-WORKSPACE-TRANSLATION-RESTORE-001-20261031-R01.md
review_focus: [runtime_configuration, private_backup, exact_image_digests, no_external_send]
created_at: 2026-10-31T00:07:06Z
updated_at: 2026-10-31T00:07:06Z
supersedes: null
---

# 审查范围、依据与重点风险

复核 staging 翻译丢失原因、恢复参数与现有镜像对应性、部署门禁、备份和平台外发边界。文档 subject 1e7e15fb 只补充保留翻译的交付步骤。

# 发现、级别、位置和证据

- 根因是运行容器开关关闭；详情 API 与前端按开关隐藏按钮，未发现翻译组件删除或接口缺失。恢复使用仓库固定 overlay，没有修改应用代码。
- 原版与候选预检通过后部署；运行镜像摘要完全不变、迁移不变。备份文件逐项可读且权限受限。部署初次参数/仓库认证失败均未切换；最终成功门禁与失败事实分开记录。
- 运行后仅翻译开关从 false 变为 true；两店人工发送、Webhook、Agent 模式及自动回复/营销/高风险写入状态未改变。临时 GHCR 登录已退出。

# 已验证与未验证内容

三健康与已登录工作台英文文字消息的翻译按钮已验证；真实供应商翻译调用未执行，不能据此评价译文质量或耗时。生产环境未审查或发布。

# 结论和返修条件

批准本次限定 staging 的配置恢复和文档记录。若后续运行开关再次变为 false，先核对部署参数与 overlay；若按钮可见但调用失败，另查翻译服务链路。
