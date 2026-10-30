---
record_id: IR-MVP-DEPARTMENT-UNIFIED-DISPATCH-001-20261030-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-DEPARTMENT-UNIFIED-DISPATCH-001
base_sha: fe5102c5557e2c0f997c566c9ea5be3e171ecd16
final_sha: f86458c35bf4a76c2d3dc8765d1186b41cf978e0
requirement_ids: [MVP-DEPARTMENT-UNIFIED-DISPATCH-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05, AC-06]
test_record: docs/reports/tests/TR-MVP-DEPARTMENT-UNIFIED-DISPATCH-001-20261030-R01.md
review_record: docs/reports/reviews/RR-MVP-DEPARTMENT-UNIFIED-DISPATCH-001-20261030-R01.md
created_at: 2026-10-30T11:28:22Z
updated_at: 2026-10-30T11:28:22Z
supersedes: null
---

# 实施目标与范围

修复账号店铺多选裁切、主管部门跨店会话范围、逐店派单配置与工作台心跳所造成的操作困惑，并让所有已登录员工可只读查看完整账号目录。仅改变 CRM 内部授权、派单归属和管理页面；没有平台消息发送。

# 实际变更及原因

- 账号抽屉用视口内浮层多选负责店铺，按店保留普通客服或主管角色；账号列表和部门账号目录均返回全体账号，非管理员只读，后端隐藏独立联系方式字段。
- 主管须属于部门且在部门至少一家有效店铺有主管角色，才能监督该部门全部有效店铺会话；普通客服仍逐店核验回复权限。转交候选和会话接管使用同一范围。
- 045 迁移新增登录会话、部门派单配置及参与者表。旧逐店配置按部门合并：任一店铺已开启则部门开启；同一客服任一店铺曾参与则迁入参与状态。旧表保留作兼容与审计。
- 派单由部门统一开关控制，按店铺回复授权筛候选，再按近期服务和部门跨店待回复量选择；不再使用工作台心跳或待回复上限。登录、刷新、退出、禁用和改密更新在线依据。人工归属不被自动覆盖。

# 关键决定与偏差

管理员仍拥有全部店铺权限但不参与自动派单。账号目录的登录名、姓名、部门与角色用于识别员工；非管理员响应的邮箱、手机和上次登录字段为空。用户要求的是登录状态在线，所以旧令牌在首次刷新前仍可用，但不会生成新在线证据。

# 数据、配置、接口、迁移影响

公共接口改为 `GET/PUT /settings/departments/{department_id}/reception`；移除逐店接待配置及工作台接待心跳接口。后端和前端须作为同一发布候选部署。045 数据迁移后有业务数据时拒绝直接 downgrade；恢复以部署前私有备份和旧镜像计划为准，保留部署后增量。

# 验证交接

完整命令、隔离 PostgreSQL 044→045 带数据迁移、浏览器回归与未执行项见对应 TR；授权、数据与迁移审查见 RR。合并与 staging 发布分别另核对，不能以本记录宣称已部署。

# 限制、风险与回滚

部门统一配置会把原来仅部分店铺开启的状态扩展到本部门全部负责店铺，这是已确认的产品目标；发布前必须核对现场参与者和自动发送开关。在线以有效登录会话为准，不以浏览器窗口是否仍打开判断。旧无 sid 令牌须刷新或重新登录才能进入在线名单。
