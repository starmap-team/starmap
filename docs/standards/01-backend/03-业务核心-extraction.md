# Extraction 核心规范

## 范围

`core/extraction/` 分别处理 JD 与简历抽取，共享 LLM fallback、prompt、归一化和可信度校验；持久化和 API 编排由服务/路由完成。

## 规则

- JD 和简历入口使用各自 Schema 与 prompt。
- LLM 输出只在成功解析并通过结构校验后进入领域逻辑。
- 归一化先使用规范别名/字符串规则，向量匹配是可选能力。
- 每个技能保存 confidence/trust、来源和证据。
- provider 顺序、超时和重试集中在 `llm_client.py`。
- Golden truth 不得进入被评估 prompt 或输入。
- 图写入基于已验证结果，并遵循 PG 事实源/Neo4j 投影边界。

## 变更检查

Prompt、归一化或信任规则变化需要运行 baseline；API 输出变化需要同步 OpenAPI、Pydantic/JSON Schema 和前端类型。
