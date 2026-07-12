# 业务核心 - Extraction 规范

## 1. 模块概述

Extraction（信息抽取）模块是 StarMap 的核心业务层之一，负责从 JD（职位描述）和简历中提取结构化技能信息，并将结果写入 Neo4j 图数据库。该模块位于 `backend/app/core/extraction/`，包含 6 个核心文件，共约 3298 行代码。

**核心目标**：
- 从非结构化的 JD 文本和简历中提取结构化的技能、工具、证书等信息
- 通过 LLM 多供应商降级策略确保高可用性
- 技能标准化（别名映射、向量相似度、来源数验证）
- 反幻觉检查（信任度评分）
- 将抽取结果写入 Neo4j 图数据库

**在系统中的位置**：位于 `backend/app/core/extraction/`，被 `services/` 层调用，依赖 `models/` 层和外部 LLM 服务。

---

## 2. 文件清单

| 文件路径 | 行数 | 职责 | 主要导出 |
|---------|------|------|---------|
| `backend/app/core/extraction/__init__.py` | 91 | 公共 API 聚合，向后兼容导入 | `extract_from_jd`, `LLMClient`, `normalize_skill`, `batch_write_extractions` 等 |
| `backend/app/core/extraction/graph_writer.py` | 764 | Neo4j 图写入器：节点/关系创建、三元组写入、批量操作 | `GraphConfig`, `GraphNodeRef`, `GraphTriple`, `write_extraction_to_graph`, `batch_write_extractions` |
| `backend/app/core/extraction/jd_extract.py` | 418 | JD 抽取主流程：Prompt 填充 → LLM 调用 → JSON 解析 → 标准化 → 反幻觉 | `extract_from_jd`, `mask_pii`, `SkillCategory` |
| `backend/app/core/extraction/llm_client.py` | 390 | 多供应商 LLM 客户端：MiMo → DeepSeek → Xunfei → Ollama 自动降级 | `LLMClient`, `call_llm_with_fallback`, `call_xunfei_llm`, `LLMConnectionError`, `LLMResponseError`, `LLMTimeoutError` |
| `backend/app/core/extraction/normalize.py` | 618 | 技能标准化：别名映射、向量相似度、来源数验证、熟练度归一化 | `normalize_skill`, `batch_normalize_skills`, `SKILL_ALIAS`, `NormalizationResult` |
| `backend/app/core/extraction/prompt.py` | 668 | Prompt 模板管理：版本控制、A/B 测试支持 | `get_prompt`, `list_prompt_versions`, `JD_EXTRACTION_PROMPT`, `ANTI_HALLUCINATION_PROMPT` |
| `backend/app/core/extraction/resume_eval.py` | 349 | 简历抽取评估：F1/Precision/Recall 评估、黄金集对比 | `build_golden_set`, `evaluate_f1`, `run_resume_evaluation`, `GoldenSample`, `F1Metrics` |

---

## 3. 架构设计

### 3.1 模块内部结构

```
core/extraction/
├── __init__.py        ← 公共 API 聚合
├── graph_writer.py    ← Neo4j 图写入（7 节点类型 + 8 关系类型）
├── jd_extract.py      ← JD 抽取主流程
├── llm_client.py      ← 多供应商 LLM 客户端
├── normalize.py       ← 技能标准化
├── prompt.py          ← Prompt 模板管理
└── resume_eval.py     ← 简历抽取评估
```

### 3.2 数据流向

```
JD 文本 / 简历文本
    │
    ▼
┌─────────────────────────┐
│ jd_extract.py             │
│ ├─ mask_pii()             │  ← PII 脱敏
│ ├─ get_prompt()           │  ← 获取 Prompt 模板
│ ├─ LLMClient.call()       │  ← LLM 调用
│ └─ parse_llm_json_response()│  ← JSON 解析
└─────────────────────────┘
    │
    ▼
┌─────────────────────────┐
│ normalize.py              │
│ ├─ 别名查找（精确匹配）     │
│ ├─ 向量相似度（模糊匹配）   │
│ └─ 来源数验证             │
└─────────────────────────┘
    │
    ▼
┌─────────────────────────┐
│ graph_writer.py           │
│ ├─ build_triples_from_extraction() │
│ └─ write_triples_to_graph()        │
└─────────────────────────┘
    │
    ▼
Neo4j 图数据库
```

### 3.3 Neo4j 节点与关系类型

**7 类节点**（Spec §2.1）：
- `Position` — 职位
- `Skill` — 技能
- `KnowledgeArea` — 知识领域
- `Tool` — 工具
- `Certificate` — 证书
- `LearningResource` — 学习资源
- `Industry` — 行业

**8 类关系**（Spec §2.2）：
- `REQUIRES` — Position → Skill（required: bool, weight: float）
- `PREREQUISITE` — Skill → Skill（strength: float）
- `EVOLVES_TO` — Position → Position（similarity: float, evidence_count）
- `USES` — Position/Skill → Tool
- `BELONGS_TO` — Position → Industry
- `CERTIFIES` — Certificate → Skill
- `RECOMMENDED_FOR` — LearningResource → Skill（rank: float）
- `APPLIES_TO` — KnowledgeArea → Industry

---

## 4. 接口规范

### 4.1 主要函数签名

```python
# jd_extract.py
async def extract_from_jd(
    jd_text: str,
    options: dict[str, Any] | None = None,
) -> list[SkillRecord]:
    """从 JD 文本中提取结构化技能信息。"""

# llm_client.py
async def call_llm_with_fallback(
    prompt: str,
    model: str | None = None,
    temperature: float = 0.7,
) -> dict[str, Any]:
    """多供应商 LLM 调用，自动降级。"""

class LLMClient:
    async def call(self, prompt: str, **kwargs) -> dict[str, Any]:
        ...

# normalize.py
class NormalizationResult:
    skill_name: str
    confidence: float
    sources: list[str]
    alias_matched: bool
    vector_matched: bool

async def normalize_skill(
    raw_skill: str,
    context: dict[str, Any] | None = None,
) -> NormalizationResult:
    """标准化单个技能名称。"""

async def batch_normalize_skills(
    raw_skills: list[str],
) -> list[NormalizationResult]:
    """批量标准化技能名称。"""

# graph_writer.py
async def write_extraction_to_graph(
    extraction_result: dict[str, Any],
    neo4j_driver: Any,
) -> dict[str, Any]:
    """将抽取结果写入 Neo4j。"""

async def batch_write_extractions(
    extractions: list[dict[str, Any]],
    neo4j_driver: Any,
) -> dict[str, Any]:
    """批量写入抽取结果。"""
```

### 4.2 LLM 降级链

```
MiMo (主用) → DeepSeek → Xunfei → Ollama (本地降级)
```

- 每个供应商最多重试 3 次
- 超时时间：60 秒（可配置）
- 降级条件：连接失败、超时、非 200 响应

---

## 5. 编码规范（本模块特有）

### 5.1 PII 脱敏

```python
# jd_extract.py
_PII_PATTERNS: list[re.Pattern] = [
    re.compile(r"1[3-9]\d{9}"),           # 手机号
    re.compile(r"\d{18}[\dXx]"),           # 身份证号
    re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),  # 邮箱
]
_NAME_PREFIX_PATTERN = re.compile(r"(?:姓名|名字|联系人|候选人|求职者|name|Name)[:\s：：]+([一-鿿]{2,4})")
```

### 5.2 技能别名映射

```python
# normalize.py
SKILL_ALIAS: dict[str, list[str]] = {
    "Python": ["python", "python3", "python 3", "py", ...],
    "JavaScript": ["javascript", "js", "ecmascript", ...],
    # ... 更多别名
}
```

### 5.3 Prompt 版本管理

```python
# prompt.py
JD_EXTRACTION_PROMPT_V1 = "..."
JD_EXTRACTION_PROMPT_V2 = "..."
ANTI_HALLUCINATION_PROMPT = "..."

def get_prompt(name: str, version: str | None = None, **kwargs) -> str:
    """获取指定名称和版本的 Prompt 模板。"""
```

### 5.4 反模式

| 反模式 | 说明 | 正确做法 |
|--------|------|---------|
| 直接调用单个 LLM 供应商 | 单点故障 | 使用 `call_llm_with_fallback` |
| 跳过 PII 脱敏 | 隐私泄露 | 调用 `mask_pii` |
| 跳过技能标准化 | 重复计数 | 调用 `normalize_skill` |
| 直接写 Neo4j | 绕过 graph_writer | 使用 `write_extraction_to_graph` |
| 硬编码 Prompt | 无法 A/B 测试 | 使用 `get_prompt` |

---

## 6. 测试规范

### 6.1 对应测试文件

| 被测模块 | 测试文件 | 行数 | 测试类型 |
|---------|---------|------|---------|
| `extraction/` 整体 | `tests/unit/test_extraction.py` | 126 | 单元测试 |
| `normalize.py` | `tests/unit/test_normalize.py` | 255 | 单元测试 |
| `normalize.py` (额外) | `tests/unit/test_normalize_extra.py` | 47 | 单元测试 |
| `llm_client.py` | `tests/unit/test_llm_client.py` | 47 | 单元测试 |
| `graph_writer.py` | `tests/unit/test_graph_writer_coverage.py` | 510 | 单元测试 |
| `graph_writer.py` (Stage3) | `tests/unit/test_graph_writer_stage3.py` | 187 | 单元测试 |
| `resume_eval.py` | `tests/unit/test_persist_extraction.py` | 152 | 单元测试 |
| `extraction` API | `tests/integration/test_extraction_api.py` | 140 | 集成测试 |

### 6.2 覆盖率要求

- `jd_extract.py`：抽取流程 >= 60%
- `llm_client.py`：降级逻辑 >= 60%
- `normalize.py`：别名映射、向量匹配 >= 60%
- `graph_writer.py`：节点/关系写入 >= 60%
- `prompt.py`：版本管理 >= 60%

### 6.3 Mock 策略

```python
# 测试 LLM 调用时 mock 供应商
@pytest.fixture
def mock_llm_response():
    return {"skills": [...]}

def test_extract_from_jd(mock_llm_response):
    # mock LLMClient.call()
    # 验证抽取结果格式正确

# 测试标准化时 mock 向量服务
def test_normalize_skill_with_alias():
    # 使用 SKILL_ALIAS 中的别名
    # 验证标准化结果
```

---

## 7. 变更管理

### 7.1 修改检查清单

修改 Extraction 模块时：

- [ ] 是否修改 LLM 调用逻辑？是 → 确认降级链正常工作
- [ ] 是否修改 Prompt 模板？是 → 更新版本号，评估 A/B 测试影响
- [ ] 是否新增技能别名？是 → 更新 `SKILL_ALIAS`
- [ ] 是否修改 Neo4j 节点/关系类型？是 → 同步更新 `graph_writer.py`
- [ ] 是否修改 PII 脱敏规则？是 → 评估隐私合规性
- [ ] 是否修改标准化逻辑？是 → 运行评估套件确认不降级

### 7.2 契约影响

| 变更 | 影响 |
|------|------|
| 修改 LLM 调用 | 影响所有抽取端点，需评估质量 |
| 修改 Prompt | 影响抽取质量，需 A/B 测试 |
| 新增别名 | 影响标准化结果，需验证 |
| 修改 Neo4j 结构 | 影响图查询，需同步更新 Cypher |
| 修改 PII 规则 | 影响隐私合规，需法务确认 |

### 7.3 迁移要求

- 修改 Prompt 时，必须更新版本号并保留旧版本
- 新增别名时，必须验证不会与现有别名冲突
- 修改 Neo4j 结构时，必须同步更新 `starmap-contracts/graph_cypher/` 中的 Cypher 查询
- 修改 LLM 调用时，必须评估对评估 baseline 的影响
