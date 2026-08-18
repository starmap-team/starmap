# 任务寻路

| 任务 | 先读 | 代码入口 |
|---|---|---|
| 运行项目 | [根 README](../../../README.md) | Compose 文件、模块 README |
| 熟悉项目 | [入职指南](../../guides/onboarding.md) | [架构总览](../../architecture/overview.md) |
| 修改 API | [契约规范](../04-contracts/01-API契约规范.md) | `starmap-contracts/openapi.yaml`、`backend/app/schemas/`、`backend/app/api/v1/` |
| 修改后端领域逻辑 | 对应 `01-backend/` 规范 | `backend/app/core/`、`backend/app/services/` |
| 修改前端页面 | `02-frontend/` 规范 | `frontend/src/pages/`、stores、composables、components |
| 修改数据库 | [数据库与会话](../01-backend/12-数据库与会话.md) | models + Alembic |
| 修改流水线 | [Pipeline](../01-backend/07-业务核心-pipeline.md) | core/pipeline + tasks |
| 修改爬虫 | [爬虫规范](../03-crawler/01-爬虫模块规范.md) | `crawler/` |
| 修改 CI/部署 | `07-devops/` 规范 | `.github/workflows/`、Compose、Dockerfile |
| 写/移动文档 | [文档治理](../../governance/documentation.md) | `docs/`、模块 README/AGENTS |
| 查历史报告 | [归档索引](../../archive/README.md) | `docs/archive/` |

## 决策顺序

1. 读取目标目录最近的 `CONTRIBUTING.md`。
2. 读取契约、配置和当前实现。
3. 用测试或可重复命令确认现状。
4. 修改最小职责范围，并同步对应活文档。
5. 不从归档或 `.planning/` 复制旧状态作为当前结论。