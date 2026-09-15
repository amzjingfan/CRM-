# MinIO 部署资源

当前 MinIO 服务由根目录 Docker Compose 管理。K2 通过 `docker-compose.knowledge.yml` 中的一次性 `knowledge-minio-init` 容器创建 `company-knowledge` 桶、专用服务账号并绑定 `company-knowledge-policy.json`。

K2 运行策略只允许列出该桶和读取对象，不能写入、删除或访问 CRM `crm-files` 及其他桶。K3 导入器必须使用另行审批的写入身份，不得复用运行时账号。生产环境必须替换本地示例账号和密码；知识服务运行进程不接收 MinIO root 凭证。
