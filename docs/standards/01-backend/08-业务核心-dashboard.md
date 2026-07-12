# 业务核心 - Dashboard 规范

## 1. 模块概述

Dashboard（数据大屏）模块是 StarMap 的核心业务层之一，负责实时数据聚合和 SSE（Server-Sent Events）推送。该模块位于 `backend/app/core/dashboard/`，包含 2 个核心文件，共约 731 行代码。

**核心目标**：
- 实时聚合系统运行数据（流水线状态、匹配结果、演化趋势等）
- 通过 SSE 向客户端推送实时更新
- 提供数据大屏所需的统计指标和图表数据

**在系统中的位置**：位于 `backend/app/core/dashboard/`，被 `api/v1/dashboard.py` 调用，依赖 Redis 和 PostgreSQL。

---

## 2. 文件清单

| 文件路径 | 行数 | 职责 | 主要导出 |
|---------|------|------|---------|
| `backend/app/core/dashboard/__init__.py` | 0 | 包声明 | 无 |
| `backend/app/core/dashboard/dashboard_service.py` | 486 | 数据大屏服务：实时数据聚合、统计计算 | `DashboardService`, `get_dashboard_data`, `get_pipeline_stats` |
| `backend/app/core/dashboard/sse_broadcaster.py` | 245 | SSE 广播器：Redis pub/sub 桥接、事件推送 | `publish_event`, `subscribe_events`, `SSEBroadcaster` |

---

## 3. 架构设计

### 3.1 模块内部结构

```
core/dashboard/
├── __init__.py            ← 包声明
├── dashboard_service.py   ← 数据大屏服务
└── sse_broadcaster.py     ← SSE 广播器
```

### 3.2 数据流向

```
HTTP GET /api/v1/dashboard/stream
    │
    ▼
┌─────────────────────────┐
│ api/v1/dashboard.py      │
└─────────────────────────┘
    │
    ▼
┌─────────────────────────┐
│ core/dashboard/dashboard_service.py │
│ ├─ 聚合流水线状态          │
│ ├─ 聚合匹配结果            │
│ ├─ 聚合演化趋势            │
│ └─ 计算统计指标            │
└─────────────────────────┘
    │
    ▼
┌─────────────────────────┐
│ core/dashboard/sse_broadcaster.py │
│ ├─ Redis pub/sub         │
│ └─ SSE 推送               │
└─────────────────────────┘
    │
    ▼
客户端 (Vue + EventSource)
```

### 3.3 SSE 推送机制

```
Redis pub/sub
    │
    ├──► SSEBroadcaster.publish_event()
    │       │
    │       ▼
    │   客户端 1 (EventSource)
    │
    ├──► SSEBroadcaster.publish_event()
    │       │
    │       ▼
    │   客户端 2 (EventSource)
    │
    └──► SSEBroadcaster.publish_event()
            │
            ▼
        客户端 3 (EventSource)
```

---

## 4. 接口规范

### 4.1 主要类与函数签名

```python
# dashboard_service.py
class DashboardService:
    async def get_overview(self) -> dict[str, Any]:
        """获取数据大屏概览数据。"""

    async def get_pipeline_stats(self) -> dict[str, Any]:
        """获取流水线统计。"""

    async def get_match_stats(self) -> dict[str, Any]:
        """获取匹配统计。"""

    async def get_evolution_stats(self) -> dict[str, Any]:
        """获取演化统计。"""

# sse_broadcaster.py
async def publish_event(redis: Redis, channel: str, data: dict[str, Any]) -> None:
    """通过 Redis pub/sub 发布事件。"""

async def subscribe_events(redis: Redis, channel: str) -> AsyncIterator[dict[str, Any]]:
    """订阅 Redis pub/sub 事件。"""

class SSEBroadcaster:
    def __init__(self, redis: Redis) -> None: ...
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
```

### 4.2 SSE 事件格式

```json
{
  "event": "pipeline_update",
  "data": {
    "run_id": "...",
    "stage": "crawl",
    "status": "completed",
    "progress": 1.0,
    "records_processed": 100,
    "message": ""
  }
}
```

---

## 5. 编码规范（本模块特有）

### 5.1 Redis pub/sub 使用

```python
# sse_broadcaster.py
async def publish_event(redis: Redis, channel: str, data: dict[str, Any]) -> None:
    """通过 Redis pub/sub 发布事件。"""
    await redis.publish(channel, json.dumps(data))

async def subscribe_events(redis: Redis, channel: str) -> AsyncIterator[dict[str, Any]]:
    """订阅 Redis pub/sub 事件。"""
    pubsub = redis.pubsub()
    await pubsub.subscribe(channel)
    async for message in pubsub.listen():
        if message["type"] == "message":
            yield json.loads(message["data"])
```

### 5.2 反模式

| 反模式 | 说明 | 正确做法 |
|--------|------|---------|
| 直接推送 SSE | 绕过 Redis | 使用 Redis pub/sub 桥接 |
| 在 SSE 中推送大量数据 | 性能问题 | 只推送关键指标和状态变更 |
| 忽略连接断开 | 资源泄漏 | 处理客户端断开事件 |

---

## 6. 测试规范

### 6.1 对应测试文件

| 被测模块 | 测试文件 | 行数 | 测试类型 |
|---------|---------|------|---------|
| `dashboard_service.py` | `tests/unit/test_dashboard_service.py` | 164 | 单元测试 |
| `sse_broadcaster.py` | `tests/unit/test_sse_broadcaster.py` | 122 | 单元测试 |

### 6.2 覆盖率要求

- `dashboard_service.py`：数据聚合 >= 60%
- `sse_broadcaster.py`：SSE 推送 >= 60%

### 6.3 Mock 策略

```python
# 测试 DashboardService
def test_get_overview():
    # mock PostgreSQL 查询
    # 验证返回数据格式正确

# 测试 SSEBroadcaster
def test_publish_event():
    # mock Redis
    # 验证事件发布正确
```

---

## 7. 变更管理

### 7.1 修改检查清单

修改 Dashboard 模块时：

- [ ] 是否新增统计指标？是 → 确认数据来源
- [ ] 是否修改 SSE 事件格式？是 → 同步更新前端
- [ ] 是否修改 Redis 频道？是 → 同步更新订阅方

### 7.2 契约影响

| 变更 | 影响 |
|------|------|
| 新增统计指标 | 影响前端展示 |
| 修改 SSE 事件格式 | 影响前端解析 |
| 修改 Redis 频道 | 影响所有订阅方 |

### 7.3 迁移要求

- 修改 SSE 事件格式时，必须同步更新前端 EventSource 解析逻辑
- 新增统计指标时，必须确认数据来源可靠
