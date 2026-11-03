---
record_id: TR-MVP-AGENT-REALSHOP-API-001-20261103-R01
record_type: test
revision: R01
status: PASS
task_id: MVP-AGENT-REALSHOP-API-001
tested_sha: fc5d0c70e3d508b9ba78949a5d609f28ee234559
implementation_record: null
review_record: docs/reports/reviews/RR-MVP-AGENT-REALSHOP-API-001-20261103-R01.md
requirement_ids: [USER-REAL-SHOP-API-TEST]
acceptance_ids: [AC-01, AC-02, AC-03]
environment: staging real TikTok US and XBM, current authenticated administrator
created_at: 2026-11-03T04:20:35.889428+00:00
updated_at: 2026-11-03T04:20:35.889428+00:00
supersedes: null
---

# 实际验收范围

用户授权向指定TikTok US测试买家发送明确标注的虚拟订单测试消息、结束清理合成数据；买家无订单时以正确空结果为准。随后用户明确允许XBM现有买家验证增强物流。本次仅验收现有接口连通性和定向真实发送，不改代码、模型、配置、策略或数据结构；IR=N/A，无新部署、无需重复本地产品全量回归。真实输入仅必要已授权字段，内存JWT保留既有有效登录会话/auth_version、CSRF和店铺权限。

| 能力/现场 | 本次结果 |
|---|---|
| US指定买家身份/窗口 | 当前grant/identity/window均true；可信已有入站3条，不伪造新入站 |
| US正式工作台查单 | HTTP200/code0，0订单；空结果正确 |
| US本店官方订单读取 | 列表20，202507详情精确匹配1笔；通用202309物流8节点 |
| US抽样增强物流 | 平台拒绝11007009，应用映射502/50003；该样本不计通过，原结果保留 |
| US Agent实际调试 | HTTP200，review_ready，非空英文答案；search_customer_orders succeeded，内容正确说明无订单 |
| US真实发送及回读 | 仅1条TEST ONLY虚拟订单示例，通过正式确认/幂等发送接口HTTP200/code0，sent/real，有平台消息ID；官方消息历史同ID可见，CUSTOMER_SERVICE |
| XBM正式买家订单/详情 | HTTP200/code0，1订单，增强物流可用 |
| XBM正式增强物流 | HTTP200/code0，1包裹、15节点；没有向该买家发送消息 |
| XBM Agent实际调试 | HTTP200，review_ready，非空答案；search_customer_orders和query_logistics实际succeeded |
| 清理与安全 | 未创建合成订单/临时Agent/知识文件，故没有此类业务fixture需删除；真实消息、回执、运行和发送审计保留。Token只在内存，运行进程结束；原策略未修改 |

# 原件、差异和未执行

受控runner位于唯一测试临时根，确切脚本/原始输出SHA256见[低敏证据](../../../release/evidence/staging/crm-real-shop-api-20261103.json)。原请求脚本首次缺SidebarSearch.field返回422，补齐真实schema后200；增强错误捕获首次误把字符串枚举转int使runner退出，改为numeric_code后重跑只读请求，旧失败原件保留。没有重复真实发送。

US debug tool_calls为空，但原始响应tool_events包含实际搜索成功；证据从已保存private-debug.json提取，不把空tool_calls误报为未调用。XBM亦按tool_events核对。未将缺依据的虚拟订单塞进真实订单表，也没有把US失败样本重标成功。

本PASS表示所列能力各有正式成功样本；不等于所有店铺/所有订单增强接口均可用。发给指定买家的虚拟信息明确声明不是真实购买/发货且无需行动付款；该1条真实发送与平台可见不证明买家已读。未强制自动回复、欢迎、60分钟超时或物流节点事件，不冒称四项自动触发实发成功，也未伪造平台Webhook/订单或放宽安全门禁。
