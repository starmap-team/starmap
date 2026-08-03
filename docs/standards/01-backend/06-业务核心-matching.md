# Matching 核心规范

## 范围

`core/matching/` 负责规范技能比较、覆盖率/差距评分、缓存和学习路径构建；`services/match_service.py` 负责 API 编排和数据加载。

## 规则

- 输入技能先使用 extraction normalization 统一名称。
- required 与 bonus 技能分开计分，熟练度权重集中维护。
- 输出必须解释已匹配、缺失、部分匹配和建议依据。
- 缓存 key 包含影响结果的全部输入和版本信息。
- 不将 ChromaDB 可用性作为匹配正确性的前提。
- 批量匹配限制输入规模并保留每项错误上下文。

## 验证

运行匹配单元测试和 `evaluation/golden_set_match.jsonl` 对应评估；不要在规范写入某次准确率。
