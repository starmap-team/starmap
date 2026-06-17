# W3 联调契约：流 A (R1) ↔ 流 B (R3)

**版本**: v1
**生效日期**: 2026-06-17
**作者**: R1 罗智峰
**对接方**: R3 杨博文（流 B 算法-抽取岗）

---

## 一、目的

定义 R1（后端-数据）与 R3（算法-抽取）端到端联调时的输入、输出与边界。让两边的代码可以独立并行开发、契约可验证。

---

## 二、输入契约（R3 依赖 R1 提供的）

### 2.1 数据源表：`jd_raw`（R1 维护）

```sql
SELECT id, clean_text, job_title, source_site, source_url
FROM jd_raw
WHERE status = 'raw'              -- 只取未抽取的
ORDER BY id ASC
LIMIT N;                          -- 批量取 N 条
```

| 字段 | 类型 | 是否必填 | 说明 |
|---|---|---|---|
| id | BIGINT | ✓ | 主键（联调结果回写用）|
| clean_text | TEXT | ✓ | 清洗后的 JD 文本（≤ 50000 字符）|
| job_title | VARCHAR(200) | ✓ | 用于回写 jd_extraction_records.job_title |
| source_site | VARCHAR(32) | ✓ | 标注用（不参与 R3 逻辑）|
| source_url | TEXT | ✓ | 唯一键 |

### 2.2 服务地址
- 容器内：`http://backend:8000/api/v1/extract/jd`
- 宿主（开发机）：`http://localhost:8000/api/v1/extract/jd`
- 协议：HTTP POST + JSON
- 超时：60 秒（LLM 调用可能较慢）

---

## 三、输出契约（R3 返回给 R1）

### 3.1 HTTP 响应格式（与 openapi.yaml 一致）

```json
{
  "position_name": "高级Python后端工程师",
  "required_skills": [
    {"name": "Python", "level": "expert", "category": "hard_skill", "years_of_experience": 5}
  ],
  "preferred_skills": [
    {"name": "Kubernetes", "category": "tool"}
  ],
  "experience_required": 5,
  "education_required": "本科及以上",
  "responsibilities": ["负责核心API服务的设计", "..."],
  "confidence": 0.87,
  "hallucination_score": null,
  "normalized_skills": [
    {"original": "python3", "normalized": "Python", "score": 0.95}
  ]
}
```

### 3.2 错误响应

| 状态码 | 含义 | R1 处理 |
|---|---|---|
| 200 | 成功 | 写入 jd_extraction_records |
| 422 | LLM 返回非合法 JSON | jd_raw.status='failed', 记录 error_msg |
| 500 | 后端内部错误 | jd_raw.status='failed', 记录 error_msg |
| 502 | LLM API 不可用（讯飞 key 缺失）| jd_raw.status='failed' |
| 504 | 超时 | jd_raw.status='failed' |

### 3.3 必填字段（200 响应）

| 字段 | 类型 | 不可空 |
|---|---|---|
| position_name | string | 否（兜底用 jd_raw.job_title）|
| required_skills | array | 否（默认 []）|
| preferred_skills | array | 否（默认 []）|
| confidence | float | 否（默认 0.85）|

---

## 四、输出存储（R1 写回的表）

### 4.1 目标表：`jd_extraction_records`（R3 维护，schema 权限归 R3）

| 字段 | 类型 | R1 写入值 |
|---|---|---|
| jd_content | TEXT | jd_raw.clean_text（前 50000 字符）|
| job_title | VARCHAR(255) | 响应 position_name 或 jd_raw.job_title |
| extracted_skills | JSON | `{required_skills, preferred_skills, normalized_skills, responsibilities}` |
| experience_years | INT | 响应 experience_required |
| education | VARCHAR(100) | 响应 education_required |
| confidence | FLOAT | 响应 confidence |
| hallucination_score | FLOAT | 响应 hallucination_score |
| status | VARCHAR(20) | 'completed'（默认）/ 'failed' |

### 4.2 jd_raw 状态回写

| 场景 | jd_raw.status | jd_raw.error_msg |
|---|---|---|
| API 200 + DB 写入成功 | 'extracted' | NULL |
| API 4xx/5xx | 'failed' | API 错误信息（前 200 字符）|
| DB 写入失败 | 'failed' | 'DB insert failed: ...' |

---

## 五、联调验收标准（M2 里程碑）

| 指标 | 目标 | 验证方式 |
|---|---|---|
| 端到端跑通 | ≥ 10 条 jd_raw 完整跑通 | `python crawler/scripts/w3_integration.py --max 10` |
| Golden Set F1 | ≥ 0.80 | `python crawler/scripts/w3_run_golden.py --max 50` |
| jd_extraction_records 累计 | ≥ 50 条 | `SELECT COUNT(*) FROM jd_extraction_records` |
| jd_raw status=extracted | ≥ 50 条 | `SELECT COUNT(*) FROM jd_raw WHERE status='extracted'` |
| API 失败率 | < 5% | 跑 100 条统计 |

---

## 六、调用示例

```bash
# 1. 启 Docker 全栈
docker-compose -f docker-compose.dev.yml up -d

# 2. 等 backend 就绪（30s）
sleep 30
curl -sf http://localhost:8000/health

# 3. 建 jd_extraction_records 表（首次）
PYTHONPATH=. python crawler/scripts/w3_integration.py --init-schema

# 4. 跑 10 条真实联调
PYTHONPATH=. python crawler/scripts/w3_integration.py --max 10

# 5. 跑 50 条 Golden Set 验证
PYTHONPATH=. python crawler/scripts/w3_run_golden.py --max 50

# 6. 查结果
docker exec starmap-postgres psql -U starmap -d starmap -c "
  SELECT 
    (SELECT COUNT(*) FROM jd_raw WHERE status='extracted') AS jd_extracted,
    (SELECT COUNT(*) FROM jd_extraction_records) AS extraction_records;
"
```

---

## 七、变更记录

| 版本 | 日期 | 变更 |
|---|---|---|
| v1 | 2026-06-17 | 初稿（R1 罗智峰）|

> ⚠️ 任何对 jd_extraction_records schema 的修改需 R0 + R3 审批。
> 字段调整走 Alembic 迁移，参考 `backend/alembic/versions/001_initial_migration.py`。
