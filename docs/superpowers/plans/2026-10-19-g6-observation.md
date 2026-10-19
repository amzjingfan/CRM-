# G6 连续稳定性观察实施计划

**目标：** 在 staging 取得连续 72 小时、至少 99.5% 可用性的可复核原始证据，并验证告警、资源、积压与故障恢复。

**基线：** `62960a40c1f7d2f041e3aae2553bd32acc8171ea`；目标 `origin/main`；任务 `MVP-007`。验收源为 `docs/product/MVP.md` 和 `docs/operations/RELEASE-GATES.md`。只使用现有 `crmdeploy` Rootless Docker 与 systemd 用户实例，不新建产品服务或付费监控平台。

**约束：** 只观察 staging，不发送 TikTok 消息、不开启自动回复、不碰 production 或公司系统 Docker；原始记录只含固定健康状态、资源聚合和时间戳，保存在主机私有目录；缺样本计不可用，历史运行片段不拼接。CI/CD 零步骤失败不计通过，使用本地针对性测试和手动 staging 预检。

## 任务 1：采集与判定

- [x] 先在 `src/tests/backend/runtime_infrastructure/test_staging_g6_observer.py` 写失败测试：72 小时窗口、缺样本、重复槽位、失败槽位、未满窗口不得通过。
- [x] 在 `src/backend/scripts/observe_staging_g6.py` 实现固定公网健康、Rootless helper 与实际固定出口每分钟采集；每五分钟采集资源和 backend TCP 队列。仅输出低敏 JSONL，首次故障与恢复写本地告警事件。
- [x] 本地运行目标测试、格式/静态检查和失败注入；核对不读取或输出凭证、正文和完整环境。

## 任务 2：现场前置与启动

- [ ] 从合入 main 的脚本核对 SHA-256，经受控 SSH 放入 `crmdeploy` 私有目录；核对 UID 1004、Rootless socket、健康与固定出口。
- [ ] 预先做一次受控 helper 故障与恢复演练，核对失败关闭、恢复后的固定出口和其他容器状态；不把演练时段纳入观察。
- [ ] 以独立 systemd 用户服务启动 72 小时采集，冻结 UTC 起止、源码 SHA、脚本 SHA 和运行容器身份；立即核对首个样本及告警路径。

## 任务 3：持续核对与结束

- [ ] 观察期间按原始槽位和日志确认运行、告警、资源、队列及缺口；异常及时记录和恢复，不放宽安全或失败关闭规则。
- [ ] 72 小时结束后计算 4320 个分钟槽位，可用不少于 4299 槽（累计不可用最多 21 个整分钟槽，较 21 分 36 秒上限保守）；缺样本视为不可用。只有证据齐全且恢复演练通过才关闭 G6。
- [ ] 形成低敏证据与 IR/TR/RR，更新 `TASKS.md`、`TEST-STATUS.md`、`RELEASE-GATES.md` 和 `PROJECT-STATE.md`，经审查合并；G8/production 另行决策。
