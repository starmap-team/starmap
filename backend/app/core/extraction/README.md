# 信息抽取核心

`backend/app/core/extraction/` 负责 JD/简历抽取、LLM provider 降级、prompt 版本、技能归一化和图写入适配。

## 模块

| 文件 | 职责 |
|---|---|
| `jd_extract.py` | JD 抽取编排和结构化解析 |
| `resume_extract.py` | 简历专用抽取流程 |
| `resume_eval.py` | 简历抽取评估辅助 |
| `llm_client.py` | MiMo、DeepSeek、星火和 Qwen 调用/降级 |
| `prompt.py` | prompt 注册、版本与 A/B 配置 |
| `normalize.py` | 别名和字符串归一化；向量能力为可选增强 |
| `graph_writer.py` | 将已验证结果写入图投影 |

## 不变量

- JD 与简历使用各自入口，不把简历文本伪装成 JD。
- LLM 输出必须经过结构解析、Schema 校验、归一化和可信度处理后才能持久化。
- 每个技能保留来源与 confidence/trust 信息。
- 开发环境不能依赖 ChromaDB 存在；无向量服务时必须正常降级。
- provider 调用通过共享客户端，不在业务流程中硬编码单一供应商。

## 验证

```bash
cd backend
poetry run pytest tests/unit/test_extraction.py tests/unit/test_normalize.py tests/unit/test_resume_service.py
```

涉及 Pydantic API 模型时，遵循根 `AGENTS.md` 的集中 Schema 与 JSON Schema 同步规则。