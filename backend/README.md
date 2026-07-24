# StarMap 后端

FastAPI 应用、领域核心、服务层、SQLAlchemy 模型和 Celery worker 位于本目录。

## 启动

```bash
cd backend
poetry install
poetry run python -m scripts.bootstrap
poetry run uvicorn app.main:app --reload --port 8000
```

也可从仓库根运行：

```bash
docker compose -f docker-compose.dev.yml up -d backend celery-worker
```

开发 API 文档：<http://localhost:8000/docs>。

## 质量命令

```bash
cd backend
poetry run ruff check .
poetry run mypy app
poetry run pytest
```

`pytest` 会读取 `pyproject.toml` 并执行当前覆盖率门禁；不要在 README 中复制测试通过数或实测覆盖率。

## 结构

| 路径 | 职责 |
|---|---|
| `app/api/v1/` | HTTP 路由和依赖注入边界 |
| `app/schemas/` | 集中式 Pydantic 请求/响应模型 |
| `app/core/` | extraction、evolution、learning、matching、pipeline、validation 等领域逻辑 |
| `app/services/` | 业务编排、数据访问和图投影 |
| `app/models/` | SQLAlchemy ORM |
| `app/tasks/` | Celery 任务入口 |
| `alembic/` | PostgreSQL 迁移 |
| `tests/` | 单元与集成测试 |

## 约束

- API 变更先修改 `../starmap-contracts/openapi.yaml`。
- 路由直接使用 `app/schemas/`，不内联新的 Pydantic API 模型。
- 数据模型变化必须新增 Alembic migration。
- PostgreSQL 是业务事实源；Neo4j 写入通过服务/投影层完成。
- 配置来自 `app/config.py` 与环境变量；`.env.example` 是字段参考，不保存真实密钥。