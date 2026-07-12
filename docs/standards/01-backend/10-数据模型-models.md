# 数据模型 - Models 规范

## 1. 模块概述

Models（数据模型）模块是 StarMap 后端的数据持久化层，使用 SQLAlchemy async ORM 定义 PostgreSQL 数据库表结构。该模块位于 `backend/app/models/`，包含 5 个核心文件，共约 1279 行代码。

**核心目标**：
- 定义所有 PostgreSQL 数据库表结构
- 提供 ORM 映射，支持异步操作
- 支持 Alembic 数据库迁移
- 统一的数据模型基类

**在系统中的位置**：位于 `backend/app/models/`，被 `services/`、`core/`、`api/v1/` 和 `db/` 层引用。

---

## 2. 文件清单

| 文件路径 | 行数 | 职责 | 主要导出 |
|---------|------|------|---------|
| `backend/app/models/__init__.py` | 59 | 模型包聚合，导入所有模型 | `Base`, `DataSourceRecord`, `EvolutionChangelog`, `EvolutionPath`, `EvolutionSnapshot`, `ExtractionEvaluationRecord`, `JDExtractionRecord`, `LearningPlan`, `LearningProgress`, `LoopResultRecord`, `PipelineRun`, `PipelineSchedule`, `PositionRecord`, `PositionSkillRelation`, `RawJDRecord`, `SkillAliasRecord`, `SkillPrerequisite`, `SkillRecord`, `SkillTimeseries`, `SystemConfig` |
| `backend/app/models/extraction_models.py` | 446 | 抽取模型：JD 抽取记录、原始 JD、技能记录、别名记录 | `JDExtractionRecord`, `RawJDRecord`, `SkillRecord`, `SkillAliasRecord`, `PositionRecord`, `PositionSkillRelation`, `ExtractionEvaluationRecord`, `SystemConfig` |
| `backend/app/models/evolution_models.py` | 308 | 演化模型：快照、变更日志、演化路径、时间序列 | `EvolutionSnapshot`, `EvolutionChangelog`, `EvolutionPath`, `SkillTimeseries` |
| `backend/app/models/learning_models.py` | 205 | 学习模型：学习计划、进度、前置条件 | `LearningPlan`, `LearningProgress`, `SkillPrerequisite` |
| `backend/app/models/pipeline_models.py` | 261 | 流水线模型：运行记录、数据源、调度、闭环结果 | `PipelineRun`, `DataSourceRecord`, `PipelineSchedule`, `LoopResultRecord` |

---

## 3. 架构设计

### 3.1 模块内部结构

```
models/
├── __init__.py           ← 模型包聚合
├── extraction_models.py  ← 抽取相关模型
├── evolution_models.py   ← 演化相关模型
├── learning_models.py    ← 学习相关模型
└── pipeline_models.py    ← 流水线相关模型
```

### 3.2 模型关系图

```
┌─────────────────────────────────────────────────────────┐
│  extraction_models.py                                    │
│  ├─ JDExtractionRecord ──► RawJDRecord                  │
│  ├─ SkillRecord ◄── SkillAliasRecord                    │
│  ├─ PositionRecord ◄── PositionSkillRelation            │
│  └─ ExtractionEvaluationRecord                          │
├─────────────────────────────────────────────────────────┤
│  evolution_models.py                                     │
│  ├─ EvolutionSnapshot ──► EvolutionChangelog            │
│  ├─ EvolutionPath                                       │
│  └─ SkillTimeseries                                     │
├─────────────────────────────────────────────────────────┤
│  learning_models.py                                      │
│  ├─ LearningPlan ──► LearningProgress                   │
│  └─ SkillPrerequisite                                   │
├─────────────────────────────────────────────────────────┤
│  pipeline_models.py                                     │
│  ├─ PipelineRun ──► DataSourceRecord                    │
│  ├─ PipelineSchedule                                    │
│  └─ LoopResultRecord                                    │
└─────────────────────────────────────────────────────────┘
```

### 3.3 数据流向

```
HTTP Request
    │
    ▼
┌─────────────────────────┐
│ api/v1/*.py              │
└─────────────────────────┘
    │
    ▼
┌─────────────────────────┐
│ services/ 或 core/        │
└─────────────────────────┘
    │
    ▼
┌─────────────────────────┐
│ models/*.py              │
│ ├─ extraction_models.py  │
│ ├─ evolution_models.py │
│ ├─ learning_models.py   │
│ └─ pipeline_models.py   │
└─────────────────────────┘
    │
    ▼
PostgreSQL
```

---

## 4. 接口规范

### 4.1 基类定义

```python
# models/__init__.py
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    """所有 ORM 模型的基类。"""
```

### 4.2 主要模型定义

```python
# extraction_models.py
class JDExtractionRecord(Base):
    __tablename__ = "jd_extraction_records"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    jd_content: Mapped[str] = mapped_column(Text, nullable=False)
    job_title: Mapped[str] = mapped_column(String(255), nullable=False)
    extracted_skills: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    experience_years: Mapped[int | None] = mapped_column(Integer, nullable=True)
    education: Mapped[str | None] = mapped_column(String(100), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    hallucination_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")

# pipeline_models.py
class PipelineRun(Base):
    __tablename__ = "pipeline_runs"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_type: Mapped[str] = mapped_column(String(20), nullable=False, default="full")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    stages: Mapped[dict | list | None] = mapped_column(JSON, nullable=True, default=list)
    total_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    new_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    quality_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    error_log: Mapped[str | None] = mapped_column(Text, nullable=True)
    selected_stages: Mapped[list | None] = mapped_column(JSON, nullable=True)

# evolution_models.py
class EvolutionSnapshot(Base):
    __tablename__ = "evolution_snapshots"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    position_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    snapshot_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    required_skills: Mapped[dict] = mapped_column(JSON, nullable=False, default=list)
    preferred_skills: Mapped[dict] = mapped_column(JSON, nullable=False, default=list)
    source_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    trust_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

# learning_models.py
class LearningPlan(Base):
    __tablename__ = "learning_plans"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True, default="anonymous")
    position: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    skills: Mapped[dict] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    match_score_at_creation: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    estimated_hours: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
```

---

## 5. 编码规范（本模块特有）

### 5.1 模型定义规范

```python
# 每个模型必须包含：
# 1. 业务说明 docstring
# 2. 技术说明 comment
# 3. 类型注解（Mapped[T]）
# 4. 默认值
# 5. 索引（查询频繁的字段）

class ExampleModel(Base):
    """业务说明：..."""
    __tablename__ = "example_models"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
```

### 5.2 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| 表名 | `snake_case`，复数 | `jd_extraction_records`, `pipeline_runs` |
| 列名 | `snake_case` | `created_at`, `match_score` |
| 模型类名 | `PascalCase`，单数 | `JDExtractionRecord`, `PipelineRun` |
| 索引名 | `idx_表名_列名` | `idx_evolution_snapshots_position_name` |

### 5.3 反模式

| 反模式 | 说明 | 正确做法 |
|--------|------|---------|
| 直接修改表结构 | 数据丢失风险 | 使用 Alembic 迁移 |
| 缺少类型注解 | 类型不安全 | 使用 `Mapped[T]` |
| 缺少默认值 | 插入失败 | 设置合理的默认值 |
| 缺少索引 | 查询慢 | 为查询频繁的字段添加索引 |

---

## 6. 测试规范

### 6.1 对应测试文件

| 被测模块 | 测试文件 | 行数 | 测试类型 |
|---------|---------|------|---------|
| `models/` 整体 | `tests/unit/test_models.py` | 137 | 单元测试 |
| `models/` 表示 | `tests/unit/test_model_repr.py` | 114 | 单元测试 |

### 6.2 覆盖率要求

- 所有模型类 >= 60%
- 重点关注：默认值、类型注解、索引定义

### 6.3 Mock 策略

```python
# 测试模型
def test_jd_extraction_record_defaults():
    record = JDExtractionRecord()
    assert record.status == "pending"
    assert record.confidence == 0.0
```

---

## 7. 变更管理

### 7.1 修改检查清单

修改 Models 模块时：

- [ ] 是否新增模型？是 → 生成 Alembic 迁移
- [ ] 是否修改表结构？是 → 生成 Alembic 迁移
- [ ] 是否修改字段类型？是 → 生成 Alembic 迁移
- [ ] 是否新增索引？是 → 生成 Alembic 迁移

### 7.2 契约影响

| 变更 | 影响 |
|------|------|
| 新增模型 | 影响数据库结构 |
| 修改字段 | 影响现有数据 |
| 删除字段 | 可能导致数据丢失 |
| 新增索引 | 影响写入性能，提升查询性能 |

### 7.3 迁移要求

- 任何模型变更必须通过 Alembic 迁移
- 迁移文件命名：`XXX_描述.py`
- 迁移前必须备份数据
- 迁移后必须验证数据完整性
