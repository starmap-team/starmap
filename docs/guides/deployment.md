# 部署指南

> 状态：活文档
> 最近核对：2026-07-24

## 开发编排

```bash
cp .env.example .env
docker compose -f docker-compose.dev.yml config
docker compose -f docker-compose.dev.yml up -d
```

默认服务：backend、celery-worker、frontend、PostgreSQL、Neo4j、Redis。Ollama 通过 `llm` profile 启用；开发编排没有 ChromaDB 服务。

```bash
docker compose -f docker-compose.dev.yml --profile llm up -d ollama ollama-pull
```

检查：

```bash
docker compose -f docker-compose.dev.yml ps
curl http://localhost:8000/health
curl http://localhost:8000/ready
curl http://localhost:5173/
```

## 生产编排

生产 Compose 使用 `.env.production`，后端与 worker 引用预构建镜像，前端在 Compose 中构建。部署前先构建后端镜像：

```bash
docker build -f backend/Dockerfile -t starmap-backend:2026.07 backend
docker build -f backend/Dockerfile.celery -t starmap-celery-worker:2026.07 backend
```

准备生产环境：

```bash
# 在安全的密钥管理流程中生成并写入 .env.production
python -c "import secrets; print(secrets.token_urlsafe(32))"

docker compose --env-file .env.production -f docker-compose.prod.yml config
docker compose --env-file .env.production -f docker-compose.prod.yml up -d
```

`docker-compose.prod.yml` 包含 backend、celery-worker、frontend/Nginx、PostgreSQL、Neo4j、Redis、ChromaDB 和 Ollama。确认宿主资源能够承载本地模型；不需要 Ollama 时，应在受控部署变体中移除该服务，而不是让资源不足的容器反复重启。

## 必要生产配置

- `APP_ENV=production`
- `APP_DEBUG=false`
- 长度足够的 `SECRET_KEY`
- `BOOTSTRAP_SEED_ADMIN=false`
- 带密码的 `REDIS_URI` 与匹配的 `REDIS_PASSWORD`
- PostgreSQL SSL mode 为 `require`、`verify-ca` 或 `verify-full`
- Neo4j URI 使用 TLS scheme
- 生产域名的 `CORS_ALLOWED_ORIGINS`
- `secrets/ssl/`、`secrets/postgres/`、`secrets/neo4j/` 中的有效证书和严格文件权限

应用设置校验不满足时会 fail fast。不要通过降低校验或把开发 `.env` 传给生产来绕过。

## 入口与健康

生产前端暴露 80/443，HTTP 由 Nginx 重定向到 HTTPS。FastAPI 端口由 Compose 暴露给运维网络；生产 Swagger、ReDoc 和 OpenAPI UI 被禁用。

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml ps
docker compose --env-file .env.production -f docker-compose.prod.yml logs --tail 200 backend
curl -k https://localhost/
curl http://localhost:8000/health
curl http://localhost:8000/ready
```

`/health` 表示进程可响应；`/ready` 检查 PostgreSQL、迁移、用户种子和 Redis 等启动依赖。部署门禁应使用 `/ready`。

## 数据持久化

生产命名卷保存 PostgreSQL、Neo4j、Redis、Chroma 和 Ollama 数据。备份前确认实际 Compose project name，以 `docker volume ls` 的结果为准，不在脚本中假设裸卷名。

PostgreSQL 示例：

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml exec -T postgres \
  pg_dump -U starmap -d starmap > starmap-postgres.sql
```

Neo4j dump 需要按 Neo4j 版本和容器权限停止写入或使用受支持的在线备份方案。恢复演练应在隔离环境执行，并同时验证 PG 权威记录和 Neo4j 投影的一致性。

## 更新

```bash
git pull --ff-only
# 重新构建受影响镜像
docker compose --env-file .env.production -f docker-compose.prod.yml up -d
curl http://localhost:8000/ready
```

模型或数据库变更上线前执行 Alembic 检查。不要在生产容器内手工修改表结构或图数据；图不一致时使用受审计的 reconcile/rebuild 脚本。

## 故障定位

| 现象 | 首查 |
|---|---|
| backend 不健康 | backend 日志、`.env.production`、PG/Redis/Neo4j 健康状态 |
| `/ready` 503 | 返回的依赖检查、Alembic head、users 表和 Redis |
| 前端 502 | Nginx upstream、backend 健康状态、`/api/v1` 路径 |
| Celery 无任务 | broker URI、worker queue、worker inspect ping |
| 图谱与岗位列表不一致 | PG 记录、outbox 状态、GraphProjector/reconcile |
| LLM 超时 | 云端 key、网络、Ollama 模型和资源限制 |