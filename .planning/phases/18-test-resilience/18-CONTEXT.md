# Phase 18 CONTEXT — 测试弹性和清理

## 用户决策 (从 Phase 17 残留 OPEN)

Phase 17 完成后, 2 项残留测试改进:
1. **跨端 20 抽样测试**: `asyncio.run()` 与 pytest 同步事件循环冲突,需改 `pytest-asyncio`
2. **失败重试集成测试**: Phase 17 计划留作 TODO,需 mock LLM/Redis 失败路径

## Phase 18 范围

**包含:**
- 18-01: 跨端 20 抽样测试改 `pytest-asyncio` (解决事件循环冲突)
- 18-02: 失败重试集成测试 (mock LLM/Redis 失败路径)
- 18-03: 清理 — 关闭 active debug, archive todos

**不包含:**
- 修复其他遗留 plan (历史重复, 不影响 v5.0 进度)
- 重新设计 Pipeline 状态机
- 数据完整性重构 (status gate + outbox 已足够)

## 锁定决策

1. **18-01 测试改 async**: 用 `@pytest.mark.asyncio` + `httpx.AsyncClient`, 避免事件循环冲突
2. **18-02 失败重试 mock 范围**: 只 mock LLM (返回 failed) + Redis (连接失败), 不 mock Neo4j (有专门的集成测试)
3. **18-03 清理策略**: graph-child-nodes-fix 确认已修, position-list-detail-ux-resolved 标记 resolved; todos 全部 archive

## 风险

| 风险 | 缓解 |
|------|------|
| pytest-asyncio 安装问题 | 检查 pyproject.toml, 必要时手动 pip install |
| Mock LLM 测试与实际 API 行为不同 | mock 只测试降级路径, 真实集成保留 |
| 关闭 debug session 后又有新 bug | 留 debug/ 目录供后续 |