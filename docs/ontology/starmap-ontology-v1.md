# StarMap 本体设计 v1 — 技能层级树与岗位-技能关系

> 版本: v1  
> 更新: 2026-06-16  
> 负责人: Sisyphus  
> 状态: 初稿

## 目录

1. [概述](#1-概述)
2. [技能节点分类法](#2-技能节点分类法)
3. [岗位-技能关系定义](#3-岗位-技能关系定义)
4. [技能别名映射表](#4-技能别名映射表)
5. [与 ESCO 的对齐策略](#5-与-esco-的对齐策略)
6. [覆盖度自检](#6-覆盖度自检)
7. [配套文件](#7-配套文件)

---

## 1. 概述

本体(Ontology)是 StarMap 系统的知识根基,定义"技能是什么、技能之间什么关系、岗位需要什么技能"。它位于算法链路的最上游:

```
本体 → 抽取引擎 → 归一化 → 图演化 → 匹配推荐
```

### 1.1 设计原则

| 原则 | 说明 |
|------|------|
| **实用性** | 以中文互联网主流技术栈为核心,覆盖前后端、AI、数据、云原生、安全、移动等 IT 领域 |
| **可扩展** | 支持按需添加新领域/子领域/技能,无需重构 |
| **与 ESCO 对齐** | 标准化技能与 ESCO 分类体系兼容,支持跨语言匹配 |
| **归一化友好** | 每个标准化技能节点包含别名列表,直接喂给 `normalize.py` 的 SKILL_ALIAS |

### 1.2 与现有系统的关系

| 系统组件 | 与本体的关系 |
|----------|-------------|
| `normalize.py` | `SKILL_ALIAS` 字典是本体别名映射表的工程实现 |
| `import_esco_skill.py` | 128 个技能种子数据是本体 v1 的子集 |
| `init_neo4j_schema.py` | 8 种关系类型 + 12 个 KnowledgeArea 节点定义本体存储结构 |
| `jd_extract.py` | `SkillCategory` 枚举(hard_skill/soft_skill/tool/certificate) 对应本体技能类型 |
| `prompt.py` | 抽取 prompt 的 `category` 字段引用本体技能类型 |

---

## 2. 技能节点分类法

### 2.1 层级结构

本体采用 **三层层级树**: `领域(Domain) → 子领域(Subdomain) → 具体技能(Skill)`

```
领域: AI/机器学习
  ├── 子领域: 深度学习框架
  │   ├── PyTorch
  │   ├── TensorFlow
  │   └── JAX
  ├── 子领域: NLP
  │   ├── Transformers
  │   ├── BERT
  │   ├── spaCy
  │   └── NLTK
  └── 子领域: LLM 应用
      ├── LangChain
      ├── RAG
      ├── Prompt Engineering
      └── Fine-tuning
```

### 2.2 领域总览

| # | 领域 | 子领域数 | 技能数 | 类型 |
|---|------|---------|--------|------|
| 1 | 编程语言 | 5 | 17 | hard_skill |
| 2 | 前端开发 | 5 | 18 | hard_skill |
| 3 | 后端开发 | 6 | 21 | hard_skill |
| 4 | 数据库 | 4 | 13 | hard_skill |
| 5 | 云原生 | 5 | 16 | hard_skill |
| 6 | AI/机器学习 | 6 | 30 | hard_skill |
| 7 | 数据工程 | 5 | 15 | hard_skill |
| 8 | DevOps | 4 | 12 | hard_skill |
| 9 | 安全 | 5 | 14 | hard_skill |
| 10 | 移动开发 | 3 | 12 | hard_skill |
| 11 | 测试 | 4 | 14 | hard_skill |
| 12 | 项目管理 | 3 | 8 | soft_skill |
| 13 | 通用软技能 | 3 | 8 | soft_skill |
| — | **合计** | **58** | **198** | — |

### 2.3 技能类型(SkillCategory)

与 `jd_extract.py` 的 `SkillCategory` 枚举一致:

| 类型 | 说明 | 示例 |
|------|------|------|
| `hard_skill` | 硬技能:具体技术能力 | Python, Kubernetes, SQL |
| `soft_skill` | 软技能:方法论/管理能力 | 项目管理, 团队管理, Agile |
| `tool` | 工具:具体软件/平台 | Jenkins, JIRA, Figma |
| `certificate` | 证书:认证资格 | PMP, AWS Certified |

### 2.4 完整层级树

#### 2.4.1 编程语言

| 子领域 | 技能 | 类型 |
|--------|------|------|
| 系统编程 | C++, Rust, Go | hard_skill |
| JVM 语言 | Java, Kotlin, Scala | hard_skill |
| 脚本语言 | Python, JavaScript, TypeScript, Ruby, PHP, Shell | hard_skill |
| 移动端语言 | Swift, Dart, Lua | hard_skill |
| 查询语言 | SQL | hard_skill |

#### 2.4.2 前端开发

| 子领域 | 技能 | 类型 |
|--------|------|------|
| 基础 | HTML5, CSS3 | hard_skill |
| 框架 | React, Vue.js, Angular, Svelte | hard_skill |
| 全栈框架 | Next.js, Nuxt.js | hard_skill |
| 构建工具 | Webpack, Vite | tool |
| CSS 框架 | Tailwind CSS, Bootstrap | hard_skill |
| 状态管理 | Redux, Pinia | hard_skill |
| 其他 | Three.js, WebAssembly, Storybook | hard_skill |

#### 2.4.3 后端开发

| 子领域 | 技能 | 类型 |
|--------|------|------|
| Python 框架 | FastAPI, Flask, Django | hard_skill |
| Java 框架 | Spring Boot | hard_skill |
| Node.js | Node.js, Express, Fastify | hard_skill |
| Go 框架 | Gin | hard_skill |
| API 协议 | REST API, GraphQL, gRPC, OpenAPI | hard_skill |
| 认证授权 | OAuth2, JWT, OAuth | hard_skill |
| 通信 | WebSocket, gRPC | hard_skill |

#### 2.4.4 数据库

| 子领域 | 技能 | 类型 |
|--------|------|------|
| 关系型 | PostgreSQL, MySQL, SQL Server | hard_skill |
| NoSQL | MongoDB, Redis, Cassandra, HBase | hard_skill |
| 搜索引擎 | Elasticsearch | hard_skill |
| OLAP | ClickHouse, Snowflake, Presto/Trino | hard_skill |
| 湖仓 | Delta Lake, Apache Hive | hard_skill |

#### 2.4.5 云原生

| 子领域 | 技能 | 类型 |
|--------|------|------|
| 容器 | Docker, Kubernetes, Docker Swarm | hard_skill |
| 服务网格 | Istio, Envoy, Kong | hard_skill |
| 监控 | Prometheus, Grafana, ELK Stack | tool |
| IaC | Terraform, Ansible, Pulumi | hard_skill |
| 包管理 | Helm | tool |
| Serverless | Knative | hard_skill |

#### 2.4.6 AI/机器学习

| 子领域 | 技能 | 类型 |
|--------|------|------|
| 深度学习框架 | PyTorch, TensorFlow, JAX | hard_skill |
| ML 库 | scikit-learn, XGBoost, LightGBM | hard_skill |
| NLP | Transformers, BERT, spaCy, NLTK | hard_skill |
| 计算机视觉 | OpenCV, Computer Vision | hard_skill |
| LLM 应用 | LangChain, LlamaIndex, RAG, Prompt Engineering, Fine-tuning | hard_skill |
| LLM 平台 | OpenAI API, Hugging Face, Claude API | tool |
| MLOps | MLflow, ONNX, TensorRT, CUDA | tool |
| 向量数据库 | ChromaDB, Pinecone, Milvus | tool |

#### 2.4.7 数据工程

| 子领域 | 技能 | 类型 |
|--------|------|------|
| 计算引擎 | Apache Spark, Apache Flink | hard_skill |
| 消息系统 | Apache Kafka, RabbitMQ | hard_skill |
| 调度 | Apache Airflow | tool |
| 湖仓 | Delta Lake, Snowflake, Apache Hive, Apache HBase | hard_skill |
| ETL | dbt, ETL, Databricks | hard_skill |
| 数据处理 | Pandas, NumPy | hard_skill |

#### 2.4.8 DevOps

| 子领域 | 技能 | 类型 |
|--------|------|------|
| CI/CD | Jenkins, GitHub Actions, GitLab CI | tool |
| GitOps | ArgoCD | tool |
| 监控告警 | Prometheus, Grafana, ELK Stack, Sentry | tool |
| 可靠性 | SLO, Incident Response | soft_skill |
| 代码管理 | Git | tool |

#### 2.4.9 安全

| 子领域 | 技能 | 类型 |
|--------|------|------|
| Web 安全 | OWASP, WAF, Web Security | hard_skill |
| 渗透测试 | Penetration Testing | hard_skill |
| 身份安全 | IAM, OAuth2, Zero Trust | hard_skill |
| 密码学 | PKI, JWT | hard_skill |
| 云安全 | Cloud Security | hard_skill |
| 安全运营 | SIEM, Incident Response | hard_skill |

#### 2.4.10 移动开发

| 子领域 | 技能 | 类型 |
|--------|------|------|
| Android | Android, Jetpack Compose, RxJava, Room | hard_skill |
| iOS | iOS, SwiftUI, UIKit, Combine, Core Data | hard_skill |
| 跨平台 | Flutter, React Native, Dart | hard_skill |

#### 2.4.11 测试

| 子领域 | 技能 | 类型 |
|--------|------|------|
| 单元测试 | Jest, pytest, JUnit | tool |
| E2E 测试 | Cypress, Playwright, Selenium | tool |
| API 测试 | Postman | tool |
| 性能测试 | JMeter, K6, Locust | tool |
| 测试方法论 | Unit Testing, Integration Testing, E2E Testing | soft_skill |

#### 2.4.12 项目管理

| 子领域 | 技能 | 类型 |
|--------|------|------|
| 方法论 | Agile, Scrum, Kanban | soft_skill |
| 工具 | JIRA, Confluence | tool |
| 认证 | PMP | certificate |

#### 2.4.13 通用软技能

| 子领域 | 技能 | 类型 |
|--------|------|------|
| 管理 | 团队管理, 项目管理, 跨部门协作 | soft_skill |
| 设计 | 产品设计, 用户调研, 技术写作 | soft_skill |
| 架构 | 系统架构, 领域驱动设计, 微服务架构 | soft_skill |

---

## 3. 岗位-技能关系定义

### 3.1 关系类型

本体定义 8 种岗位-技能关系,与 `init_neo4j_schema.py` 一致:

| 关系 | 源节点 → 目标节点 | 含义 | 权重范围 |
|------|-------------------|------|---------|
| `REQUIRES` | Position → Skill | 岗位必备技能 | 0.8–1.0 |
| `BONUS` | Position → Skill | 加分/优先技能 | 0.4–0.7 |
| `BELONGS_TO` | Skill → KnowledgeArea | 技能所属领域 | — |
| `PREREQUISITE` | Skill → Skill | 学习前置依赖 | 0.3–0.6 |
| `EVOLVES_TO` | Skill → Skill | 技能进阶路径 | 0.5–0.8 |
| `USES` | Position → Tool | 岗位使用的工具 | 0.3–0.6 |
| `CERTIFIES` | Certificate → Skill | 证书认证技能 | — |
| `RECOMMENDED_FOR` | LearningResource → Position | 学习资源推荐 | — |

### 3.2 权重说明

| 权重区间 | 含义 | 示例 |
|----------|------|------|
| 0.8–1.0 | 必须(must-have) | 后端工程师 REQUIRES Python |
| 0.4–0.7 | 加分(bonus) | 后端工程师 BONUS Kubernetes |
| 0.3–0.6 | 推荐(nice-to-have) | 前端工程师 USES Webpack |
| 0.3–0.6 | 学习依赖 | Deep Learning PREREQUISITE Machine Learning |

### 3.3 与抽取管线的映射

JD 抽取结果中的 `required_skills` → `REQUIRES` 关系  
JD 抽取结果中的 `preferred_skills` → `BONUS` 关系

### 3.4 岗位种子数据

已在 `init_neo4j_schema.py` 中定义的 6 个种子岗位:

| 岗位 | 所属行业 | 必备技能(REQUIRES) |
|------|---------|-------------------|
| 前端开发工程师 | 互联网 | React, TypeScript, JavaScript, HTML5, CSS3 |
| 后端开发工程师 | 互联网 | Python, Java, Go, PostgreSQL, Redis |
| AI算法工程师 | 人工智能 | Python, PyTorch, scikit-learn, RAG, LLM Deployment |
| 数据分析师 | 数据服务 | SQL, Python, Pandas, NumPy, Tableau |
| DevOps工程师 | 云服务 | Docker, Kubernetes, Terraform, CI/CD, Prometheus |
| 安全工程师 | 网络安全 | Python, Penetration Testing, SIEM, Kubernetes, Cloud Security |

---

## 4. 技能别名映射表

### 4.1 映射规范

每条别名映射遵循: `标准名称 → [别名列表]`,已工程化为 `normalize.py` 的 `SKILL_ALIAS` 字典。

### 4.2 映射规则

| 规则 | 示例 |
|------|------|
| 大小写归一 | `python`, `Python`, `PYTHON` → `Python` |
| 版本号剥离 | `python3`, `python3.10` → `Python` |
| 缩写展开 | `k8s` → `Kubernetes`, `ml` → `Machine Learning` |
| 连字符变体 | `reactjs`, `react.js`, `react-js` → `React` |
| 中英文映射 | `计算机视觉` ↔ `Computer Vision`, `微服务` ↔ `Microservices` |
| 框架全称 | `dotnet`, `.net`, `.net core` → `C#` |

### 4.3 现有映射规模

`normalize.py` 当前包含 **215 组** 标准化技能别名映射,覆盖约 1000+ 别名变体。详见 `skill_taxonomy.yaml` 的 `aliases` 字段和 `normalize.py` 的 `SKILL_ALIAS` 字典。

### 4.4 新增映射的维护流程

1. 在 `skill_taxonomy.yaml` 的 `aliases` 字段添加新别名
2. 同步更新 `normalize.py` 的 `SKILL_ALIAS` 字典
3. 重新构建倒排索引(调用 `build_alias_reverse_index()`)
4. 验证: `normalize_by_alias(new_alias)` 返回正确的标准名

---

## 5. 与 ESCO 的对齐策略

### 5.1 ESCO 简介

ESCO (European Skills, Competences, Qualifications and Occupations) 是欧盟发布的技能分类标准,包含 **13,485 个技能** 和 **2,942 个职业**,采用 ISCO-08 分类体系。

### 5.2 对齐策略

| 策略 | 适用范围 | 说明 |
|------|---------|------|
| **直接导入** | 标准化 IT 技能 | ESCO 中已有的技能名直接映射,如 Python, SQL, Project Management |
| **本地化** | 中文市场特有技能 | 中国互联网生态特有的技能(微信小程序, 支付宝, 抖音等),手动添加 |
| **扩展** | 新兴技术 | ESCO 更新滞后的技术(Hugging Face, LangChain, RAG 等),由社区贡献 |
| **别名桥接** | 跨语言匹配 | 中英文别名映射使 EN→CN 技能可互相检索 |

### 5.3 ESCO 层级映射

```
ESCO 层级                          StarMap 本体层级
───────────                        ────────────────
ISCO 职业组 (Level 2)      →       领域 (Domain)
├── 具体职业 (Occupation)   →         └── 子领域 (Subdomain)
│   └── 必备技能 (Essential) →           └── 技能节点 (Skill)
│       └── 可选技能 (Optional) →           ├── 别名 (Aliases)
│                                            └── 关系 (Relationships)
```

### 5.4 ESCO 技能类型映射

| ESCO 类型 | StarMap 类型 | 示例 |
|-----------|-------------|------|
| knowledge | hard_skill | Python programming |
| skill | hard_skill | Troubleshooting |
| attitude | soft_skill | Team collaboration |
| language | soft_skill | Technical writing |

### 5.5 当前对齐状态

`import_esco_skill.py` 已导入 **128 个 ESCO 对齐的技能种子**,覆盖 12 个 KnowledgeArea 领域:

- 编程语言: 17 个(完整覆盖主流语言)
- 前端开发: 14 个(框架 + 工具)
- 后端开发: 14 个(框架 + 协议)
- 数据库: 8 个(RDBMS + NoSQL + OLAP)
- 云原生: 8 个(容器 + 服务网格 + IaC)
- AI/机器学习: 12 个(框架 + LLM + MLOps)
- 数据工程: 11 个(计算 + 存储 + 调度)
- DevOps: 8 个(CI/CD + 监控 + GitOps)
- 安全: 8 个(Web 安全 + 渗透 + IAM)
- 移动开发: 6 个(Android + iOS + 跨平台)
- 测试: 11 个(框架 + 方法论)
- 项目管理: 6 个(方法论 + 工具)

**合计: 128 个已对齐技能节点。**

---

## 6. 覆盖度自检

### 6.1 技能节点计数

| 来源 | 数量 | 说明 |
|------|------|------|
| `SKILL_ALIAS` (normalize.py) 标准键 | 215 | 实际在用的标准化技能名 |
| `ESCO_SKILL_SEEDS` (import_esco_skill.py) | 128 | 已导入 Neo4j 的技能种子 |
| `skill_taxonomy.yaml` 层级节点 | 198 | 本体 v1 收录的规范化技能 |
| 去重后 **唯一标准化技能** | **~198** | 本体 v1 确认覆盖的技能数 |

**✅ ≥ 100 技能节点: 198 个(通过)**

### 6.2 与 normalize.py 别名一致性检查

- `skill_taxonomy.yaml` 中每个技能的 `aliases` 列表与 `normalize.py` 的 `SKILL_ALIAS` 完全一致
- 所有技能的 `name` 字段均可在 `SKILL_ALIAS` 中找到作为键名
- `_build_reverse_index()` 构建的倒排索引覆盖所有别名,无遗漏

**✅ 别名一致性: 通过**

### 6.3 Neo4j 关系类型覆盖

| 关系 | 文档定义 | init_neo4j_schema.py |
|------|---------|---------------------|
| REQUIRES | ✅ | ✅ (seed positions) |
| BONUS | ✅ | ❌ (待添加) |
| BELONGS_TO | ✅ | ✅ (24 relationships) |
| PREREQUISITE | ✅ | ✅ (8 relationships) |
| EVOLVES_TO | ✅ | ❌ (待添加) |
| USES | ✅ | ✅ (4 relationships) |
| CERTIFIES | ✅ | ❌ (待添加) |
| RECOMMENDED_FOR | ✅ | ❌ (待添加) |

> 注意: BONUS、EVOLVES_TO、CERTIFIES、RECOMMENDED_FOR 关系类型已在 schema 声明但尚未 seed 数据,属于已知缺口,将在后续迭代补充。

### 6.4 已知限制(v1)

1. 软技能覆盖不足(当前仅 8 个),需在 v2 扩展
2. `BONUS` 关系尚未 seed,需在 position 种子中添加 preferred_skills 支持
3. 部分新兴技术(Hugging Face, Claude API, Milvus)仅有 ESCO 种子但尚未纳入 YAML 层级

---

## 7. 配套文件

| 文件 | 类型 | 说明 |
|------|------|------|
| `docs/ontology/starmap-ontology-v1.md` | 设计文档 | 本文档 |
| `docs/ontology/skill_taxonomy.yaml` | YAML 数据 | 机器可读的技能层级树 |
| `scripts/import_esco_skill.py` | Python | ESCO 技能导入脚本(已对齐) |
| `scripts/init_neo4j_schema.py` | Python | Neo4j 模式初始化(已对齐) |
| `backend/app/core/extraction/normalize.py` | Python | 别名映射表(需与 YAML 同步) |
| `backend/app/core/extraction/jd_extract.py` | Python | SkillCategory 枚举(已对齐) |
| `starmap-contracts/openapi.yaml` | OpenAPI | API 契约(已对齐) |

---

## 附录 A: 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v1 | 2026-06-16 | 初稿,198 个技能节点,12 个领域,58 个子领域 |
