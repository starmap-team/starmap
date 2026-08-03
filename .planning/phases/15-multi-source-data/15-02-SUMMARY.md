---
phase: 15-multi-source-data
plan: 02
completed: 2026-07-29
status: completed
---

# Plan 15-02 — CSV/JSON 用户手动导入端点 — COMPLETED

## 实现概览

实现了完整 CSV/JSON 导入端点，包含:
- Pydantic schemas
- CSV 解析器 (UTF-8/BOM/GBK 自动检测)
- PII 检测器 (Fix H2)
- Import 服务 (Fix H2 + H3)
- POST `/api/v1/import/jd` (CSV) 和 `/api/v1/import/jd/json` (JSON)
- Alembic 022 + 023 迁移 (UNIQUE constraint 切换)
- 16 个单元测试

## 关键文件修改

| 文件 | 变更 |
|------|------|
| `backend/app/schemas/import_jd.py` | NEW — ImportItem, ImportRequest, ImportResult |
| `backend/app/services/pii_detector.py` | NEW — 手机/邮箱/身份证检测 (Fix H2) |
| `backend/app/services/csv_parser.py` | NEW — 多编码支持 (Fix M3) |
| `backend/app/services/import_service.py` | NEW — 复用 dao.upsert_jd + content_hash (Fix H3) |
| `backend/app/api/v1/import_jd.py` | NEW — 两个端点 |
| `backend/app/api/v1/router.py` | 注册新路由 |
| `backend/app/utils/audit.py` | 添加 AuditEvent.MANUAL_IMPORT / PII_DETECTED |
| `backend/alembic/versions/022_unique_content_hash.py` | NEW — content_hash 唯一索引 |
| `backend/alembic/versions/023_drop_source_url_unique.py` | NEW — 删除 source_url UNIQUE 约束 |
| `crawler/persistence/dao.py` | upsert_jd 改用 content_hash + inserted_primary_key 判断 |
| `backend/Dockerfile` | ADD `COPY crawler/ ./crawler/` |
| `docker-compose.dev.yml` | ADD `./crawler:/app/crawler` 挂载 |
| `tests/unit/test_import_jd.py` | NEW — 16 个测试 |

## 实施过程中的关键 Bug 修复

### 🐛 Bug 1: `dao.upsert_jd` 返回错误的 "duplicate"

**症状:** 即使新数据被实际插入数据库，函数仍返回 "duplicate"

**根因:** `result.rowcount == -1` (psycopg + SQLAlchemy `pg_insert().on_conflict_do_nothing()` 的怪异行为)，导致 `if result.rowcount > 0` 判定失败

**修复:** 改用 `result.inserted_primary_key` 判断 (Phase 15-02 期间)

```python
# Before
return "inserted" if result.rowcount > 0 else "duplicate"

# After
inserted_pk = getattr(result, "inserted_primary_key", None)
if inserted_pk:
    return "inserted"
return "inserted" if (result.rowcount and result.rowcount > 0) else "duplicate"
```

### 🐛 Bug 2: source_url UNIQUE 约束导致 CSV 导入全部失败

**症状:** `duplicate key value violates unique constraint "jd_raw_source_url_key"` — 因为 CSV source_url 经常为空

**修复:**
1. Alembic 022: 加 `uq_jd_raw_content_hash` UNIQUE 索引
2. Alembic 023: `DROP CONSTRAINT jd_raw_source_url_key`
3. dao.upsert_jd 改用 content_hash 而非 source_url

### 🐛 Bug 3: backend 容器缺 crawler/ 目录

**修复:** 
- `Dockerfile`: `COPY crawler/ ./crawler/`
- `docker-compose.dev.yml`: `- ./crawler:/app/crawler`

### 🐛 Bug 4: backend 容器缺 psycopg3

**修复:** `docker exec starmap-backend pip install 'psycopg[binary]>=3.0'` (持久化需重 build image)

## 验证结果

### API 端到端测试

```bash
# Test 1: 唯一内容 → inserted=1
$ curl -X POST /api/v1/import/jd -F file=@test_v6.csv ...
{"total":1,"inserted":1,"duplicate":0,"errors":[],"pii_warnings":0}

# Test 2: 重复上传 → duplicate=1
$ curl -X POST /api/v1/import/jd -F file=@test_v6.csv ... (same content)
{"total":1,"inserted":0,"duplicate":1,"errors":[],"pii_warnings":0}

# Test 3: PII 检测 → pii_warnings=1
$ curl -X POST /api/v1/import/jd -F file=@test_pii6.csv ...
{"total":1,"inserted":1,"duplicate":0,"errors":[],"pii_warnings":1}
```

### 数据库验证

```
SELECT job_title FROM jd_raw WHERE source_site = 'manual';
-- V4QAEngineer1785264280888721000
-- V6QAEngineer<NEW>           ← 新插入
-- Data Engineer PII6 <NEW>     ← PII 检测
```

### 测试

| 测试 | 结果 |
|------|------|
| `test_import_jd.py` (16 个: PII detector 7 + CSV parser 8 + service 1) | ✅ PASS |
| `test_zombie_skip.py` (7) | ✅ PASS |
| `test_pipeline_dag.py` (10) | ✅ PASS |
| `test_pipeline_orchestrator.py` (62) | ✅ PASS |
| `test_contract_regression.py` (4) | ✅ PASS |
| `test_pipeline_api.py` | ✅ PASS |
| `test_spiders.py` (9) | ✅ PASS |

**总计: 153/153 PASS**

## 残留 OPEN

- 前端 UI (Plan 15-03 未执行): CSV 导入对话框尚未实现
- Alembic 022/023 需 `poetry run alembic upgrade head` 应用（已通过手动 docker exec 应用）
- Dockerfile psycopg3 持久化：当前是 hotfix，需要重 build backend image

## 建议

1. 重 build backend image 持久化 psycopg3
2. 推进 Plan 15-03 (前端 UI) 让用户能用 UI 上传
3. 推进 Plan 15-04 (健康度监控) 增加 PII 警告展示