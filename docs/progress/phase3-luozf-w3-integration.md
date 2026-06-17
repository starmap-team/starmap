# W3 联调进度报告 — R1 罗智峰（流 A 后端-数据岗）

**报告日期**: 2026-06-17
**阶段**: W3（端到端联调）
**作者**: R1 罗智峰
**对接方**: R3 杨博文（流 B 算法-抽取岗）

---

## 一、本次提交内容

### 1.1 新增文件

| 文件 | 行数 | 用途 |
|---|---|---|
| `crawler/scripts/w3_integration.py` | 230 | 端到端联调主脚本：jd_raw → API → jd_extraction_records |
| `crawler/scripts/w3_run_golden.py` | 195 | 50 条 Golden Set 验证 F1 |
| `crawler/persistence/extraction_models.py` | 60 | R3 jd_extraction_records 表的 SQLAlchemy ORM |
| `crawler/persistence/extraction_dao.py` | 75 | R3 表的 DAO（upsert_extraction / count）|
| `crawler/tests/test_w3_integration.py` | 200 | 13 个 W3 单测（mock httpx + F1 + DAO roundtrip）|
| `docs/contract-w3-integration.md` | 170 | R1 ↔ R3 联调契约 v1 |

### 1.2 核心功能

#### 1.2.1 端到端联调 (`w3_integration.py`)
- 从 `jd_raw` 读 status=raw 的 JD（带 limit 限流）
- 调 `http://localhost:8000/api/v1/extract/jd`（R3 已实现）
- 响应回写 `jd_extraction_records` 表（R3 schema）
- 错误时回写 `jd_raw.status='failed'` + error_msg
- 完整请求/响应日志，支持 UTF-8

#### 1.2.2 F1 验证 (`w3_run_golden.py`)
- 加载 `evaluation/golden_set.jsonl` 50 条
- 每条调 `/extract/jd` 拿抽取结果
- 对比 jd_extraction_records-style 输出与 golden.required_skills
- 计算 Macro Precision / Recall / F1
- 输出 JSON 报告

#### 1.2.3 契约文档
- 输入/输出/错误处理/状态回写全部明确
- 验收标准对齐 M2 文档（F1 ≥ 0.80）

---

## 二、测试结果

### 2.1 单元测试

```
============================== 23 passed in 4.05s ==============================
```

| 文件 | 通过/总 | 覆盖率 |
|---|---|---|
| `test_dedup.py` | 5/5 | 97% |
| `test_clean.py` | 4/4 | 93% |
| `test_persistence.py` | 1/1 | 66% |
| `test_w3_integration.py` | 13/13 | 100% |
| **合计** | **23/23** | **45%（整体）** |

### 2.2 端到端测试

**状态：未完成**，原因：Docker Desktop 服务未启动（`com.docker.service` STOPPED），backend 容器无法运行。

**已就绪**：
- ✅ jd_extraction_records 表已建（`init_extraction_schema` 跑通）
- ✅ 302 条 jd_raw mock 数据已入库
- ✅ 联调脚本可通过 import 静态检查
- ✅ Mock httpx 单测全过
- ⏸️ 真实 backend 调用（需 Docker up + 讯飞 API key）

### 2.3 验收命令（Docker 起来后即可跑）

```bash
# 1. 启动 Docker
docker-compose -f docker-compose.dev.yml up -d

# 2. 等 backend 就绪
sleep 30
curl -sf http://localhost:8000/health

# 3. 跑 10 条真实联调
PYTHONIOENCODING=utf-8 POSTGRES_PORT=5433 PYTHONPATH=. \
  python crawler/scripts/w3_integration.py --max 10

# 4. 跑 50 条 Golden Set
PYTHONIOENCODING=utf-8 POSTGRES_PORT=5433 PYTHONPATH=. \
  python crawler/scripts/w3_run_golden.py --max 50

# 5. 查结果
docker exec starmap-postgres psql -U starmap -d starmap -c "
  SELECT
    (SELECT COUNT(*) FROM jd_raw WHERE status='extracted') AS jd_extracted,
    (SELECT COUNT(*) FROM jd_extraction_records) AS extraction_records;
"
```

---

## 三、当前阻塞项

| 阻塞项 | 原因 | 解锁条件 |
|---|---|---|
| Docker 服务 | `com.docker.service` 停了 | 手动启动 Docker Desktop |
| 讯飞星火 API key | `.env` 是占位符 | R3 杨博文或李帅提供 |
| jd_extraction_records 表 R1 写入权限 | R3 schema 所有权 | 已在契约里明确「只 INSERT」 |

---

## 四、依赖与对接

### 4.1 R3 依赖 R1 提供的
- ✅ `jd_raw` 表（PR #9 已合）
- ✅ 302 条 mock 数据（`m1_seed.py`）
- ✅ PostgreSQL 5433 端口（Windows 兼容）

### 4.2 R1 依赖 R3 提供的
- ✅ `/api/v1/extract/jd` 端点（PR #13 已合）
- ✅ 契约定义（`starmap-contracts/openapi.yaml`）
- ⏸️ 讯飞星火 API key（待 R3 提供）

### 4.3 R7 依赖 R1 提供的
- ⏸️ jd_extraction_records 真实数据（Docker 起来后即可生成）

---

## 五、下一步计划

| 时间 | 任务 | 负责人 |
|---|---|---|
| 6/17 今天 | Docker up + 跑通 1 条真实联调 | R1 罗智峰 |
| 6/18 周三 | 跑完 50 条 Golden Set 验证 F1 | R1 罗智峰 + R7 姜文彬 |
| 6/19 周四 | 反馈 F1 数字给 R3 调 prompt | R1 + R3 |
| 6/20 周五 | W3 联调 PR 提交 M2 验收 | R1 |

---

## 六、备注

- 本次新增代码**完全独立于 R3 schema**，未修改任何 R3 维护的表结构
- 字段调整走 Alembic 迁移（参见 `docs/contract-w3-integration.md` 第七节）
- Docker 启动 + 讯飞 API key 配置后，可立即完成端到端验证

> 报告由 R1 罗智峰生成于 2026-06-17 09:10
