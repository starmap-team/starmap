# 阶段 3: 输入校验与注入防护

**开始时间**: 2026-07-08T10:30:00+08:00
**结束时间**: 2026-07-08T11:00:00+08:00
**风险计数**: P0 × 1 / P1 × 0 / P2 × 4 / P3 × 1

---

## INJ-01 [P0] Judge batch 路径遍历

**CVSS 3.1**: 8.6
**文件**: `judge.py:56-57`, `judge_service.py:145-160`
**详情**: `BatchJudgeRequest.golden_file/system_file` 直接传给 `Path(filepath).read_text()`，无目录白名单。

**攻击**: `POST /judge/batch {"golden_file":"/etc/passwd","system_file":"/etc/passwd"}`

**最小修复**: 限制路径在 `data/evaluation/` 目录内：
```python
_ALLOWED_DIR = Path("data/evaluation")
path = Path(filepath).resolve()
if not str(path).startswith(str(_ALLOWED_DIR.resolve())):
    raise ValueError(f"File path must be within {_ALLOWED_DIR}")
```

---

## INJ-02 [P2] /match/batch 无 Pydantic schema

**CVSS 3.1**: 4.3
**文件**: `match.py:157-159`
**详情**: `body: dict` 无校验，`items[:20]` 无认证保护。

**最小修复**: 定义 `BatchMatchRequest(BaseModel)` schema。

---

## INJ-03 [P2] SQL ilike 通配符注入

**CVSS 3.1**: 3.7
**文件**: `position.py:62,70`
**详情**: `ilike(f"%{search}%")` 未转义 `%` 和 `_`。

**最小修复**: `search.replace("%","\\%").replace("_","\\_")` + `escape="\\"`。

---

## INJ-04 [P2] Neo4j Cypher f-string (白名单缓解)

**CVSS 3.1**: 4.3 (当前不可利用)
**文件**: `admin_graph_nodes.py:94-96`, `graph_writer.py:335-352`
**详情**: f-string 拼接标签，但已有 `_ALLOWED_LABELS` 白名单。

---

## INJ-05 [P2] 文件上传仅校验扩展名

**CVSS 3.1**: 5.3
**文件**: `extract.py:178-179`, `resume.py:21-33`
**详情**: `/resume/upload` 连扩展名都不检查。

---

## INJ-06 [P3] admin.py sa.text() 静态 SQL

**文件**: `admin.py:156` — 纯静态 SQL，无风险。

---

**下一阶段输入交接**:
- Judge batch 路径遍历为 P0，需立即修复
- 文件上传 MIME 校验需在阶段 5 跟进
