# PostgreSQL 与对象存储备份恢复

生产备份必须在受控运维主机执行，并写入加密、受访问控制的备份目录。脚本不会把数据库密码、MinIO 密钥或业务正文输出到日志。

## PostgreSQL

备份使用逻辑 SQL，恢复脚本要求 `-ConfirmTarget` 与目标数据库完全一致，并再次触发 PowerShell `ShouldProcess` 确认：

```powershell
.\src\scripts\backup-postgres.ps1 -OutputFile D:\crm-backups\crm-20260822.sql
.\src\scripts\restore-postgres.ps1 -InputFile D:\crm-backups\crm-20260822.sql -Database crm -ConfirmTarget crm -Confirm
```

恢复前应先停止 backend、worker、jobs 和 agent-worker，避免恢复期间产生新写入。恢复后执行 `alembic current`、`/v1/health/ready` 和抽样业务查询。恢复脚本不会自动删除数据库，也不会绕过目标确认。

## MinIO

对象存储使用 Docker Compose 的容器复制能力，保留对象键目录结构：

```powershell
.\src\scripts\backup-minio.ps1 -OutputDirectory D:\crm-backups\minio-20260822
.\src\scripts\restore-minio.ps1 -InputDirectory D:\crm-backups\minio-20260822 -ConfirmTarget crm-minio -Confirm
```

MinIO 恢复会覆盖同名对象但不会主动清空目标桶。完整灾难恢复演练必须由测试工程师在隔离环境验证数据库版本、对象数量、FAQ 导入文件和审计数据的一致性。

## Redis

Redis 仅保存可重建缓存、登录限流、Refresh Token 撤销和短期任务协调状态，不作为订单、消息、审计或 Agent 运行事实的权威存储。灾难恢复不复制未知来源的 Redis 快照；启动空 Redis 后，要求所有用户重新登录，并由 PostgreSQL 中的任务状态恢复 Worker。恢复窗口内保持真实平台写操作和自动回复关闭。
