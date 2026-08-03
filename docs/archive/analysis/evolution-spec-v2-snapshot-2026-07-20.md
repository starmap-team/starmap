> **归档说明（2026-07-28）**：本文件为 2026-07-20 的一次性模块状态快照，已移出 `docs/standards/`。其"6 个文件已删除"的判断已被后续合并推翻——当前磁盘上 `backend/app/core/evolution/` 含 diff_engine、emergence_finder、orchestrator、path_recommender、snapshot_manager、timeseries_loader、trust_scorer 全部 7 个文件。Evolution 现行规范见 `docs/standards/01-backend/04-业务核心-evolution.md`。以下为原文，保留历史证据，不做修正。

---

# 业务核心 — Evolution 规范(v2,基于 2026-07-20 磁盘实况)

> ⚠️ **本文件是 v2,反映 2026-07-20 磁盘实况**
>
> **旧版**:`docs/standards/01-backend/04-业务核心-evolution.md`(基于 9 文件结构)
> 已与磁盘严重不一致 — `orchestrator.py` / `snapshot_manager.py` /
> `diff_engine.py` / `trust_integration.py` / `hallucination_guard.py` /
> `path_recommender.py` 6 个文件被删除(在 dirty 中)。
>
> **新实况**(从 `backend/app/core/evolution/__init__.py` 读取):
> - **Live**:`emergence_finder.py`(549 行)、`timeseries_loader.py`(待补充)
> - **In-Progress**:`AGENTS.md` 自身 dirty,待 WIP branch 合并后回写
> - **Removed**:6 个旧文件,逻辑去向由重构者决定(本 spec 不臆断)

---

## 1. 模块概述

Evolution(演化分析)是 StarMap 的核心业务层,负责追踪职位技能随时间的变化、检测新兴技能趋势。

**当前职责**(v2 实况):
- **新兴技能检测**:Z-score 算法(`emergence_finder.py`)
- **时间序列加载**:技能历史数据加载(`timeseries_loader.py`,待确认)

**过去职责**(v1 已删除):
- ~~快照管理~~(`snapshot_manager.py`)— 已删,功能去向待 WIP 合并
- ~~Diff 引擎~~(`diff_engine.py`)— 已删
- ~~反幻觉守卫~~(`hallucination_guard.py`)— 已删
- ~~信任度评分~~(`trust_integration.py`)— 已删
- ~~演化路径推荐~~(`path_recommender.py`)— 已删
- ~~8 步编排器~~(`orchestrator.py`)— 已删

**核心目标**:
- 保留真实"演化"信号能力(emergence_finder 是核心)
- 缩减冗余模块,避免逻辑分散到多个文件
- 待 WIP branch 合并后再扩职责描述

**在系统中的位置**:`backend/app/core/evolution/`,被 `api/v1/evolution.py` 调用,依赖 `models/` 层和 Neo4j/PostgreSQL。

---

## 2. 文件清单(磁盘实况,2026-07-20)

| 文件路径 | 状态 | 行数 | 职责 |
|---------|------|------|------|
| `__init__.py` | 🟢 Live(已修) | 7 | 公共 API 聚合,只声明 `emergence_finder` + `timeseries_loader` |
| `emergence_finder.py` | 🟢 Live(已修) | 549 | 新兴技能 Z-score 检测 + 跨领域分析 + 可迁移性评分 |
| `timeseries_loader.py` | ⚪ 待 WIP 合并确认 | - | 技能时间序列加载器(未读到具体内容) |
| `AGENTS.md` | 🟡 dirty(WIP) | 39 | 项目指令源(待 WIP 合并) |
| ~~`diff_engine.py`~~ | ❌ 已删(D) | - | 旧 diff 引擎 |
| ~~`hallucination_guard.py`~~ | ❌ 已删(D) | - | 旧反幻觉守卫 |
| ~~`orchestrator.py`~~ | ❌ 已删(D) | - | 旧 8 步编排器 |
| ~~`path_recommender.py`~~ | ❌ 已删(D) | - | 旧路径推荐 |
| ~~`snapshot_manager.py`~~ | ❌ 已删(D) | - | 旧快照管理 |
| ~~`trust_integration.py`~~ | ❌ 已删(D) | - | 旧信任度评分 |

---

## 3. 架构设计(v2)

### 3.1 当前模块结构

```
core/evolution/
├── __init__.py            ← 极简公共 API(7 行)
└── emergence_finder.py    ← Z-score 新兴技能检测(549 行,核心)
```

### 3.2 EmergenceFinder 核心算法

```python
z = (f(t) - μ) / σ
if z > 2.0 AND f(t) > 3 AND 独立来源 >= 3:    → EMERGING
elif z > 1.5:                                  → RISING
elif z < -1.5:                                 → DECLINING
else:                                          → STABLE
```

### 3.3 公共 API(v2)

```python
from app.core.evolution import EmergenceFinder, EmergenceSignal, EmergenceLevel
from app.core.evolution.timeseries_loader import TimeseriesLoader  # 假设命名
```

> **注意**: `__init__.py` 当前只声明 2 个模块,未重新导出具体类名(只有模块名)。使用者应直接从子模块 import。

---

## 4. 接口规范

### 4.1 输入
- **EmergenceFinder**:技能时间序列数据(`TimeseriesLoader` 提供)
- **TimeseriesLoader**:PostgreSQL `skill_timeseries` 表(或 Neo4j 时序)

### 4.2 输出
- `EmergenceSignal`:技能名 + Z-score + 等级 + 跨领域计数 + 可迁移性
- `EmergenceLevel`:enum(EMERGING/RISING/STABLE/DECLINING)

### 4.3 异常
- 无外部 LLM 调用,纯统计 → 无反幻觉需求
- 数据缺失 → 静默返回空信号列表(由调用方决定是否降级)

---

## 5. 编码规范

### 5.1 本模块特有
- **纯函数优先**:`EmergenceFinder.find()` 应该是幂等的(给定相同输入产生相同输出)
- **Dataclass 序列化**:`@dataclass` 而非 Pydantic,保持纯统计语义
- **枚举使用 `StrEnum`**:`EmergenceLevel(StrEnum)` 而非 `Enum`,方便 JSON 序列化
- **算法实现内置**:`z_score` 计算在模块内,不依赖 numpy(避免重型依赖)

### 5.2 反模式
- **不要**新增 LLM 调用到此模块(演化分析是纯统计,不接受幻觉)
- **不要**把"信任度"逻辑塞到 emergence_finder(信任度在 WIP 重构中,待新模块)
- **不要**直接 import Neo4j 驱动(数据由 `services/` 层提供)

---

## 6. 测试规范

- 当前文件:`backend/tests/unit/test_emergence_finder.py`(推测,未验证)
- 覆盖率:emergence_finder.py 内部分支应 100% 覆盖(纯统计)
- 用例:
  - `z > 2.0 + 高频 + 多源` → EMERGING
  - `z > 1.5` → RISING
  - `z < -1.5` → DECLINING
  - 空输入 → 空列表
  - 数据点 < 3 → 跳过(避免除零)

---

## 7. 变更管理

### 修改本模块时的检查清单

- [ ] 是否新增了 LLM 调用?(若"是",违反 §5.2 第一条)
- [ ] `__init__.py` 是否仍只声明 live 模块?
- [ ] 是否更新了 `emergence_finder.py` 行数(自我验证)?
- [ ] 是否同步更新了 `AGENTS.md`(当前 dirty,待 WIP 合并)?
- [ ] 是否更新了 ONBOARDING.md §3 的"反幻觉/信任的真实实现处"链接?

### 升级到 v3 的触发条件

当以下任一条件满足时,把本 spec 升级为 v3:
1. `AGENTS.md` 不再 dirty(已被 WIP branch 合并)
2. `__init__.py` 内容扩展到 > 7 行(说明新增了模块)
3. 出现新的子模块(除 `timeseries_loader.py` 外)

---

## 8. 引用

- **公共 API**:`backend/app/core/evolution/__init__.py`(磁盘实况)
- **核心实现**:`backend/app/core/evolution/emergence_finder.py`(549 行)
- **历史 v1**:`docs/standards/01-backend/04-业务核心-evolution.md`(已陈旧,保留作历史)
- **脏状态**:6 个文件 D + `__init__.py` / `emergence_finder.py` / `AGENTS.md` 改 — 等 WIP 合并
- **寻路**:`docs/standards/00-总纲/00-寻路-LANDING.md §1.3`