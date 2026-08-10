/**
 * 闭环演示示例 JD — 供 LoopStepInput 快速填充真实岗位 JD 文本。
 * 从组件内联抽离，便于维护与复用。
 */
export interface ExampleJD {
  title: string
  position: string
  text: string
}

export const EXAMPLE_JDS: ExampleJD[] = [
  {
    title: '前端工程师',
    position: '前端工程师',
    text: `岗位职责：
1. 负责公司核心产品的前端开发，使用 Vue3 + TypeScript 技术栈
2. 参与前端架构设计，持续优化前端工程化体系
3. 与后端、设计团队紧密协作，推动产品快速迭代
4. 负责前端性能优化，提升用户体验

任职要求：
1. 计算机相关专业本科及以上学历，3年以上前端开发经验
2. 精通 Vue3、TypeScript、HTML5、CSS3
3. 熟悉 React、Webpack、Vite 等前端工具链
4. 了解 Node.js、Git、CI/CD 流程
5. 具备良好的沟通能力和团队协作精神
6. 有大型 SPA 应用开发经验者优先`,
  },
  {
    title: '数据分析师',
    position: '数据分析师',
    text: `岗位职责：
1. 负责公司数据分析体系建设，搭建数据指标体系
2. 通过数据挖掘和分析，为业务决策提供数据支持
3. 设计和维护数据看板，监控核心业务指标
4. 进行 A/B 测试分析，驱动产品优化

任职要求：
1. 统计学、数学、计算机相关专业本科及以上学历
2. 精通 SQL、Python，熟悉 Pandas、NumPy 等数据分析工具
3. 熟悉 Tableau、Power BI 等数据可视化工具
4. 了解机器学习基本算法（回归、分类、聚类）
5. 具备良好的逻辑思维和数据敏感度
6. 有大数据处理经验（Spark、Hive）者优先`,
  },
  {
    title: 'AI 工程师',
    position: 'AI 工程师',
    text: `岗位职责：
1. 负责大语言模型（LLM）应用的开发与优化
2. 设计和实现 RAG 系统、Prompt Engineering 流程
3. 构建 AI Agent 框架，实现多步骤任务编排
4. 进行模型评估与效果优化，建立质量评估体系

任职要求：
1. 计算机科学、人工智能相关专业硕士及以上学历
2. 精通 Python，熟悉 PyTorch/TensorFlow
3. 熟悉 LangChain、LlamaIndex 等 LLM 应用框架
4. 了解向量数据库（Milvus、Pinecone）、RAG 技术
5. 掌握 NLP 基础技术（Transformer、BERT、GPT）
6. 有 LLM 应用开发或 Agent 系统经验者优先`,
  },
]
