# 评测模块

**负责人**: R7 姜文彬（流D QA评估）

## 文件说明

| 文件 | 用途 |
|------|------|
| `judge_eval.py` | LLM-as-judge裁判评估+F1指标计算 |
| `golden_set.jsonl` | 50条Golden标注样本（JD抽取标准答案），含raw_jd原始文本 |
| `run_baseline.py` | 基于 normalize.py 别名表的关键词匹配基线评估 |
| `simulate_llm_eval.py` | LLM抽取模拟（从Golden答案注入随机噪声），无API时用于验证评估框架 |
| `baseline_report/` | 基线评估报告（F1=0.758，关键词匹配） |
| `llm_sim_report/` | LLM模拟评估报告（F1=0.9759，非真实LLM结果） |

## 评估指标

- **技能F1**: 基于集合的精确率/召回率/F1（大小写不敏感，自动trim）
- **加权总分**: F1(0.5) + 岗位名称(0.15) + 经验(0.15) + 学历(0.20)
- **质量门禁**: F1≥0.90绿色 / ≥0.85黄色 / ≥0.80橙色 / <0.80红色

## 评估数据说明

| 报告 | F1 | 方法 | 含义 |
|------|-----|------|------|
| `baseline_report/` | 0.758 | 纯关键词匹配（基于 normalize.py 别名表进行 JD 原文子串匹配） | 无 AI 参与的下限参考 |
| `llm_sim_report/` | 0.9759 | 从 Golden 标准答案注入 ~5% 随机噪声（删3%技能、8%样本加1个幻觉、5%分类错误） | 模拟理想上限，非真实 LLM 抽取结果 |

**为什么 llm_sim 远高于 baseline？**

两份报告来自不同的评估方法，不可直接对比：
- **baseline（0.758）** 是真实的关键词硬匹配，漏检和误检如实反映，jd-010 仅 0.387
- **llm_sim（0.9759）** 从完美答案出发随机增减，回避了系统性失败模式（如 jd-010 在 sim 中为 1.0）
- **二者均为 M1 阶段验证评估框架所用，不代表 M2 LLM 抽取的真实水平**

**M2 真实 LLM 管线（讯飞星火 API）预期 F1：0.80~0.90**，待开发完成后更新。

## 使用方式

```python
from evaluation.judge_eval import evaluate_batch, check_quality_gate

# 批量评估
metrics = evaluate_batch(
    golden_file="evaluation/golden_set.jsonl",
    system_file="data/output/jd_output.jsonl",
    output_file="data/output/eval_result.json"
)

# 检查门禁
gate = check_quality_gate(metrics)
print(gate)  # {"passed": True/False, "status": "green"/"red", ...}
```
