# StarMap 代码规范文档

> 本规范提取自项目实际配置文件与代码实践，覆盖后端（Python/FastAPI）与前端（Vue 3 + TypeScript）双栈。
> 生成日期：2026-07-05

---

## 1. 命名规范

### 1.1 文件命名

#### Python（后端 `backend/app/`）

| 类型 | 规范 | 示例 |
|------|------|------|
| 模块文件 | `snake_case.py` | `graph_service.py`, `evolution_models.py` |
| 测试文件 | `test_<module>.py` | `test_graph_service.py` |
| 路由文件 | `<feature>.py` | `graph.py`, `position.py` |
| 模型文件 | `<feature>_models.py` | `evolution_models.py`, `extraction_models.py` |
| 配置文件 | `config.py`（单数） | `config.py`, `dependencies.py` |
| 入口文件 | `main.py` | `main.py` |
| Alembic 迁移 | `XXX_<description>.py`（3位数字） | `003_add_evolution_tables.py` |

#### TypeScript / Vue（前端 `frontend/src/`）

| 类型 | 规范 | 示例 |
|------|------|------|
| Vue 组件 | `PascalCase.vue` | `Graph2D.vue`, `DetailPanel.vue` |
| 页面组件 | `PascalCase.vue`（语义化） | `HomeGraphSection.vue` |
| Store 文件 | `<feature>.ts`（kebab-case） | `graph.ts`, `dashboard.ts` |
| Composable | `use<Feature>.ts`（camelCase） | `useKPIMetrics.ts`, `useSSE.ts` |
| API 请求 | `request.ts`, `schema.ts` | `request.ts` |
| 工具函数 | `<feature>.ts` | `graphColors.ts` |
| 样式文件 | `*.css` / `*.scss` | `animations.css` |

### 1.2 类命名

#### Python

| 类型 | 规范 | 示例 |
|------|------|------|
| Pydantic 模型 | `PascalCase`，语义化 | `GraphNode`, `PositionNode`, `SkillNode` |
| SQLAlchemy 模型 | `PascalCase`，表名复数 | `EvolutionSnapshot`, `EvolutionChangelog` |
| 异常类 | `PascalCase` + `Error` / `Exception` | `HTTPException`（FastAPI 内置） |
| 服务类 | 无强制类封装，函数式为主 | — |

#### TypeScript

| 类型 | 规范 | 示例 |
|------|------|------|
| 接口 / 类型 | `PascalCase` | `GraphNode`, `GraphEdge`, `ViewLayer` |
| Store 类型 | `PascalCase` + 后缀 | `DomainOverviewItem` |
| Props 类型 | 内联 `defineProps<{}>` 或单独接口 | — |

### 1.3 函数命名

#### Python

| 类型 | 规范 | 示例 |
|------|------|------|
| 公共 API 函数 | `snake_case`，动词开头 | `fetch_position_graph()`, `sync_from_pipeline()` |
| 私有辅助函数 | `_snake_case`（单下划线） | `_safe_properties()`, `_node_id()` |
| 异步函数 | `async def` + `snake_case` | `async def count_positions_neo4j(...)` |
| 生命周期 / 回调 | `snake_case`，语义化 | `lifespan()`, `healthcheck_resources()` |

#### TypeScript / Vue

| 类型 | 规范 | 示例 |
|------|------|------|
| Composable | `use<Feature>()`（camelCase） | `useKPIMetrics()`, `useGraphStore()` |
| Store Actions | `camelCase`，动词开头 | `fetchOverview()`, `goToDomainLayer()` |
| 组件方法 | `camelCase` | `highlightNode()`, `renderCurrentLayer()` |
| 事件处理 | `handle<Event>` 或 `on<Event>` | `handleResize()` |
| 工具函数 | `camelCase` | `cv()`, `loadG6Graph()` |

### 1.4 变量命名

#### Python

| 类型 | 规范 | 示例 |
|------|------|------|
| 常量 | `UPPER_SNAKE_CASE` | `TECH_STACK_KEYWORDS`, `LEVEL_COLORS` |
| 模块级变量 | `snake_case` | `api_router = APIRouter()` |
| 局部变量 | `snake_case`，语义化 | `position_name`, `skill_count` |
| 类型注解变量 | 使用 `Mapped[...]` 声明 | `id: Mapped[uuid.UUID]` |
| 私有变量 | 单下划线前缀 | `_domain_colors` |

#### TypeScript

| 类型 | 规范 | 示例 |
|------|------|------|
| 响应式变量 | `camelCase` + `ref` | `const loading = ref(false)` |
| 计算属性 | `camelCase` + `computed` | `const visibleNodes = computed(...)` |
| 常量 | `UPPER_SNAKE_CASE` | `NODE_TYPE_COLORS`, `KA_FALLBACK_COLORS` |
| 模板引用 | `camelCase` + `Ref` | `const containerRef = ref<HTMLElement>()` |
| 全局状态 | 使用 Pinia `defineStore` | `const graphStore = useGraphStore()` |

---

## 2. 代码风格

### 2.1 Python（Ruff + MyPy）

#### Ruff 配置（`backend/pyproject.toml`）

```toml
[tool.ruff]
line-length = 120
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "N", "UP", "B", "C4"]
ignore = ["E501", "B008"]  # E501: 行长由 formatter 管; B008: FastAPI 依赖注入标准模式
```

#### 启用的规则集

| 规则集 | 说明 |
|--------|------|
| `E` | pycodestyle 错误 |
| `F` | Pyflakes（未使用导入等） |
| `W` | pycodestyle 警告 |
| `I` | isort（导入排序） |
| `N` | pep8-naming（命名规范） |
| `UP` | pyupgrade（Python 升级提示） |
| `B` | flake8-bugbear（潜在 bug） |
| `C4` | flake8-comprehensions（列表/字典推导优化） |

#### MyPy 配置

```toml
[tool.mypy]
python_version = "3.11"
strict = false
ignore_missing_imports = true
warn_return_any = false
warn_unused_ignores = false
```

- `strict = false`：新模块类型检查较宽松，逐步完善
- 特定模块可配置 `ignore_errors = true`（如 `app.core.dashboard.*` 等）

#### Python 代码风格要点

- **行长度**：120 字符（Ruff formatter 管理）
- **导入排序**：Ruff `I` 规则自动排序，标准库 → 第三方 → 本地
- **类型注解**：函数参数和返回值必须标注类型
- **字符串引号**：模块 docstring 使用 `"""`，内部字符串使用单引号或双引号一致
- **注释风格**：
  - 模块级 docstring：三引号，中英文混合，包含业务说明和技术说明
  - 行内注释：`# 业务说明：...` / `# 技术说明：...`
  - 分隔注释：`# ── 标题 ──`

### 2.2 TypeScript / Vue（ESLint + TypeScript）

#### ESLint 配置（来自 `frontend/package.json`）

```json
{
  "lint": "eslint . --ext .vue,.ts,.tsx --max-warnings 50",
  "lint:fix": "eslint . --ext .vue,.ts,.tsx --fix"
}
```

#### 依赖的 ESLint 插件

| 包 | 版本 | 用途 |
|----|------|------|
| `eslint` | ^8.57.0 | 核心 |
| `@typescript-eslint/eslint-plugin` | ^7.3.0 | TypeScript 规则 |
| `@typescript-eslint/parser` | ^7.3.0 | TypeScript 解析 |
| `eslint-plugin-vue` | ^9.23.0 | Vue 规则 |
| `vue-eslint-parser` | ^9.4.0 | Vue 单文件解析 |

#### TypeScript / Vue 代码风格要点

- **行长度**：无显式限制，建议 120 字符
- **缩进**：2 空格（Vue SFC 中 `<script>` 和 `<style>` 块）
- **分号**：使用分号（JavaScript 标准）
- **引号**：单引号（`'...'`）
- **类型注解**：
  - Props 使用 `defineProps<{}>()` 显式声明
  - Emits 使用 `defineEmits<{}>()` 显式声明
  - 模板引用使用 `ref<HTMLElement>()`
- **Vue SFC 结构**：
  ```vue
  <script setup lang="ts">
  // 导入
  // 类型定义
  // Props / Emits
  // 状态
  // 计算属性
  // 方法
  // 生命周期
  </script>

  <template>
  <!-- 模板 -->
  </template>

  <style scoped>
  /* 样式 */
  </style>
  ```
- **注释风格**：
  - 文件头部 JSDoc 注释说明组件职责
  - 使用 `// ── 标题 ──` 分隔代码区块
  - 行内注释：`// 业务说明：...` / `// 技术说明：...`

---

## 3. 导入规范

### 3.1 Python

#### 导入排序（Ruff `I` 规则自动处理）

```python
from __future__ import annotations  # 第一行（如需要）

import asyncio          # 标准库
import uuid
from datetime import UTC, datetime

from fastapi import FastAPI, APIRouter    # 第三方库
from pydantic import BaseModel, Field
from sqlalchemy import DateTime, Float

from app.models import Base               # 本地模块
from app.services.graph_service import fetch_position_graph
from app.dependencies import get_neo4j_driver
```

#### 导入规范要点

- **绝对导入**：优先使用绝对导入（`from app.models import Base`）
- **相对导入**：仅在模块内部使用相对导入（如 `from . import ...`）
- **避免循环导入**：通过延迟导入（`from app.core.pipeline.cron_scheduler import cron_scanner_loop` 放在函数内部）解决
- **类型检查导入**：使用 `from __future__ import annotations` 支持 PEP 563

### 3.2 TypeScript / Vue

#### 导入排序

```typescript
// 1. Vue / 框架核心
import { ref, onMounted, watch } from 'vue'
import { defineStore } from 'pinia'

// 2. 第三方库
import axios, { type AxiosError } from 'axios'
import { ElMessage, ElNotification } from 'element-plus'

// 3. 本地模块（使用 @/ 别名）
import request from '@/api/request'
import { useGraphStore } from '@/stores/graph'
import { NODE_TYPE_COLORS } from '@/utils/graphColors'
```

#### 导入规范要点

- **别名导入**：使用 `@/` 别名引用本地模块
- **类型导入**：使用 `import type { ... }` 或 `type` 关键字明确类型导入
- **按需导入**：Element Plus 组件按需导入
- **避免 `*` 导入**：除非必要，避免使用 `import * as ...`

---

## 4. 错误处理模式

### 4.1 Python（FastAPI）

#### 标准模式

```python
from fastapi import HTTPException

# 路由层抛出 HTTP 异常
async def get_position_skills(...):
    graph = await fetch_position_graph(driver, position_id, depth)
    if graph["position"] is None:
        raise HTTPException(status_code=404, detail=f"Position '{position_id}' not found")
    return PositionSkillDetailResponse(...)
```

#### 服务层降级模式

```python
async def count_positions_neo4j(driver: Any) -> int:
    if driver is None:
        return 0  # 服务降级，不中断
    try:
        async with driver.session() as session:
            result = await session.run("MATCH (p:Position) RETURN count(p) AS cnt")
            record = await result.single()
            return int(record["cnt"]) if record else 0
    except Exception:
        return 0  # 异常降级
```

#### 错误处理要点

- **路由层**：使用 `HTTPException` 返回标准 HTTP 错误码
- **服务层**：异常时返回默认值（如 `0`），避免级联故障
- **日志记录**：使用 `loguru` 记录错误日志
- **重试机制**：使用 `tenacity` 库实现自动重试

### 4.2 TypeScript / Vue

#### Axios 拦截器模式

```typescript
// 请求拦截器：显示 loading
request.interceptors.request.use(
  (config) => { showLoading(); return config; },
  (error) => { hideLoading(); return Promise.reject(error); }
);

// 响应拦截器：错误友好提示
request.interceptors.response.use(
  (resp) => { hideLoading(); return resp.data; },
  (error: AxiosError) => {
    hideLoading();
    const status = error.response?.status;
    let message = '未知错误，请稍后重试';
    if (!error.response) {
      message = navigator.onLine ? '无法连接到服务器' : '网络连接已断开';
    } else if (status) {
      message = ERROR_MESSAGES[status] ?? `请求失败 (${status})`;
    }
    if (status !== 401) {
      ElMessage.error({ message, duration: 4000, showClose: true });
    }
    return Promise.reject(error);
  }
);
```

#### 错误处理要点

- **HTTP 状态码映射**：定义 `ERROR_MESSAGES` 常量，将状态码映射为中文友好提示
- **网络状态监听**：监听 `online` / `offline` 事件
- **401 特殊处理**：不弹窗提示，避免重复弹窗
- **Store 层**：使用 `try...catch...finally` 包裹 API 调用，设置 `loading` 状态

---

## 5. 注释规范

### 5.1 Python

#### 模块级 Docstring

```python
"""FastAPI 应用入口。

业务说明：
    本模块是 StarMap 后端应用的入口文件，负责：
    1. 创建 FastAPI 应用实例；
    2. 配置 CORS 中间件；
    3. 注册 API 路由；
    4. 管理应用生命周期（启动/关闭）。
"""
```

#### 类级 Docstring

```python
class EvolutionSnapshot(Base):
    """业务说明：职位技能快照表。

    记录特定时间点某个职位的完整技能画像...
    """
```

#### 行内注释

```python
# 业务说明：统计 Neo4j 图谱中职位节点的总数量
# 技术说明：当 driver 未初始化或查询异常时返回 0，保证服务降级不中断
```

#### 注释规范要点

- **双语注释**：模块/类/函数级注释使用中文，技术细节可夹杂英文术语
- **业务说明 vs 技术说明**：明确区分业务意图和技术实现
- **分隔线**：使用 `# ── 标题 ──` 分隔代码区块

### 5.2 TypeScript / Vue

#### 文件头部 JSDoc

```typescript
/**
 * Graph2D — G6 v5 force-directed graph visualization (2D counterpart to Graph3D).
 *
 * Owns all G6 lifecycle: dynamic import, instance creation, three-layer rendering,
 * layout switching, node highlighting, and resize handling.
 */
```

#### 行内注释

```typescript
// 业务说明：定义组件对外暴露的属性接口
// 技术说明：使用 shallowRef 持有 G6 实例，避免 Vue 深度响应式代理
```

#### 注释规范要点

- **JSDoc 格式**：文件头部使用 JSDoc 说明组件/模块职责
- **区块分隔**：使用 `// ── 标题 ──` 分隔代码区块
- **双语注释**：与 Python 一致，业务说明 + 技术说明分离

---

## 6. Git 提交规范

### 6.1 提交消息格式

项目采用 **Conventional Commits** 风格，格式如下：

```
<type>(<scope>): <subject>

<body>
```

### 6.2 类型（Type）

| 类型 | 说明 | 示例 |
|------|------|------|
| `feat` | 新功能 | `feat(backend): add Dashboard module` |
| `fix` | Bug 修复 | `fix(frontend): resolve lint errors` |
| `docs` | 文档更新 | `docs: update CHANGELOG to v1.2.0` |
| `test` | 测试相关 | `test(frontend): add E2E test specs` |
| `chore` | 构建/工具/杂项 | `chore: update .gitignore` |
| `perf` | 性能优化 | `perf(frontend): code-split vendor chunks` |
| `refactor` | 重构 | `refactor: extract graph rendering logic` |
| `style` | 代码格式（不影响功能） | `style: format with ruff` |

### 6.3 范围（Scope）

| 范围 | 说明 |
|------|------|
| `backend` | 后端代码 |
| `frontend` | 前端代码 |
| `crawler` | 爬虫模块 |
| `contracts` | API 契约 |
| `scripts` | 脚本工具 |
| `admin` | 管理后台 |
| `*` 或无 | 全局变更 |

### 6.4 提交消息示例

```
feat(backend): add Pipeline module — ETL orchestration, data fusion, quality monitor

fix(frontend): resolve lint errors — remove unused import, suppress warning

docs(contracts): update CHANGELOG to v1.2.0 — 5 new API modules, 14 new schemas

test(frontend): add E2E test specs — functional interaction, panoramic graph

perf(frontend): code-split vendor chunks and lazy-load @antv/g6
```

### 6.5 提交规范要点

- **英文类型 + 中文描述**：类型使用英文，描述使用中文
- **详细描述**：在 body 中补充变更细节和影响范围
- **关联 Issue**：如有相关 Issue，在消息中引用（如 `#53`）
- **CI 门禁**：提交前确保 `ruff check`, `mypy`, `pytest`, `eslint` 均通过

---

## 7. CI / CD 规范

### 7.1 CI 流水线（`.github/workflows/ci.yml`）

| 阶段 | 说明 |
|------|------|
| **契约校验** | 最先执行，校验 `starmap-contracts/openapi.yaml` |
| **后端 lint** | `ruff check .` + `mypy app` + `pytest`（覆盖率门禁 60%） |
| **前端 lint** | `eslint` + `vue-tsc --noEmit` + `npm run build` |
| **爬虫编译** | `python -m compileall` + `pytest`（跳过集成测试） |
| **Docker 冒烟** | 手动/定时触发，全栈构建并健康检查 |

### 7.2 门禁规则

- **Ruff**：`E`, `F`, `W`, `I`, `N`, `UP`, `B`, `C4` 规则集
- **MyPy**：`python_version = "3.11"`，`strict = false`
- **Pytest**：覆盖率门禁 **60%**，`--cov-fail-under=60`
- **ESLint**：`--max-warnings 50`
- **TypeScript**：`vue-tsc --noEmit` 无类型错误

---

## 8. 目录结构规范

### 8.1 后端（`backend/app/`）

```
backend/app/
├── api/v1/           # API 路由（按业务模块划分）
├── core/             # 核心业务逻辑（pipeline, extraction, dashboard 等）
├── models/           # SQLAlchemy / Pydantic 模型
├── services/         # 服务层（业务逻辑封装）
├── tasks/            # Celery 异步任务
├── utils/            # 工具函数
├── config.py         # 配置管理
├── dependencies.py   # FastAPI 依赖注入
└── main.py           # 应用入口
```

### 8.2 前端（`frontend/src/`）

```
frontend/src/
├── api/              # API 请求封装
├── components/       # Vue 组件（PascalCase）
├── composables/      # Vue Composables（useXxx.ts）
├── layouts/          # 布局组件
├── pages/            # 页面组件
├── router/           # Vue Router 配置
├── stores/           # Pinia Store（<feature>.ts）
├── styles/           # 全局样式
└── utils/            # 工具函数
```

---

## 9. 关键约定总结

| 维度 | Python | TypeScript / Vue |
|------|--------|------------------|
| **文件命名** | `snake_case.py` | `PascalCase.vue`, `camelCase.ts` |
| **类命名** | `PascalCase` | `PascalCase`（接口/类型） |
| **函数命名** | `snake_case` | `camelCase` |
| **变量命名** | `snake_case` | `camelCase` |
| **常量** | `UPPER_SNAKE_CASE` | `UPPER_SNAKE_CASE` |
| **私有** | `_prefix` | `_prefix`（约定） |
| **注释语言** | 中文（业务+技术） | 中文（业务+技术） |
| **行长度** | 120 | 120（建议） |
| **导入排序** | Ruff `I` 规则 | 标准库 → 第三方 → 本地 |
| **类型检查** | MyPy | TypeScript (`vue-tsc`) |
