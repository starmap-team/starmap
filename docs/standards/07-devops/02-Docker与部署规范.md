# Docker 与部署规范

完整操作见 [部署指南](../../guides/deployment.md)。

## 开发

开发 Compose 提供 backend、worker、frontend、PostgreSQL、Neo4j、Redis、ChromaDB；Ollama（含 ollama-pull）位于 `llm` profile，默认不启动。服务依赖使用健康条件，源码 volume 只用于开发。

## 生产

生产 Compose 使用 `.env.production`、预构建后端镜像、Nginx TLS、内部数据库网络，并包含 ChromaDB 与 Ollama。部署前通过 `docker compose ... config` 检查变量解析。

## 规则

- 开发和生产身份严格分开，不让生产读取 `.env` 开发值。
- 密钥、证书和密码不写进 Compose 默认 fallback；现有 fallback 视为需移除的风险，不应复制到新配置。
- 生产只暴露必要端口，数据库不直接暴露公网。
- health 与 readiness 分开；依赖门禁用 readiness。
- 持久化卷在升级前备份并演练恢复。
- 镜像 tag 可追溯，不用 floating latest 上线。
- 资源限制和 worker concurrency 根据实际负载验证。

## 验证

```bash
docker compose -f docker-compose.dev.yml config
docker compose --env-file .env.production -f docker-compose.prod.yml config
```