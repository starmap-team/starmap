# 业务核心 - Pipeline 规范

## 1. 模块概述

Pipeline（数据流水线）模块是 StarMap 的核心业务层之一，负责管理数据抽取、去重、清洗、导入、图同步等 ETL 流程的调度和执行。该模块位于 `backend/app/core/pipeline/`，包含 11 个核心文件，共约 3040 行代码。

**核心目标**：
- 管理 ETL 数据流水线的完整生命周期
- 支持 DAG（有向无环图）依赖调度和阶段执行
- 提供 CRON 定时调度功能
- 支持流水线取消、重试、状态监控
- 数据质量监控和告警

**在系统中的位置**：位于 `backend/app/core/pipeline/`，被 `api/v1/pipeline/routes.py` 和 `tasks/celery_app.py` 调用，依赖 PostgreSQL、Redis、Neo4j。

---

## 2. 文件清单

| 文件路径 | 行数 | 职责 | 主要导出 |
|---------|------|------|---------|
| `backend/app/core/pipeline/__init__.py` | 0 | 包声明 | 无 |
| `backend/app/core/pipeline/bootstrap.py` | 50 | 流水线启动引导：环境检测、自动触发 | `schedule_bootstrap_if_enabled` |
| `backend/app/core/pipeline/cron_scheduler.py` | 131 | CRON 调度器：定时任务扫描、触发 | `cron_scanner_loop`, `compute_next_cron` |
| `backend/app/core/pipeline/data_fusion.py` | 243 | 数据融合：多源数据合并、冲突解决 | `fuse_data_sources`, `DataFusionResult` |
| `backend/app/core/pipeline/executor.py` | 681 | 流水线执行器：DAG 执行循环、Celery 桥接 | `trigger_and_start`, `advance_pipeline`, `STAGE_EXECUTORS` |
| `backend/app/core/pipeline/loop_orchestrator.py` | 758 | 闭环验证编排器：验证循环协调 | `LoopOrchestrator`, `ValidationLoop` |
| `backend/app/core/pipeline/orchestrator.py` | 467 | 流水线编排器：DAG 状态管理、阶段调度 | `create_run`, `update_stage_status`, `RunStatus`, `StageStatus`, `StageName` |
| `backend/app/core/pipeline/quality_monitor.py` | 309 | 质量监控：数据质量指标、告警 | `QualityMonitor`, `QualityMetrics` |
| `backend/app/core/pipeline/simhash.py` | 90 | SimHash 去重：文本相似度去重 | `simhash`, `hamming_distance`, `are_similar` |
| `backend/app/core/pipeline/source_authority.py` | 91 | 来源权威度：数据源评分、权威度计算 | `calculate_authority`, `SourceAuthority` |
| `backend/app/core/pipeline/status_aggregator.py` | 220 | 状态聚合器：多阶段状态汇总、报告生成 | `aggregate_status`, `StatusReport` |

---

## 3. 架构设计

### 3.1 模块内部结构

```
core/pipeline/
├── __init__.py              ← 包声明
├── bootstrap.py             ← 启动引导
├── cron_scheduler.py        ← CRON 调度器
├── data_fusion.py           ← 数据融合
├── executor.py              ← 执行器（DAG 执行循环）
├── loop_orchestrator.py     ← 闭环验证编排器
├── orchestrator.py          ← 编排器（DAG 状态管理）
├── quality_monitor.py       ← 质量监控
├── simhash.py               ← SimHash 去重
├── source_authority.py      ← 来源权威度
└── status_aggregator.py     ← 状态聚合器
```

### 3.2 DAG 依赖关系

```
crawl (根节点，无依赖)
  │
  ├──► dedup ──┐
  │             │
  ├──► clean ───┤
  │             ▼
  │           import
  │             │
  │             ▼
  │         graph_sync
  │
  └──► (可选阶段)
```

```python
# orchestrator.py
STAGE_DEPS: dict[str, list[str]] = {
    StageName.CRAWL.value: [],
    StageName.DEDUP.value: ["crawl"],
    StageName.CLEAN.value: ["crawl"],
    StageName.IMPORT.value: ["dedup", "clean"],
    StageName.GRAPH_SYNC.value: ["import"],
}
```

### 3.3 数据流向

```
HTTP POST /api/v1/pipeline/trigger
    │
    ▼
┌─────────────────────────┐
│ api/v1/pipeline/routes.py│
└─────────────────────────┘
    │
    ▼
┌─────────────────────────┐
│ core/pipeline/orchestrator.py │
│ ├─ create_run()              │
│ └─ trigger_and_start()       │
└─────────────────────────┘
    │
    ▼
┌─────────────────────────┐
│ core/pipeline/executor.py    │
│ ├─ Celery task dispatch      │
│ └─ advance_pipeline()        │
└─────────────────────────┘
    │
    ▼
┌─────────────────────────┐
│ tasks/celery_app.py          │
│ ├─ execute_pipeline_stage()  │
│ └─ sweep_orphan_runs()       │
└─────────────────────────┘
    │
    ▼
PostgreSQL + Redis + Neo4j
```

---

## 4. 接口规范

### 4.1 主要类与函数签名

```python
# orchestrator.py
class StageName(StrEnum):
    CRAWL = "crawl"
    DEDUP = "dedup"
    CLEAN = "clean"
    IMPORT = "import"
    GRAPH_SYNC = "graph_sync"

class StageStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

class RunStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

async def create_run(
    session: AsyncSession,
    run_type: str,
    selected_stages: list[str] | None = None,
) -> PipelineRun:
    """创建新的流水线运行。"""

async def update_stage_status(
    session: AsyncSession,
    run_id: uuid.UUID,
    stage_name: str,
    status: str,
    **kwargs,
) -> None:
    """更新阶段状态。"""

# executor.py
async def trigger_and_start(
    run_type: str = "full",
    selected_stages: list[str] | None = None,
) -> dict[str, Any]:
    """触发并启动流水线。"""

async def advance_pipeline(run_id: uuid.UUID) -> None:
    """推进流水线到下一阶段。"""

# cron_scheduler.py
async def cron_scanner_loop(interval_seconds: int = 60) -> None:
    """CRON 扫描循环。"""

def compute_next_cron(cron_expression: str, last_run: datetime) -> datetime:
    """计算下次执行时间。"""
```

### 4.2 流水线状态机

```
PENDING → RUNNING → COMPLETED
   │         │
   │         ▼
   │       FAILED
   │         │
   │         ▼
   │       RETRY (max 3)
   │         │
   └─────────┘
```

---

## 5. 编码规范（本模块特有）

### 5.1 阶段超时配置

```python
# config.py
settings.pipeline_stage_timeout = 1800       # 单阶段超时（秒），默认 30 分钟
settings.pipeline_worker_concurrency = 2     # 工作并发数
settings.pipeline_crawl_concurrency = 5      # 爬取并发数
settings.pipeline_retry_max = 3              # 最大重试次数
settings.pipeline_retry_backoff = 10         # 指数退避基数（秒）
```

### 5.2 SimHash 去重

```python
# simhash.py
def simhash(text: str, hashbits: int = 64) -> int:
    """计算文本的 SimHash 值。"""

def hamming_distance(hash1: int, hash2: int) -> int:
    """计算两个 SimHash 值的汉明距离。"""

def are_similar(text1: str, text2: str, threshold: int = 3) -> bool:
    """判断两个文本是否相似。"""
```

### 5.3 反模式

| 反模式 | 说明 | 正确做法 |
|--------|------|---------|
| 跳过 DAG 依赖检查 | 阶段执行顺序错误 | 使用 `STAGE_DEPS` |
| 硬编码超时时间 | 无法调整 | 使用 `settings` 配置 |
| 忽略阶段失败 | 数据不一致 | 使用重试机制 |
| 多处实现 simhash | 维护困难 | 统一使用 `simhash.py` |

---

## 6. 测试规范

### 6.1 对应测试文件

| 被测模块 | 测试文件 | 行数 | 测试类型 |
|---------|---------|------|---------|
| `pipeline/` 整体 | `tests/unit/test_pipeline.py` | 264 | 单元测试 |
| `pipeline/routes.py` | `tests/unit/test_pipeline_api.py` | 869 | 单元测试 |
| `bootstrap.py` | `tests/unit/test_pipeline_bootstrap.py` | 75 | 单元测试 |
| `orchestrator.py` | `tests/unit/test_pipeline_orchestrator.py` | 185 | 单元测试 |
| `cron_scheduler.py` | `tests/unit/test_cron_scheduler.py` | 219 | 单元测试 |
| `quality_monitor.py` | `tests/unit/test_quality_monitor.py` | 384 | 单元测试 |
| `status_aggregator.py` | `tests/unit/test_status_aggregator.py` | 346 | 单元测试 |
| `loop_orchestrator.py` | `tests/unit/test_loop_orchestrator.py` | 294 | 单元测试 |
| `loop_orchestrator.py` (覆盖) | `tests/unit/test_loop_orchestrator_coverage.py` | 573 | 单元测试 |

### 6.2 覆盖率要求

- `orchestrator.py`：DAG 调度 >= 60%
- `executor.py`：执行循环 >= 60%
- `cron_scheduler.py`：CRON 解析 >= 60%
- `quality_monitor.py`：质量监控 >= 60%
- `simhash.py`：去重算法 >= 60%

### 6.3 Mock 策略

```python
# 测试流水线
def test_create_run():
    # mock AsyncSession
    # 验证 PipelineRun 创建正确

def test_advance_pipeline():
    # mock Celery task
    # 验证阶段推进逻辑
```

---

## 7. 变更管理

### 7.1 修改检查清单

修改 Pipeline 模块时：

- [ ] 是否修改 DAG 依赖？是 → 确认不会引入循环依赖
- [ ] 是否修改阶段逻辑？是 → 确认状态机正确
- [ ] 是否修改超时配置？是 → 更新 `config.py`
- [ ] 是否修改 CRON 解析？是 → 验证解析正确性
- [ ] 是否修改质量监控？是 → 确认告警阈值

### 7.2 契约影响

| 变更 | 影响 |
|------|------|
| 修改 DAG 依赖 | 影响流水线执行顺序 |
| 修改阶段逻辑 | 影响数据处理流程 |
| 修改超时配置 | 影响任务执行时间 |
| 修改 CRON 解析 | 影响定时任务触发 |

### 7.3 迁移要求

- 修改 DAG 依赖时，必须确认不会引入循环依赖
- 修改阶段逻辑时，必须评估对现有流水线的影响
- 修改超时配置时，必须同步更新 `config.py` 和 `.env.example`
- `app/pipeline/`（旧版）与 `app/core/pipeline/`（新版）并存期间，旧版禁止新增功能
