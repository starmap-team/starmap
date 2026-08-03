# Golden Set 标注规范

> 状态：活文档
> 最近核对：2026-07-24

## 数据集边界

| 文件 | 评估域 |
|---|---|
| `golden_set.jsonl` | JD 抽取 |
| `golden_set_resume.jsonl` | 简历抽取 |
| `golden_set_match.jsonl` | 人岗匹配 |
| `golden_set_pipeline.jsonl` | 流水线场景 |

记录数从 JSONL 实际内容统计，不在规范维护副本：

```powershell
(Get-Content evaluation/golden_set.jsonl | Where-Object { $_.Trim() }).Count
```

## JD 标注结构

每行一个 UTF-8 JSON object，至少包含稳定 `id`、`raw_jd`、岗位名称、required/bonus skills、经验、学历和来源。字段名与评估代码保持一致。

## 技能标注

- 只标注原文明确表达或可直接等价归一的技能。
- required：任职要求、必须、熟练/精通等硬要求。
- bonus：优先、加分、了解即可等非硬要求。
- 不把职责目标、软性形容词、公司福利或推断出的技术栈当技能。
- 使用规范技能名；别名映射由 normalization 维护，标注中不保留同义重复。
- 原文证据不足时不补全常识，避免把标注者推测当真值。

## 结构字段

- `job_title` 保留明确岗位名称，不从公司宣传语推断。
- `experience_years` 取明确最低年限；范围取下界；未写则使用约定空值。
- `education` 保留原文最低学历语义；未写则使用约定空值。
- 文本中的"工作经验不限"与缺失必须区分。

## 评审与版本

- 新增/修改样本需要第二标注者复核；争议由仲裁者记录理由。
- 冻结版本后只追加新版本，不静默修改用于已发布结果的真值。
- 评估结果记录数据集 commit、模型、prompt 版本和时间。
- Golden truth 不得进入被评估的抽取 prompt、检索上下文或 mock 输出。
- 单人历史标注可用于框架回归，但不能宣称为双盲质量基准。

## 质量检查

- `id` 唯一，JSONL 每行可解析。
- required/bonus 内无重复、无交叉冲突。
- 技能可在 `raw_jd` 找到直接证据或明确别名证据。
- 不含真实个人隐私、密钥或未授权简历数据。
- baseline、模拟 LLM、真实 LLM 使用同一冻结数据版本时才可横向比较。