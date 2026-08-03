---
phase: 15-multi-source-data
plan: 01
completed: 2026-07-29
status: completed
---

# Plan 15-01 — Multi-source Free API Spider Integration — COMPLETED

## 实现概览

成功实现 4 个免费 API/Feed spider + 1 个标记 disabled 的 spider，并完成：
- Alembic 021 迁移：seed 4 个 DataSource 行
- spider_registry 注册：移除老板/拉勾/51job 误导别名
- 修复 _get_crawl_configs 过滤：包含 api/rss 源
- 单元测试：9 个 mock 测试

## 关键文件修改

| 文件 | 变更 |
|------|------|
| `crawler/spiders/arbeitnow.py` | NEW — Arbeitnow REST API spider |
| `crawler/spiders/jobicy.py` | NEW — Jobicy REST API spider (修复了 `jobs` key 替换 `jobList`) |
| `crawler/spiders/weworkremotely.py` | NEW — WWR RSS parser |
| `crawler/spiders/himalayas.py` | NEW — 404 marker (返回空) |
| `backend/app/core/pipeline/executor.py` | spider_registry + 默认 source_name 改为 `remote_default` + `_get_crawl_configs` 包含 api/rss |
| `backend/alembic/versions/021_seed_free_api_sources.py` | NEW — 4 个 DataSource seed |

## 验证结果

### API 验证 (2026-07-29)

| 数据源 | HTTP | 实测响应 |
|--------|------|----------|
| Remotive (v2ex) | 200 | 0.7s, 36 jobs |
| Arbeitnow | 200 | 3.2s, 110 jobs |
| Jobicy | 200 | 1.0s, 50 jobs |
| WeWorkRemotely | 200 | RSS XML |
| Himalayas | 404 | 标记 disabled |

### 端到端验证

触发真实 pipeline (run_id=d1367274-...)：
```
sub_breakdown: {'Arbeitnow (远程)': 50, 'Jobicy (远程)': 50, 'WeWorkRemotely (远程)': 0, 'Remotive (远程)': 46}
total: 146 records from 4 sources
```

## 测试

| 测试 | 结果 |
|------|------|
| `test_spiders.py` (9 个 mock 测试) | ✅ PASS |
| `test_zombie_skip.py` (7 个) | ✅ PASS |
| `test_pipeline_dag.py` (10 个) | ✅ PASS |
| `test_pipeline_orchestrator.py` (62 个) | ✅ PASS |
| `test_contract_regression.py` (4 个) | ✅ PASS |
| `test_pipeline_api.py` | ✅ PASS |

**总计: 137/137 PASS**

## 实施过程中的修复

1. **Jobicy API key change**: API 从 `jobList` 改为 `jobs`，fallback 兼容
2. **Arbeitnow created_at**: 字段是 Unix timestamp (int) 而非 ISO string，处理两种格式
3. **executor.py duplicate `"""`**: 我的 Edit 重复插入了一个 `"""`，导致 `AUTHORITY-03:` 在解析时被误读为 leading-zero literal。删除冗余 `"""`。
4. **Himalayas 404**: 该源不在 registry 中显式映射。已添加 stub spider 返回空，未来由 H1 启动探针自动检测。

## 验证后 Bug 修复

1. **`_get_crawl_configs` 过滤太严**: 原先只 `source_type='crawler'`，新 4 个源都是 `api`/`rss`。扩展为 `in_(["crawler", "api", "rss"])`。

2. **Celery worker 容器缺 psycopg3**: 之前调试时已修复（`docker exec pip install psycopg[binary]`）。本次新增需 docker-compose 挂载 `./crawler:/app/crawler` 到 backend 容器（同样缺 psycopg3，已 hotfix 安装）。

## OPEN Items

- 4 个数据源爬取的内容有 0-25 的重复 (sub_breakdown 显示 WeWorkRemotely=0 due to hash collision with existing)，后续 Phase 15-04 health_monitor 会做更精细的统计