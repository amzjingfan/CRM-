# TikTok OAuth 快速回跳（staging）

用户于 2026-09-24 确认：沿用现有 jobs worker 异步完成授权，callback 立即跳回 CRM，一次性 state 不得重放；先在 staging 验证，production 不变。

## 问题与边界

真实授权的入口日志显示同一浏览器来源的 callback 首次约 4.17 秒后以 499 断开，随后重复 callback 返回 400；后端继续完成 Token/店铺校验并保存 connected。浏览器因此未收到 303。重复调用不可再次交换 Token，不能通过延长浏览器等待、放宽 state 或泄露 code 来修复。

另有独立的卖家类型门禁：当前绑定店铺为美国市场、跨境卖家、主体地区 HK；应用截图仅显示美国本土与中国跨境。普通 Chrome 新授权在 TikTok 侧报 seller type 不适用，未进入 callback。目标卖家配置需由用户在 Partner Center 核对；本设计不绕过平台门禁。

## 方案

1. callback 先只读校验 Redis state 绑定及发起用户/店铺，按 state 摘要创建唯一的短期数据库任务。state 与 code 使用现有服务端密钥分别加密保存；不写入日志、API 响应或明文持久层。重复 callback 返回同一任务的站内进度页，不创建第二任务。
2. callback 在本地事务提交后立即以 303 回到固定 `/settings/channels`，仅携带低敏任务 UUID 和 `processing` 状态；Redis state 仍由 worker 原子 GETDEL。拒绝不受信的 return_to。
3. 现有 jobs worker 按 FIFO 领取 pending 任务，以 `FOR UPDATE SKIP LOCKED` 行锁贯穿一次性 state 消费、平台调用及数据库终态提交；processing 不单独提交。渠道、成功审计、任务 connected 和临时密文清除在同一事务提交。平台失败时用保存点撤销部分渠道写入，外层任务锁一直保持到 failed、密文清除和低敏审计一同提交；任务超出 state 有效期则失败关闭。进程崩溃时事务回滚为 pending；再次领取若 state 已消费则失败关闭，不重放 code。持锁期间第二个 worker 跳过该任务，避免固定超时误判仍在运行的调用。
4. 登录用户仅可查询本人发起、仍有店铺访问权的任务状态。渠道页短时轮询并展示 connected、failed 或超时；不自动开启真实读取、写入、Webhook、LLM 或自动回复。

## 验收

- callback 不等待 TikTok 外部请求即可 303；重复回调不再次交换 Token；无效、过期、越权 state 失败关闭。
- worker 成功绑定当前店铺；跨店铺冲突、Token/Scope 异常不形成部分成功；临时密文终态清除。
- 任务状态不得跨用户/店铺读取；URL、响应、日志和证据不含 code、state、Token 或客户数据。
- staging 真实回跳需在平台卖家类型配置允许后由用户亲自授权复测；production 不部署。
