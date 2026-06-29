# Accuracy Measurement Report — StarMap v2.1 (Real LLM Data)

**Measurement date:** 2026-06-28
**LLM model:** MiMo v2.5 (xiaomimimo.com)
**Scope:** JD extraction accuracy against 10 golden samples

---

## 1. JD Extraction Accuracy — PASS ✅

### 1.1 Test Method

- Used `backend/tests/fixtures/golden_jd_evaluation_sample.jsonl` (10 JDs covering 10 IT job types)
- Sent each JD to live `POST /api/v1/extract/jd` API endpoint
- MiMo v2.5 performed real LLM extraction with anti-hallucination validation
- Compared extracted skills against golden ground truth with fuzzy normalization

### 1.2 Results

| Sample | Job Title | Precision | Recall | F1 | Status |
|--------|-----------|-----------|--------|-----|--------|
| golden-1 | AI 应用工程师 | 1.000 | 1.000 | 1.000 | ✅ |
| golden-2 | 数据分析师 | 0.571 | 0.571 | 0.571 | ⚠️ |
| golden-3 | 前端开发工程师 | 0.857 | 0.857 | 0.857 | ✅ |
| golden-4 | 后端开发工程师 | 1.000 | 1.000 | 1.000 | ✅ |
| golden-5 | 机器学习工程师 | 1.000 | 1.000 | 1.000 | ✅ |
| golden-6 | 大数据开发工程师 | 1.000 | 1.000 | 1.000 | ✅ |
| golden-7 | DevOps工程师 | 1.000 | 1.000 | 1.000 | ✅ |
| golden-8 | 自然语言处理工程师 | 0.889 | 0.889 | 0.889 | ✅ |
| golden-9 | Android开发工程师 | 1.000 | 1.000 | 1.000 | ✅ |
| golden-10 | 信息安全工程师 | 0.889 | 0.889 | 0.889 | ✅ |

### 1.3 Summary

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| Avg Precision | **0.9206** | >=0.85 | ✅ PASS |
| Avg Recall | **0.9206** | >=0.85 | ✅ PASS |
| Avg F1 | **0.9206** | >=0.85 | ✅ PASS |
| Samples >= 0.85 F1 | 9/10 (90%) | >=80% | ✅ PASS |
| Perfect samples (F1=1.0) | 6/10 (60%) | — | ✅ |

### 1.4 Notes

- golden-2 (数据分析师) has F1=0.571: LLM extracted 7 skills but 3 didn't match golden (possibly different naming like "统计学" vs "Statistics")
- All other samples achieve >=0.857 F1, with 6 being perfect 1.0
- Results are consistent across multiple measurement runs

---

## 2. Match Accuracy — PASS ✅

### 2.1 Test Method

- Used `backend/tests/fixtures/golden_match_sample.jsonl` (8 match pairs)
- Tests run via `test_match_golden.py` against match engine

### 2.2 Results

8/8 samples pass (100%):
- 4 positive matches: all score above threshold
- 4 negative matches: all score below 0.6
- Perfect overlap test: >=0.85
- Empty skills test: <0.5
- Result persistence test: match_id retrievable

---

## 3. Resume Golden Set — Ready

- `backend/tests/fixtures/golden_resume_sample.jsonl` (8 samples, 8 IT job types)
- Resume extraction requires file upload (PDF/DOCX) — tested via API

---

## 4. Infrastructure Verification

| Component | Status | Evidence |
|-----------|--------|----------|
| Live API (Docker) | ✅ | Health: postgres=ok, neo4j=ok, redis=ok |
| Neo4j data volume | ✅ | 36 positions, 201 skills, 360 edges |
| Graph panorama | ✅ | 281 nodes, 500 edges |
| API smoke (18 endpoints) | ✅ | 18/18 passed |
| Backend tests | ✅ | 192 passed, 1 skipped, 71.81% coverage |
| Team simulation | ✅ | 11/11 (100%) |

---

## 5. Conclusion

StarMap v2.1 extraction accuracy **meets the 85% target** with real MiMo v2.5 LLM:

- **JD Extraction F1: 0.9206** (target: >=0.85) ✅
- **Match Accuracy: 100%** (8/8 golden pairs) ✅
- **All E2E and smoke tests: PASS** ✅

---

**Signed:** R7 蒋文斌 / R0 李帅
**Date:** 2026-06-28
