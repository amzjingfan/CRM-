# 项目状态与恢复入口

2026-10-30 `MVP-DEPARTMENT-UNIFIED-DISPATCH-001` 源码 subject `f86458c35bf4a76c2d3dc8765d1186b41cf978e0` 已经 PR #668 squash 合入主线 `0fc2b50b993d2f53e63d1b555fd60a26add268d4`。同版前后端已从该干净主线直接部署 staging：私有备份、原版/候选 ValidateOnly、Deploy、045、12 服务、固定出口、三个健康接口与账号/部门页面 200 通过；已登录部门页显示全局管理员和主管两行，进一步派单页浏览器读取超时。部门派单开启但参与者 0 位；旧令牌需刷新或重新登录才能计在线。人工真实发送仍限原两家已授权店铺，Agent 调试/建议保持，自动回复、营销、高风险写入关闭；本轮无真实买家外发、无 production 发布。见[发布 TR](../reports/tests/TR-MVP-DEPARTMENT-UNIFIED-DISPATCH-STAGING-001-20261030-R01.md)与[精确证据](../../release/evidence/staging/crm-staging-department-unified-dispatch-20261030.json)。证据 PR #669 已合并到主线 `4bcc638f13587c54e374c705c9b9c5bc947c038e`。用户新增的冗余说明移除任务 `MVP-DEPARTMENT-RECEPTION-COPY-001` 已在 `fix/department-reception-copy-20261030` 验证，subject `af29152e19ad252a5bb6f25c0b33b84a42cf511a`，待 PR 合并与 staging 前端更新；本分支索引为 `CANDIDATE_VIEW`，根 checkout 未改动。下一动作：①合并文案修复；②从合并主线部署前端并现场核对；③坐席刷新/重新登录后观察在线与派单资格。

2026-10-30 最新 staging 从干净合并主线 `4483ec9b512f698721d2db6500d54e0bbfd95b8e` 仅部署账号多店授权和派单资格说明的前端修复，后端及运行开关不变。私有备份、双 ValidateOnly、最终 Deploy、044、12 服务、公网健康和已登录账号/部门派单只读回显通过；[发布证据](../../release/evidence/staging/crm-staging-team-multistore-reception-20261030.json)与 [TR](../reports/tests/TR-MVP-TEAM-MULTISTORE-RECEPTION-STAGING-001-20261030-R01.md)。PR #666 已合入主线 `44d5e4efc3d5e1f329e35a944934bc32d6de2ad1`，三索引从权威主线记录复核为 `CURRENT`。现场只读快照显示账号 2 位（全店管理员和 1 店主管）；TikTok US 测试店铺派单开关已开启，但没有合格客服可接待；XBM 派单关闭。人工发送仍限原两家已授权店铺，自动回复、营销、高风险写入关闭；零真实买家测试外发，production No-Go。源码 subject `4483ec9b512f698721d2db6500d54e0bbfd95b8e`，证据 HEAD 现场读取。

2026-10-30 此前 staging 从主线 `eb76837823f9e200f47db4a7786d4e91a94f9997` 发布部门角色、逐店派单摘要、账号部门选择与菜单可见性修复；前端新摘要 `903acf1a…74860`，后端原摘要不变。私有备份、双 ValidateOnly、Deploy、044、12 服务、五个公网路径和已登录账号菜单通过。低敏[发布证据](../../release/evidence/staging/crm-staging-department-role-ui-20261030.json)及[TR](../reports/tests/TR-MVP-DEPARTMENT-ROLE-UI-STAGING-001-20261030-R01.md)。人工发送范围与安全开关未变，零外发，production No-Go；`CANDIDATE_SUBJECT_SHA=eb76837823f9e200f47db4a7786d4e91a94f9997`，`EVIDENCE_HEAD_SHA=READ_AT_GATE`。发布证据 PR #662 已合入主线 `9d8264689f5445a87557f6b3ce4423e3a49cf1ad`；三索引已从权威主线源记录重建为 `CURRENT`。

2026-10-30 部门角色、逐店派单摘要、账号部门选择和“更多”菜单完整显示已通过 PR #660 合入主线 `6b9b2bc450e54d88760ae33d31217055db5ec34c`；源码 subject `0fb8202f5b39b77e085228b3dd6acc64ecf88c35`，验证见 [TR R01](../reports/tests/TR-MVP-DEPARTMENT-ROLE-UI-002-20261030-R01.md)。前端生产构建浏览器回归 56 项通过，后端全量 2658 通过、77 跳过；staging 已连接测试店合成入站事务回滚，零外发、零残留。PR 两项 Actions 为 0 步骤失败，按本地替代门禁记录为 CI 未运行。此 UI 变更已从合并主线发布 staging，现场证据见首段。

2026-10-30；治理档位 STANDARD；TikTok 人工辅助；CP11-gh/CRM；origin/main；此前人工发送发布源码 `18a0d7bb0b0ca6b2bb601de32af7128d1a41a9ec`，`EVIDENCE_HEAD_SHA=READ_AT_GATE`；任务状态以 [TASKS](../tasks/TASKS.md) 为准。staging 从干净合并主线 `18a0d7bb` 的同版不可变镜像手动扩展人工发送至两家已授权 TikTok 店铺，迁移头 `044_reception_assignment`。精确镜像、私有备份、ValidateOnly/Deploy、12 容器、固定出口、三健康及只读发送模式见 [全店人工发送证据](../../release/evidence/staging/crm-staging-all-store-manual-send-20261030.json)和 [TR R01](../reports/tests/TR-MVP-TIKTOK-ALL-STORE-MANUAL-SEND-001-20261030-R01.md)。发布证据 PR #658 已合入主线 `a3380c7e`，任务完成；三索引从权威主线源记录重建为 `CURRENT`。production 未发布。

此前部门接待与派单从干净主线 `b21f59a76adce8775eb5f9d61993e3b42886d72a` 发布，部门现场与清理事实见[部门发布证据](../../release/evidence/staging/crm-staging-department-assignment-20261030.json)和[TR R02](../reports/tests/TR-MVP-DEPARTMENT-AUTO-ASSIGN-001-20261030-R02.md)。PR #654/#655 已合入主线；全店人工发送由后续独立发布扩展。

本轮发布记录 PR #656 已合入主线 `3a97bf4371ec58ba088005a1dd673f1b7a17f0a8`；IR/TR/RR 三项源记录从合并主线复核并更新索引为 `CURRENT`。PR 的两项 CI 在零步骤时失败，按持续批准的本地替代门禁处理，不记为 CI 通过。

主线 PR #652/#653 的授权单入口源码现已包含于当前 staging 镜像：授权页旧卡片与全局入口移除，异常店铺行内重新授权绑定自身 store_id；功能测试见[授权 TR R01](../reports/tests/TR-MVP-TIKTOK-OAUTH-UX-001-20261030-R01.md)，独立发布核对见[OAuth 现场证据](../../release/evidence/staging/crm-staging-oauth-single-entry-20261030.json)。模板与批量差异更新仅有[设计提案](../superpowers/specs/2026-10-30-agent-templates-batch-design.md)，尚未实施。

用户指定的 staging 清理已完成：只保留一个系统管理员和「TikTok US 测试店铺」「测试店铺」「XBM」，删除 50 个合成账号及 2 家合成店铺；清理前私有数据库备份、审计、提交后对账及恢复限制见 [CLEANUP-20261030-001](../operations/cleanup/CLEANUP-20261030-001.md)。MinIO 对象未删，未做整库恢复演练。

此前逐店自动派单配置为 0，默认关闭；人工真实发送 allowlist 为「TikTok US 测试店铺」与「XBM」，未接入 TikTok 的「测试店铺」失败关闭。自动回复、自动营销、主动物流通知、高风险平台写入保持关闭；Agent 调试及正式人工建议维持，测试未向真实买家发送消息。在「测试店铺」短暂建立合成两坐席的并发派单与幂等验证已通过，测试账号、配置、咨询及审计清理为 0；真实 TikTok 入站仍未演练。

此前 Agent 回复现场验收见 [TR R01](../reports/tests/TR-MVP-AGENT-REPLY-STAGING-001-20261030-R01.md)；模板与批量差异更新仅为 [设计提案](../superpowers/specs/2026-10-30-agent-templates-batch-design.md)，尚未实施。GitHub Actions 零步骤作业不计通过，按持续批准的本地替代门禁处理。G8 production 仍 No-Go。

Workspace hygiene: ATTENTION。主 checkout 的未知历史、活动 worktree 和未跟踪 `src/frontend/AGENTS.md` 保留；此前对此文件的移除操作被自动批准审查拒绝，本轮未重试。本次仅清理用户精确指定的 staging 账号与店铺，未清理本地未知文件。

下一动作：①若新增已授权店铺，重新核对渠道并更新人工发送 allowlist；②如需证明真实授权体验，在已登录测试店铺执行 OAuth 回跳与多店选择；③若准备让已开启的店铺实际派单，先授权普通客服参与并在受控平台会话补测真实入站。
