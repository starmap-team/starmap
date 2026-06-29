# Prompt A/B Test Report — StarMap v2.1 (Real LLM Data)

**Test date:** 2026-06-28
**LLM model:** MiMo v2.5 (xiaomimimo.com)
**Test samples:** 3 representative JDs (AI应用工程师, 后端开发工程师, NLP工程师)

---

## 1. Test Method

- Used `POST /api/v1/extract/jd` with live MiMo v2.5 LLM
- Tested all 4 prompt versions (v1-v4) on 3 golden JD samples
- Compared extracted skills against golden ground truth
- Measured Precision, Recall, and F1 for each version

## 2. Results

| Version | Avg F1 | golden-1 (AI) | golden-4 (Backend) | golden-8 (NLP) |
|---------|--------|---------------|---------------------|----------------|
| v1 (Baseline) | **0.963** | 1.000 | 1.000 | 0.889 |
| v2 (Structured) | **0.963** | 1.000 | 1.000 | 0.889 |
| v3 (Few-shot) | **0.963** | 1.000 | 1.000 | 0.889 |
| v4 (Chain-of-thought) | **0.963** | 1.000 | 1.000 | 0.889 |

## 3. Analysis

All 4 prompt versions produce **identical F1=0.963** on the test samples:
- **AI应用工程师**: 8/8 skills extracted perfectly (F1=1.0)
- **后端开发工程师**: 7/7 skills extracted perfectly (F1=1.0)
- **NLP工程师**: 8/9 skills matched, 1 minor naming difference (F1=0.889)

The MiMo v2.5 model is robust across all prompt variations for these well-structured JDs. This indicates the extraction quality is primarily driven by the LLM capability rather than prompt engineering differences.

## 4. Recommendation

- **Keep v1 as production default** — simplest prompt, identical performance
- **Re-test with harder samples** (ambiguous JDs, non-standard skill names) if prompt differentiation is needed
- **v4 (CoT) for audit scenarios** where explainability matters

## 5. Broader Accuracy Context

Combined with the full 10-sample measurement:
- **Full 10-sample JD F1: 0.9206** (target >=0.85) ✅ PASS
- **3-sample A/B F1: 0.963** (all versions identical)
- **Match accuracy: 100%** (8/8 golden pairs) ✅ PASS

---

**Signed:** R3 杨博文 / R0 李帅
**Date:** 2026-06-28
