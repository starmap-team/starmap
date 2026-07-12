# 异步任务 - Tasks 规范

## 1. 模块概述

Tasks（异步任务）模块是 StarMap 后端的 Celery 异步任务层，负责处理耗时操作（如批量 JD 抽取、图构建、演化分析等）的异步执行。该模块位于 `backend/app/tasks/`，包含 2 个核心文件，共约 596 行代码。

**核心目标**：
- 提供 Celery 异步任务定义和调度
- 处理批量 JD 抽取、图构建、演化分析等耗时操作
- 支持任务重试、超时、取消
- 与流水线编排器集成

**在系统中的位置**：位于 `backend/app/tasks/`，被 `core/pipeline/executor.py` 和 `api/v1/pipeline/routes.py` 调用，依赖 Redis 和 PostgreSQL。

---

## 2. 文件清单

| 文件路径 | 行数 | 职责 | 主要导出 |
|---------|------|------|---------|
| `backend/app/tasks/celery_app.py` | 303 | Celery 应用定义：任务注册、配置、调度 | `celery_app`, `batch_extract_jd`, `build_graph_from_extractions`, `analyze_evolution_trends`, `execute_pipeline_stage`, `advance_pipeline_task`, `scheduled_pipeline_run`, `sweep_orphan_runs` |
| `backend/app/tasks/stage3_services.py` | 293 | Stage3 服务：批量抽取、图构建、演化分析的具体实现 | `run_batch_extract_jd`, `run_build_graph_from_extractions`, `run_analyze_evolution_trends` |

---

## 3. 架构设计

### 3.1 模块内部结构

```
tasks/
├── celery_app.py      ← Celery 应用定义
└── stage3_services.py ← Stage3 服务实现
```

### 3.2 数据流向

```
HTTP POST /api/v1/pipeline/trigger
    │
    ▼
┌─────────────────────────┐
│ core/pipeline/orchestrator.py │
└─────────────────────────┘
    │
    ▼
┌─────────────────────────┐
│ core/pipeline/executor.py    │
└─────────────────────────┘
    │
    ▼
┌─────────────────────────┐
│ tasks/celery_app.py          │
│ ├─ batch_extract_jd          │
│ ├─ build_graph_from_extractions│
│ ├─ analyze_evolution_trends  │
│ ├─ execute_pipeline_stage    │
│ └─ sweep_orphan_runs         │
└─────────────────────────┘
    │
    ▼
Redis (Broker) → Celery Worker → PostgreSQL/Neo4j
```

### 3.3 任务类型

| 任务 | 用途 | 重试策略 |
|------|------|---------|
| `batch_extract_jd` | 批量 JD 抽取 | max_retries=3, delay=10s |
| `build_graph_from_extractions` | 从抽取结果构建图 | max_retries=3, delay=10s |
| `analyze_evolution_trends` | 演化趋势分析 | max_retries=3, delay=10s |
| `execute_pipeline_stage` | 执行流水线阶段 | max_retries=3, delay=10s |
| `advance_pipeline_task` | 推进流水线 | 不重试 |
| `scheduled_pipeline_run` | 定时流水线 | 不重试 |
| `sweep_orphan_runs` | 清理孤儿任务 | 不重试 |

---

## 4. 接口规范

### 4.1 主要任务定义

```python
# celery_app.py
@celery_app.task(bind=True, max_retries=3, default_retry_delay=10)
def batch_extract_jd(self, jd_text: str, options: dict[str, Any] | None = None) -> dict[str, Any]:
    """批量 JD 抽取。"""

@celery_app.task(bind=True, max_retries=3, default_retry_delay=10)
def build_graph_from_extractions(self, limit: int = 100) -> dict[str, Any]:
    """从抽取结果构建图。"""

@celery_app.task(bind=True, max_retries=3, default_retry_delay=10)
def analyze_evolution_trends(self, days: int = 90) -> dict[str, Any]:
    """演化趋势分析。"""

@celery_app.task(bind=True, max_retries=settings.pipeline_retry_max, default_retry_delay=settings.pipeline_retry_backoff)
def execute_pipeline_stage(self, run_id: str, stage_name: str) -> dict[str, Any]:
    """执行流水线阶段。"""

@celery_app.task
def advance_pipeline_task(run_id: str) -> None:
    """推进流水线。"""

@celery_app.task
def scheduled_pipeline_run(schedule_id: str) -> None:
    """定时流水线。"""

@celery_app.task
def sweep_orphan_runs() -> dict[str, Any]:
    """清理孤儿任务。"""
```

### 4.2 Celery 配置

```python
# celery_app.py
celery_app = Celery(
    "starmap",
    broker=settings.redis_uri,
    backend=settings.redis_uri,
)
celery_app.conf.update(
    task_default_queue="starmap",
    task_track_started=True,
    timezone="Asia/Shanghai",
    enable_utc=False,
    task_time_limit=settings.pipeline_stage_timeout,           # 单阶段超时
    task_soft_time_limit=settings.pipeline_stage_timeout - 30,  # 软超时
)
```

---

## 5. 编码规范（本模块特有）

### 5.1 任务定义规范

```python
# 每个任务必须包含：
# 1. bind=True（用于 self.retry）
# 2. max_retries
# 3. default_retry_delay
# 4. 异常处理（try/except）
# 5. 日志记录

@celery_app.task(bind=True, max_retries=3, default_retry_delay=10)
def example_task(self, *args, **kwargs):
    try:
        # 业务逻辑
        return {"status": "completed"}
    except Exception as exc:
        logger.exception("Task failed")
        raise self.retry(exc=exc) from exc
```

### 5.2 反模式

| 反模式 | 说明 | 正确做法 |
|--------|------|---------|
| 任务中直接操作数据库 | 绕过 ORM | 使用 async_sessionmaker |
| 忽略异常处理 | 任务失败无重试 | 使用 try/except + self.retry |
| 硬编码超时 | 无法调整 | 使用 settings 配置 |
| 任务中同步调用 | 阻塞 | 使用 run_async 桥接 |

---

## 6. 测试规范

### 6.1 对应测试文件

| 被测模块 | 测试文件 | 行数 | 测试类型 |
|---------|---------|------|---------|
| `celery_app.py` | `tests/unit/test_celery_stage3_tasks.py` | 48 | 单元测试 |

### 6.2 覆盖率要求

- `celery_app.py`：任务定义 >= 60%
- `stage3_services.py`：服务实现 >= 60%

### 6.3 Mock 策略

```python
# 测试 Celery 任务
def test_batch_extract_jd():
    # mock run_batch_extract_jd
    # 验证任务执行正确
```

---

## 7. 变更管理

### 7.1 修改检查清单

修改 Tasks 模块时：

- [ ] 是否新增任务？是 → 注册到 Celery
- [ ] 是否修改重试策略？是 → 确认不影响现有任务
- [ ] 是否修改超时配置？是 → 更新 `config.py`

### 7.2 契约影响

| 变更 | 影响 |
|------|------|
| 新增任务 | 影响 Celery 调度 |
| 修改重试策略 | 影响任务执行 |
| 修改超时配置 | 影响任务执行时间 |

### 7.3 迁移要求

- 新增任务时，必须注册到 `celery_app`
- 修改重试策略时，必须评估对现有任务的影响
- 修改超时配置时，必须同步更新 `config.py` 和 `.env.example`
