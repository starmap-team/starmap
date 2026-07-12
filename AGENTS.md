# StarMap — 项目指令

## 技术栈

- **后端**: Python 3.11–3.12 / FastAPI 0.110+ / SQLAlchemy async / Neo4j / PostgreSQL / Redis / Celery
- **前端**: Vue 3.4+ / TypeScript 5.4+ / Element Plus / Pinia / ECharts / @antv/G6 / Vite
- **LLM**: 星火 API / MiMo / DeepSeek / Qwen (Ollama)
- **测试**: pytest + vitest + Playwright
- **代码质量**: Ruff + mypy + ESLint + vue-tsc

## 代码风格

- **Python**: snake_case 文件/变量/函数, PascalCase 类, 行宽 120, 用 Ruff 格式化
- **前端**: PascalCase 组件/Vue 文件, camelCase 变量/函数
- **API 字段**: snake_case (如 `match_score`, `skill_name`) — 项目约定，前后端一致，不做 camelCase 转换
- **文件命名**: 模块名简写（`graph.py`, `match.py`, `MatchDiagnosis.vue`）
- **类型注解**: 后端 `from __future__ import annotations` + mypy, 前端 `vue-tsc --noEmit`

## 项目结构

| 路径 | 用途 |
|------|------|
| `backend/app/api/v1/` | API 路由层 |
| `backend/app/core/` | 业务核心 (extraction/, evolution/) |
| `backend/app/services/` | 服务层 (graph, match, resume, judge) |
| `backend/app/models/` | SQLAlchemy ORM 模型 |
| `backend/app/tasks/` | Celery 异步任务 |
| `frontend/src/pages/` | 页面组件 |
| `frontend/src/stores/` | Pinia 状态管理 |
| `frontend/src/components/` | 通用 UI 组件 |
| `starmap-contracts/` | API 契约 (OpenAPI + Cypher), **跨团队真相源** |
| `evaluation/` | 评估套件 (baseline/模拟LLM/真实LLM) |
| `tests/e2e/` | E2E 冒烟 + Playwright 测试 |

## 关键约定

- **契约优先**: API 变更先改 `starmap-contracts/openapi.yaml`，再 `npm run gen:api` 同步前端
- **评估驱动**: 提交前确保 baseline 评测不降级
- **图/业务分离**: Neo4j 查询在 `services/` 中，抽取/演化在 `core/` 中
- **反幻觉**: 每个技能抽取必须附带信任度评分
- **迁移优先**: 模型变更必须走 Alembic 迁移

## 测试

```bash
# 后端
cd backend && poetry run pytest                    # 单元 + 集成 (覆盖率 ≥ 60%)

# 前端
cd frontend && npm run test                        # vitest

# E2E
python tests/e2e/smoke_test.py --base-url http://localhost:8000 --all
```

## 构建 & 运行

```bash
# 全栈 Docker
docker compose -f docker-compose.dev.yml up

# 后端单独
cd backend && poetry run uvicorn app.main:app --reload

# 前端单独
cd frontend && npm run dev

# 代码检查
cd backend && poetry run ruff check . && poetry run mypy app
cd frontend && npm run lint && npm run typecheck
```

## Git 约定

- 分支: `fix/*`, `feat/*`, `chore/*`, `docs/*`
- Commit: `type(scope): description (#PR)`
- PR: squash merge

## 数据流速查

```
JD文本 → extract/jd (LLM抽取) → 归一化 → 反幻觉 → 写入Neo4j
简历   → match/diagnose → 技能对比 → 差距分析 → 学习路径
快照   → evolution/diff → 差异引擎 → 新兴技能 → 信任度聚合
```
