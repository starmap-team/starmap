# Phase 6 — JD 抽取模块 (ExtractJD) 研究报告

## 模块概述

ExtractJD.vue (311 行) 是 JD 抽取页面，用户提交 JD 文本，调用 LLM 抽取技能、标准化、入库。

## 关键文件

| 文件 | 大小 | 说明 |
|------|------|------|
| `frontend/src/pages/ExtractJD.vue` | 311 行 | JD 抽取主页面 |
| `frontend/src/pages/__tests__/ExtractJD.spec.ts` | 43 行 | 1 个冒烟测试 |
| `backend/app/api/v1/extract.py` | - | 后端抽取 API |
| `backend/app/core/extraction/` | - | 抽取核心（jd_extract.py, resume_extract.py, normalize.py, anti_hallucination.py, llm_client.py） |

## 后端 API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/extract/jd` | POST | JD 抽取 |
| `/api/v1/extract/resume` | POST | 简历抽取 |
| `/api/v1/extract/cost-summary` | GET | LLM 成本统计 |

## 关键业务流

JD 文本提交 → PII 脱敏 → LLM 抽取 (MiMo → DeepSeek → 星火 → Qwen 降级) → JSON 校验 → 标准化 → 反幻觉检查 → 入库 (PostgreSQL) → 投影 Neo4j

## 测试覆盖现状

- 1 个冒烟测试
- 无 LLM 调用、反幻觉、数据库写入测试

## 已知关注点

1. LLM 供应商降级链
2. 反幻觉检查可见性
3. 抽取结果前端展示
4. 成本统计展示
