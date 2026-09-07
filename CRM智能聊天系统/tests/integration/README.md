# 集成测试

用于依赖 PostgreSQL、Redis、MinIO 或完整 HTTP 服务的集成测试。

PostgreSQL/pgvector 集成测试必须使用隔离的 `postgres-test` 服务，禁止连接开发数据库。项目根目录执行：

```powershell
.\scripts\run-postgres-integration-tests.ps1
```

脚本会启动映射到本机 5433 端口的临时测试库、执行全部迁移和 pytest，并在完成后删除临时测试容器。需要保留数据库排查失败时使用 `-KeepDatabase`。

不要使用 `docker compose run --service-ports backend` 执行测试；该命令会与正式 backend 的 8000 端口冲突。一次性测试进程不需要暴露业务端口。
