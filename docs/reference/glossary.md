# StarMap 术语表

> 状态：活文档

| 术语 | 英文/标识 | 含义 |
|---|---|---|
| 岗位描述 | Job Description, JD | 招聘岗位的文本输入，是技能抽取的主要证据来源 |
| 岗位 | Position | 业务岗位实体，在 PG 中有权威记录，在 Neo4j 中有图投影 |
| 技能 | Skill | 可归一化、可追溯、带可信度的能力实体 |
| 知识领域 | Knowledge Area | 对岗位或技能进行上层分类的本体概念 |
| 抽取 | Extraction | 从 JD 或简历中生成结构化技能和岗位属性的过程 |
| 归一化 | Normalization | 将别名、大小写和相近表达映射到规范技能名称 |
| 可信度 | Trust score | 来源、时间、稳定性或人工证据共同形成的可靠性评分 |
| 反幻觉 | Hallucination defense | 阻止无证据技能进入权威数据的验证与审核机制 |
| 演化快照 | Evolution snapshot | 某一时间窗口内岗位技能状态的持久化记录 |
| 演化变更 | Evolution changelog | 两个窗口间技能新增、移除、晋级或降级等差异 |
| 新兴技能 | Emerging skill | 时间序列显著上升且满足来源/频率条件的技能信号 |
| 匹配诊断 | Match diagnosis | 简历技能与目标岗位要求的覆盖、差距和建议分析 |
| 学习路径 | Learning path | 针对技能差距生成的有序学习计划 |
| 流水线运行 | Pipeline run | 可持久化、可取消、可重试的 ETL 执行实例 |
| 数据源权威度 | Source authority | 数据源基于质量、稳定性和业务规则的权重 |
| 审核状态 | Review status | draft、pending_review、approved、rejected 等发布治理状态 |
| 契约优先 | Contract first | API 变化先修改 OpenAPI，再同步后端 Schema 和前端类型 |
| 事实源 | Source of truth, SSOT | 对某类信息具有最终解释权的数据或文件 |
| 图投影 | Graph projection | 从 PG 权威数据派生到 Neo4j 的可重建图表示 |
| Outbox | GraphWriteOutbox | 记录 PG 事实等待或已完成图投影的持久化队列记录 |
| 运行时校验 | Runtime validation | 前端使用 JSON Schema 对请求或响应结构执行的校验 |
| Golden Set | Golden dataset | 人工标注、用于重复评估模型或规则质量的数据集 |
| Baseline | Baseline evaluation | 不依赖真实 LLM 的可重复参考评估 |
| SSE | Server-Sent Events | 服务端向浏览器单向推送流水线/看板事件的连接 |

## 已移除或历史术语

| 术语 | 当前说明 |
|---|---|
| MSW | 前端仓库已不使用它作为当前 API 数据源；测试替身使用 Vitest/Playwright 的局部能力 |
| Chroma 开发服务 | 已从开发 Compose 移除；生产 Compose 仍可提供 ChromaDB |
| 五阶段/六阶段 ETL | 历史实现描述；当前调度入口以代码中的 `StageName` 和 `STAGE_EXECUTORS` 为准 |
| `request.improved.ts` | 历史文件名，当前 API 基础客户端是 `frontend/src/api/request.ts` |

新增术语前先确认它不是现有概念的别名；同一业务概念必须在 API、Schema、前端和文档中使用一致名称。