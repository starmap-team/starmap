# 星图 StarMap

StarMap 是面向信息技术岗位的人才能力知识图谱系统。系统从职位描述和简历中抽取技能，经过归一化与可信度校验后写入 PostgreSQL，并把图关系投影到 Neo4j，用于岗位检索、图谱浏览、匹配诊断、学习路径和技能演化分析。

## 快速开始

### 依赖

- Docker Desktop 或 Docker Engine + Compose v2
- 本地开发可选 Python 3.11-3.12、Poetry 2、Node.js 20+
- 云端 LLM 至少配置一个可提升抽取质量；无密钥时可显式启用 Ollama profile

### Docker 开发环境

```bash
cp .env.example .env
docker compose -f docker-compose.dev.yml up -d
```

开发编排包含 FastAPI、Celery worker、Vue/Vite、PostgreSQL、Neo4j 和 Redis。Ollama 是可选 profile：

```bash
docker compose -f docker-compose.dev.yml --profile llm up -d ollama ollama-pull
```

开发环境不启动 ChromaDB；技能归一化默认使用别名与字符串规则。生产编排仍提供 ChromaDB 作为可选向量能力，不能据此假设开发环境存在 `chroma` 服务。

常用地址：

- 前端：<http://localhost:5173>
- 开发 API 文档：<http://localhost:8000/docs>
- 健康探针：<http://localhost:8000/health>
- 就绪探针：<http://localhost:8000/ready>
- Neo4j Browser：<http://localhost:7474>

### 主机运行应用

先启动数据服务：

```bash
docker compose -f docker-compose.dev.yml up -d postgres neo4j redis
```

再分别启动后端和前端：

```bash
cd backend
poetry install
poetry run python -m scripts.bootstrap
poetry run uvicorn app.main:app --reload --port 8000
```

```bash
cd frontend
npm install
npm run gen:api
npm run dev
```

## 架构边界

- PostgreSQL 保存用户、审计、抽取、岗位、技能、匹配、流水线和演化等权威业务记录。
- Neo4j 是图查询投影；PG 写入成功后由投影/同步服务更新图数据。
- Redis 用于 Celery、缓存、限流和 refresh token 生命周期。
- `starmap-contracts/openapi.yaml` 是跨端 API 契约；Pydantic Schema 位于 `backend/app/schemas/`。
- 前端从 OpenAPI 生成类型，并在 `frontend/src/validation/` 执行请求与响应的运行时校验。

详见 [系统架构](docs/architecture/overview.md)、[数据存储](docs/architecture/data-storage.md) 和 [流水线](docs/architecture/pipeline.md)。

## 质量检查

```bash
cd backend
poetry run ruff check .
poetry run mypy app
poetry run pytest
```

后端 `pytest` 配置当前执行 70% 覆盖率门禁，以 `backend/pyproject.toml` 为准。

```bash
cd frontend
npm run lint
npm run typecheck
npm run test
npm run build
```

```bash
python starmap-contracts/validate.py
python tests/e2e/smoke_test.py --base-url http://localhost:8000 --all
```

Pydantic Schema 变更后同步 JSON Schema：

```bash
cd backend
poetry run python ../scripts/export_json_schemas.py
```

## 仓库结构

| 路径 | 职责 |
|---|---|
| `backend/` | FastAPI、SQLAlchemy、Celery 与领域服务 |
| `frontend/` | Vue 3 应用、Pinia、图表与运行时校验 |
| `crawler/` | 数据采集、合规、清洗与持久化适配 |
| `evaluation/` | Golden Set、baseline 与真实 LLM 评估 |
| `starmap-contracts/` | OpenAPI、JSON Schema 与 Cypher 契约 |
| `tests/` | 契约、集成与 E2E 测试 |
| `scripts/` | 初始化、同步、验证和离线工具 |
| `docs/` | 当前公共文档及历史归档 |

## 文档

从 [文档中心](docs/README.md) 开始。当前事实只来自活文档和代码；阶段报告、审计、旧设计稿与修复计划统一位于 [历史归档](docs/archive/README.md)，不得作为当前行为依据。

开发规则见 [AGENTS.md](AGENTS.md)。文档治理规则见 [docs/governance/documentation.md](docs/governance/documentation.md)。

## 安全

- 不要提交 `.env`、`.env.production` 的真实密钥或测试生成的认证状态。
- 生产必须设置 `APP_ENV=production`、`APP_DEBUG=false`、强 `SECRET_KEY`、带认证的 Redis URI、PostgreSQL SSL 和 Neo4j TLS。
- 生产环境禁用 Swagger/ReDoc/OpenAPI UI；运维验证使用 `/health` 和 `/ready`。