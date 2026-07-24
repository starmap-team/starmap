# StarMap 入职指南

> 状态：活文档
> 最近核对：2026-07-24

## 项目定位

StarMap 将职位描述、简历和技能本体转换为可追溯的人才能力图谱，提供图谱浏览、岗位匹配、技能差距、学习路径、质量治理和演化分析。

核心链路：

```text
JD/简历 -> LLM 抽取 -> 技能归一化 -> 可信度校验 -> PostgreSQL
                                                    -> Neo4j 投影
PostgreSQL/Neo4j -> API -> Pinia/组件 -> 图谱、匹配、演化和质量页面
```

## 先读什么

1. 根 [README](../../README.md)：运行、质量命令和仓库结构。
2. [系统架构](../architecture/overview.md)：层次与数据流。
3. [数据存储](../architecture/data-storage.md)：PG、Neo4j、Redis 和 Chroma 的职责。
4. [规范索引](../standards/README.md)：按任务定位规则。
5. 目标目录最近的 `AGENTS.md`：模块局部约束。

## 关键目录

| 路径 | 说明 |
|---|---|
| `backend/app/api/v1/` | FastAPI 路由；只做 HTTP 边界和服务调用 |
| `backend/app/schemas/` | 集中式 Pydantic 请求/响应模型 |
| `backend/app/core/` | 抽取、演化、匹配、学习、流水线和校验领域逻辑 |
| `backend/app/services/` | 业务编排、PG/Neo4j 访问和图投影 |
| `backend/app/models/` | SQLAlchemy ORM |
| `frontend/src/api/` | Axios 与 OpenAPI 类型客户端 |
| `frontend/src/validation/` | JSON Schema 运行时校验 |
| `frontend/src/stores/` | Pinia 业务状态和 API 动作 |
| `frontend/src/pages/` | 路由页面 |
| `starmap-contracts/` | 跨团队契约真相源 |
| `evaluation/` | Golden Set 与评估入口 |
| `docs/archive/` | 历史证据，不代表当前状态 |

## 开发流程

### API 变更

1. 修改 `starmap-contracts/openapi.yaml`。
2. 修改 `backend/app/schemas/` 和路由/服务实现。
3. 导出 JSON Schema。
4. 运行 `npm run gen:api` 更新前端类型。
5. 更新 Store 的响应校验和测试。
6. 运行契约、后端和前端质量命令。

### 数据模型变更

1. 修改 ORM model。
2. 新增 Alembic revision；不要修改旧 migration。
3. 验证 upgrade，并在高风险变更中验证 downgrade 或恢复路径。
4. 更新契约、Schema、服务和测试。

### 前端页面变更

页面负责组合，复杂状态进入 Pinia，生命周期和交互进入 composable，可复用视图进入组件。认证、错误格式和 API 字段名不得自行建立第二套约定。

## 运行与验证

```bash
# 开发全栈
docker compose -f docker-compose.dev.yml up -d

# 后端
cd backend
poetry run ruff check .
poetry run mypy app
poetry run pytest

# 前端
cd ../frontend
npm run lint
npm run typecheck
npm run test
npm run build

# 文档
cd ..
pwsh -File scripts/check-docs.ps1
```

需要真实 LLM 或浏览器链路时，再运行对应 evaluation/E2E；不要把一次历史报告中的“已通过”当成本地环境的当前结果。

## 当前实现注意点

- 开发 Compose 不包含 ChromaDB；生产 Compose 包含 ChromaDB。代码必须能在开发环境无 Chroma 时正常降级。
- 当前 ETL 调度入口是三阶段 `crawl -> dedup_clean -> import_sync`，详见 [流水线架构](../architecture/pipeline.md)。
- PostgreSQL 是业务事实源，Neo4j 是可重建投影；岗位列表和图谱浏览使用不同读取语义。
- `frontend/src/api/client.ts` 仍是逐步迁移中的便利封装，新代码应优先使用生成类型，但不要声称所有 Store 已迁移。
- `.planning/` 中旧里程碑和 `docs/archive/` 中旧问题清单只用于追溯。

## 遇到文档冲突

优先级为：运行中的代码/测试结果 -> 配置和迁移 -> OpenAPI/Schema -> 活文档 -> 模块说明 -> 归档。发现冲突时直接修活文档，并把一次性调查结果放入归档，而不是创建新的根目录报告。