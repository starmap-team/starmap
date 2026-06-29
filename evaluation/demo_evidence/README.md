# 新岗位发现证据链 — 大模型应用工程师

> 演示目标：展示系统从数据采集到新岗位入图的完整证据链，证明岗位是"被系统发现"而非"被人工预设"。

## 证据链6要素

| # | 证据要素 | 文件 | 数据来源 | 状态 |
|---|---------|------|---------|------|
| 1 | 涌现检测信号 | `01_emergence_detection.json` | 时序统计（skill_timeseries表） | ✅ Z-score > 2.0 |
| 2 | 多源独立确认 | `02_multi_source_verification.json` | 7个独立数据源 | ✅ ≥5源 |
| 3 | 技能聚类分析 | `03_skill_clustering.json` | HDBSCAN聚类 | ✅ 独立簇 |
| 4 | LLM定义生成 | `04_llm_position_definition.json` | Qwen2.5-72B via StarFire | ✅ 5要素 |
| 5 | 幻觉防控报告 | `05_hallucination_guard.json` | 三层防线 | ✅ 8/8通过 |
| 6 | 人工审核 | `06_human_review.json` | 管理后台审核队列 | ✅ 已批准 |

## 演示流程

```
全景图谱 → 看到"大模型应用工程师"节点
    ↓
点击节点 → 查看技能详情（Python/LLM/RAG/LangChain/Prompt Engineering/FastAPI）
    ↓
演化看板 → 涌现技能检测（LLM: Z=3.2, RAG: Z=2.8, LangChain: Z=2.5）
    ↓
管理后台 → 审核队列（trust_score=0.91, 已批准）
    ↓
展示中间产物 → 6份JSON证据文件逐环节追溯
```

## 数据完整性说明

- 所有JSON文件均为系统运行时产物的快照
- 原始JD数据来源：BOSS直聘、拉勾、猎聘、智联招聘、前程无忧、科大讯飞招聘、ESCO
- 时序数据采用混合策略（real_archive + inferred_consensus），每个数据点标注来源级别
