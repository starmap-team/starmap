/**
 * MSW Mock — 前端独立开发数据源（规范4：Mock优先）
 * 所有接口路径严格对应 starmap-contracts/openapi.yaml
 * ⚠️ 部分接口 enrich 了额外字段用于前端展示，已在注释中标明
 */
import { http, HttpResponse } from 'msw'

// ═══════════════════════════════════════════
// Mock 数据
// ═══════════════════════════════════════════

const MOCK_POSITIONS = [
  '数据分析师', '算法工程师', 'NLP工程师', 'CV工程师',
  '大数据开发工程师', '云架构师', 'DevOps工程师', '安全工程师',
  '前端开发工程师', '后端开发工程师',
]

const MOCK_JD_LIST = Array.from({ length: 20 }, (_, i) => ({
  id: i + 1,
  source: ['boss', 'lagou', 'liepin'][i % 3],
  title: MOCK_POSITIONS[i % MOCK_POSITIONS.length],
  company: `${['字节跳动', '腾讯', '阿里', '百度', '华为'][i % 5]}科技`,
  content: `负责${MOCK_POSITIONS[i % MOCK_POSITIONS.length]}相关工作…`,
  city: ['北京', '上海', '深圳', '杭州', '成都'][i % 5],
  salary_min: (i % 5 + 1) * 10,
  salary_max: (i % 5 + 2) * 12,
  publish_date: `2026-06-${String(15 - i % 14).padStart(2, '0')}`,
}))

// 契约: ExtractionResult（简历抽取结果）
const MOCK_RESUME_EXTRACT = {
  position_name: '数据分析师',
  required_skills: [
    { skill: 'Python', category: 'hard_skill', proficiency: '熟悉' },
    { skill: 'Excel', category: 'hard_skill', proficiency: '精通' },
    { skill: 'SQL', category: 'hard_skill', proficiency: '了解' },
    { skill: '沟通能力', category: 'soft_skill', proficiency: '熟悉' },
  ],
  preferred_skills: [],
  experience_required: 2,
  education_required: '本科',
  responsibilities: [],
  confidence: 0.89,
  hallucination_score: 0.05,
  normalized_skills: [],
}

// enrich: 契约 MatchResult + 前端展示额外字段
const MOCK_MATCH_RESULT = {
  // ── 契约字段 ──
  match_score: 0.68,
  matched_skills: ['Python', 'Excel', 'SQL基础'],
  gap_skills: ['Pandas', '统计学', '数据可视化', 'Tableau', '机器学习'],
  recommendations: [
    '建议优先学习 Pandas 和统计学基础',
    '掌握数据可视化工具（Matplotlib / Seaborn）',
    '学有余力可补充 Tableau 和机器学习入门',
  ],
  // ── enrich: 前端展示额外字段（联调时从 recommendations 拆解）──
  target_position: '数据分析师',
  missing_required: ['Pandas', '统计学', '数据可视化'],
  missing_bonus: ['Tableau', '机器学习'],
  skill_gap_detail: [
    { skill: 'Pandas', importance: 'required', gap_level: '完全缺失', learning_path: 'Python基础 → NumPy → Pandas入门 → 数据处理实战' },
    { skill: '统计学', importance: 'required', gap_level: '完全缺失', learning_path: '概率论基础 → 描述统计 → 推断统计 → 假设检验' },
    { skill: '数据可视化', importance: 'required', gap_level: '部分掌握', learning_path: 'Matplotlib基础 → Seaborn → 交互式图表' },
    { skill: 'Tableau', importance: 'bonus', gap_level: '完全缺失', learning_path: 'Tableau入门 → 仪表盘设计' },
    { skill: '机器学习', importance: 'bonus', gap_level: '完全缺失', learning_path: '统计学 → Scikit-learn → 模型调参' },
  ],
  overall_assessment: '基础编程能力扎实，需补充数据分析核心工具和统计学方法',
  estimated_learning_time: '3-4个月（兼职学习）',
}

// 契约: QualityReport + AdminStats（合并为一个便捷接口）
// enrich: source_distribution / hallucination_trend / trust_distribution / audit_queue 为前端专属
const MOCK_QUALITY = {
  // ── 契约 QualityReport 字段 ──
  precision: 0.88,
  recall: 0.82,
  f1: 0.85,
  warning_level: 'yellow',
  details: [
    { dimension: 'skill_extraction', value: 0.88, threshold: 0.85, status: 'pass' },
    { dimension: 'hallucination', value: 0.06, threshold: 0.10, status: 'pass' },
    { dimension: 'audit_pass', value: 0.82, threshold: 0.80, status: 'pass' },
    { dimension: 'trust_avg', value: 0.785, threshold: 0.75, status: 'pass' },
  ],
  // ── 契约 AdminStats 字段 ──
  total_nodes: 347,
  total_edges: 1256,
  total_positions: 28,
  total_skills: 180,
  avg_confidence: 0.785,
  hallucination_rate: 0.06,
  pending_review: 12,
  // ── enrich: 前端展示额外字段 ──
  avg_trust_score: 78.5,
  high_trust_ratio: 0.73,
  weekly_new_nodes: 15,
  audit_pass_rate: 0.82,
  source_distribution: [
    { name: 'BOSS直聘', count: 180, trust: 0.75 },
    { name: '拉勾', count: 90, trust: 0.72 },
    { name: '猎聘', count: 55, trust: 0.70 },
    { name: 'ESCO', count: 22, trust: 0.92 },
  ],
  hallucination_trend: [
    { date: 'W1', rate: 0.12 }, { date: 'W2', rate: 0.10 },
    { date: 'W3', rate: 0.08 }, { date: 'W4', rate: 0.07 },
    { date: 'W5', rate: 0.06 }, { date: 'W6', rate: 0.06 },
  ],
  trust_distribution: [
    { range: '0-50', count: 5 }, { range: '50-60', count: 12 },
    { range: '60-70', count: 35 }, { range: '70-80', count: 68 },
    { range: '80-90', count: 42 }, { range: '90-100', count: 18 },
  ],
  audit_queue: [
    { id: 1, position: '算法工程师', skill: 'Transformers', trust: 62 },
    { id: 2, position: '数据分析师', skill: 'PySpark', trust: 55 },
    { id: 3, position: 'DevOps工程师', skill: 'Helm', trust: 71 },
  ],
}

// 契约: EvolutionTrend[]
// CII 时序曲线数据（9个季度，基准 100 = 2024-Q1）
const MOCK_EVOLUTION = {
  quarters: ['24-Q1', '24-Q2', '24-Q3', '24-Q4', '25-Q1', '25-Q2', '25-Q3', '25-Q4', '26-Q1'],
  items: [
    { skill_name: '大模型应用', trend: 'rising',  confidence: 0.87, points: [100, 118, 130, 148, 160, 175, 185, 192, 198], related_positions: ['NLP工程师', '算法工程师'] },
    { skill_name: 'Kubernetes',  trend: 'rising',  confidence: 0.91, points: [100, 108, 115, 125, 135, 142, 150, 158, 165], related_positions: ['DevOps工程师', '云架构师'] },
    { skill_name: 'Python',      trend: 'rising',  confidence: 0.95, points: [100, 105, 112, 118, 125, 132, 140, 150, 158], related_positions: ['后端开发', '数据分析师', 'AI工程师'] },
    { skill_name: 'Java',        trend: 'stable',  confidence: 0.93, points: [100, 102, 105, 108, 108, 110, 112, 112, 112], related_positions: ['后端开发', '大数据开发'] },
    { skill_name: 'PHP',         trend: 'declining', confidence: 0.82, points: [100, 95, 90, 88, 82, 78, 75, 73, 72], related_positions: ['后端开发'] },
  ],
}

// ═══════════════════════════════════════════
// 图谱数据（唯一数据源，两个接口共用）
// ═══════════════════════════════════════════
const MOCK_GRAPH = {
  nodes: [
    // ── Position 岗位（4）──
    { id: 'pos-algo', labels: ['Position'], properties: { name: '算法工程师', source_count: 18, trend: 'rising' } },
    { id: 'pos-data', labels: ['Position'], properties: { name: '数据分析师', source_count: 14, trend: 'rising' } },
    { id: 'pos-fe', labels: ['Position'], properties: { name: '前端开发工程师', source_count: 16, trend: 'stable' } },
    { id: 'pos-be', labels: ['Position'], properties: { name: '后端开发工程师', source_count: 20, trend: 'stable' } },
    // ── Skill 技能（9）──
    { id: 'skill-py', labels: ['Skill'], properties: { name: 'Python', proficiency: '精通', source_count: 22, trend: 'rising', knowledge_points: ['基础语法', '面向对象', '装饰器/生成器', '异步编程', 'NumPy / Pandas', 'Flask / FastAPI'] } },
    { id: 'skill-ml', labels: ['Skill'], properties: { name: '机器学习', proficiency: '精通', source_count: 18, trend: 'rising', knowledge_points: ['监督学习', '无监督学习', '特征工程', '模型评估', '集成方法', 'Scikit-learn'] } },
    { id: 'skill-dl', labels: ['Skill'], properties: { name: '深度学习', proficiency: '熟悉', source_count: 15, trend: 'rising', knowledge_points: ['神经网络基础', 'CNN', 'RNN/Transformer', 'PyTorch', '迁移学习'] } },
    { id: 'skill-sql', labels: ['Skill'], properties: { name: 'SQL', proficiency: '精通', source_count: 20, trend: 'stable', knowledge_points: ['增删改查', 'JOIN 多表查询', '索引优化', '窗口函数', '事务与锁'] } },
    { id: 'skill-stats', labels: ['Skill'], properties: { name: '统计学', proficiency: '熟悉', source_count: 12, trend: 'stable', knowledge_points: ['描述统计', '概率分布', '假设检验', '回归分析', '贝叶斯方法'] } },
    { id: 'skill-viz', labels: ['Skill'], properties: { name: '数据可视化', proficiency: '了解', source_count: 10, trend: 'rising', knowledge_points: ['Matplotlib', 'Seaborn', 'ECharts', '仪表盘设计'] } },
    { id: 'skill-js', labels: ['Skill'], properties: { name: 'JavaScript', proficiency: '精通', source_count: 24, trend: 'stable', knowledge_points: ['ES6+ 语法', '异步 Promise/async', 'DOM/BOM', '模块化', '性能优化'] } },
    { id: 'skill-ts', labels: ['Skill'], properties: { name: 'TypeScript', proficiency: '熟悉', source_count: 16, trend: 'rising', knowledge_points: ['类型系统', '泛型', '装饰器', '声明文件', '工程化配置'] } },
    { id: 'skill-java', labels: ['Skill'], properties: { name: 'Java', proficiency: '精通', source_count: 21, trend: 'stable', knowledge_points: ['面向对象', '集合框架', '并发编程', 'JVM调优', 'Spring Boot', 'MyBatis'] } },
    // ── Tool 工具（5）──
    { id: 'tool-docker', labels: ['Tool'], properties: { name: 'Docker', proficiency: '熟悉', source_count: 18, trend: 'stable' } },
    { id: 'tool-git', labels: ['Tool'], properties: { name: 'Git', proficiency: '精通', source_count: 26, trend: 'stable' } },
    { id: 'tool-k8s', labels: ['Tool'], properties: { name: 'Kubernetes', proficiency: '了解', source_count: 14, trend: 'rising' } },
    { id: 'tool-webpack', labels: ['Tool'], properties: { name: 'Webpack', proficiency: '熟悉', source_count: 10, trend: 'declining' } },
    { id: 'tool-vscode', labels: ['Tool'], properties: { name: 'VS Code', proficiency: '精通', source_count: 23, trend: 'stable' } },
    // ── KnowledgeArea 领域（5）──
    { id: 'ka-ai', labels: ['KnowledgeArea'], properties: { name: '人工智能', source_count: 22, trend: 'rising' } },
    { id: 'ka-data', labels: ['KnowledgeArea'], properties: { name: '数据科学', source_count: 16, trend: 'rising' } },
    { id: 'ka-fe', labels: ['KnowledgeArea'], properties: { name: '前端工程', source_count: 14, trend: 'stable' } },
    { id: 'ka-be', labels: ['KnowledgeArea'], properties: { name: '后端架构', source_count: 17, trend: 'stable' } },
    { id: 'ka-cloud', labels: ['KnowledgeArea'], properties: { name: '云计算', source_count: 19, trend: 'rising' } },
    // ── Certificate 证书（3）──
    { id: 'cert-aws', labels: ['Certificate'], properties: { name: 'AWS认证', source_count: 5, trend: 'rising' } },
    { id: 'cert-pmp', labels: ['Certificate'], properties: { name: 'PMP', source_count: 4, trend: 'stable' } },
    { id: 'cert-ruankao', labels: ['Certificate'], properties: { name: '软考高级', source_count: 3, trend: 'declining' } },
    // ── LearningResource 学习资源（4）──
    { id: 'lr-docs', labels: ['LearningResource'], properties: { name: '官方文档', source_count: 20, trend: 'stable' } },
    { id: 'lr-courses', labels: ['LearningResource'], properties: { name: '在线课程', source_count: 24, trend: 'rising' } },
    { id: 'lr-blogs', labels: ['LearningResource'], properties: { name: '技术博客', source_count: 18, trend: 'stable' } },
    { id: 'lr-oss', labels: ['LearningResource'], properties: { name: '开源项目', source_count: 16, trend: 'rising' } },
    // ── Industry 行业（4）──
    { id: 'ind-internet', labels: ['Industry'], properties: { name: '互联网', source_count: 28, trend: 'stable' } },
    { id: 'ind-fintech', labels: ['Industry'], properties: { name: '金融科技', source_count: 16, trend: 'rising' } },
    { id: 'ind-medical', labels: ['Industry'], properties: { name: '医疗健康', source_count: 8, trend: 'rising' } },
    { id: 'ind-smart', labels: ['Industry'], properties: { name: '智能制造', source_count: 10, trend: 'stable' } },
  ],
  edges: [
    // 技能 → 岗位（REQUIRED_FOR）
    { source_id: 'skill-py', target_id: 'pos-algo', type: 'REQUIRED_FOR', properties: { weight: 0.95 } },
    { source_id: 'skill-ml', target_id: 'pos-algo', type: 'REQUIRED_FOR', properties: { weight: 0.90 } },
    { source_id: 'skill-dl', target_id: 'pos-algo', type: 'REQUIRED_FOR', properties: { weight: 0.85 } },
    { source_id: 'skill-py', target_id: 'pos-data', type: 'REQUIRED_FOR', properties: { weight: 0.85 } },
    { source_id: 'skill-sql', target_id: 'pos-data', type: 'REQUIRED_FOR', properties: { weight: 0.88 } },
    { source_id: 'skill-stats', target_id: 'pos-data', type: 'REQUIRED_FOR', properties: { weight: 0.82 } },
    { source_id: 'skill-viz', target_id: 'pos-data', type: 'REQUIRED_FOR', properties: { weight: 0.70 } },
    { source_id: 'skill-js', target_id: 'pos-fe', type: 'REQUIRED_FOR', properties: { weight: 0.95 } },
    { source_id: 'skill-ts', target_id: 'pos-fe', type: 'REQUIRED_FOR', properties: { weight: 0.85 } },
    { source_id: 'skill-java', target_id: 'pos-be', type: 'REQUIRED_FOR', properties: { weight: 0.93 } },
    { source_id: 'skill-sql', target_id: 'pos-be', type: 'REQUIRED_FOR', properties: { weight: 0.72 } },
    // 技能 → 工具（USES）
    { source_id: 'skill-py', target_id: 'tool-docker', type: 'USES', properties: { weight: 0.70 } },
    { source_id: 'skill-js', target_id: 'tool-git', type: 'USES', properties: { weight: 0.85 } },
    { source_id: 'skill-java', target_id: 'tool-git', type: 'USES', properties: { weight: 0.82 } },
    { source_id: 'skill-py', target_id: 'tool-k8s', type: 'USES', properties: { weight: 0.55 } },
    { source_id: 'skill-js', target_id: 'tool-webpack', type: 'USES', properties: { weight: 0.88 } },
    { source_id: 'skill-js', target_id: 'tool-vscode', type: 'USES', properties: { weight: 0.78 } },
    // 岗位 → 知识领域（BELONGS_TO）
    { source_id: 'pos-algo', target_id: 'ka-ai', type: 'BELONGS_TO', properties: { weight: 0.95 } },
    { source_id: 'pos-data', target_id: 'ka-data', type: 'BELONGS_TO', properties: { weight: 0.90 } },
    { source_id: 'pos-fe', target_id: 'ka-fe', type: 'BELONGS_TO', properties: { weight: 0.92 } },
    { source_id: 'pos-be', target_id: 'ka-be', type: 'BELONGS_TO', properties: { weight: 0.93 } },
    { source_id: 'pos-be', target_id: 'ka-cloud', type: 'BELONGS_TO', properties: { weight: 0.72 } },
    // 知识领域 → 技能（CONTAINS）── 下钻第1跳
    { source_id: 'ka-ai', target_id: 'skill-py', type: 'CONTAINS', properties: { weight: 0.90 } },
    { source_id: 'ka-ai', target_id: 'skill-ml', type: 'CONTAINS', properties: { weight: 0.95 } },
    { source_id: 'ka-ai', target_id: 'skill-dl', type: 'CONTAINS', properties: { weight: 0.88 } },
    { source_id: 'ka-data', target_id: 'skill-py', type: 'CONTAINS', properties: { weight: 0.85 } },
    { source_id: 'ka-data', target_id: 'skill-sql', type: 'CONTAINS', properties: { weight: 0.90 } },
    { source_id: 'ka-data', target_id: 'skill-stats', type: 'CONTAINS', properties: { weight: 0.82 } },
    { source_id: 'ka-data', target_id: 'skill-viz', type: 'CONTAINS', properties: { weight: 0.75 } },
    { source_id: 'ka-fe', target_id: 'skill-js', type: 'CONTAINS', properties: { weight: 0.95 } },
    { source_id: 'ka-fe', target_id: 'skill-ts', type: 'CONTAINS', properties: { weight: 0.85 } },
    { source_id: 'ka-be', target_id: 'skill-java', type: 'CONTAINS', properties: { weight: 0.90 } },
    { source_id: 'ka-be', target_id: 'skill-sql', type: 'CONTAINS', properties: { weight: 0.75 } },
    { source_id: 'ka-cloud', target_id: 'tool-docker', type: 'CONTAINS', properties: { weight: 0.88 } },
    { source_id: 'ka-cloud', target_id: 'tool-k8s', type: 'CONTAINS', properties: { weight: 0.85 } },
    // 岗位 → 证书（REQUIRES_CERT）
    { source_id: 'pos-be', target_id: 'cert-aws', type: 'REQUIRES_CERT', properties: { weight: 0.40 } },
    { source_id: 'pos-data', target_id: 'cert-pmp', type: 'REQUIRES_CERT', properties: { weight: 0.35 } },
    { source_id: 'pos-fe', target_id: 'cert-ruankao', type: 'REQUIRES_CERT', properties: { weight: 0.25 } },
    // 学习资源 → 技能（RELATED_TO）
    { source_id: 'lr-docs', target_id: 'skill-py', type: 'RELATED_TO', properties: { weight: 0.85 } },
    { source_id: 'lr-docs', target_id: 'skill-js', type: 'RELATED_TO', properties: { weight: 0.88 } },
    { source_id: 'lr-courses', target_id: 'skill-ml', type: 'RELATED_TO', properties: { weight: 0.80 } },
    { source_id: 'lr-courses', target_id: 'skill-java', type: 'RELATED_TO', properties: { weight: 0.78 } },
    { source_id: 'lr-blogs', target_id: 'skill-js', type: 'RELATED_TO', properties: { weight: 0.82 } },
    { source_id: 'lr-blogs', target_id: 'skill-ts', type: 'RELATED_TO', properties: { weight: 0.75 } },
    { source_id: 'lr-oss', target_id: 'skill-py', type: 'RELATED_TO', properties: { weight: 0.72 } },
    { source_id: 'lr-oss', target_id: 'skill-java', type: 'RELATED_TO', properties: { weight: 0.70 } },
    // 岗位 → 行业（IN_INDUSTRY）
    { source_id: 'pos-algo', target_id: 'ind-internet', type: 'IN_INDUSTRY', properties: { weight: 0.90 } },
    { source_id: 'pos-data', target_id: 'ind-internet', type: 'IN_INDUSTRY', properties: { weight: 0.85 } },
    { source_id: 'pos-data', target_id: 'ind-fintech', type: 'IN_INDUSTRY', properties: { weight: 0.78 } },
    { source_id: 'pos-fe', target_id: 'ind-internet', type: 'IN_INDUSTRY', properties: { weight: 0.95 } },
    { source_id: 'pos-be', target_id: 'ind-internet', type: 'IN_INDUSTRY', properties: { weight: 0.92 } },
    { source_id: 'pos-be', target_id: 'ind-fintech', type: 'IN_INDUSTRY', properties: { weight: 0.70 } },
  ],
}

// 管理后台（⚠️ 契约暂未覆盖，前端开发用，需后续补充到 openapi.yaml）
const MOCK_SOURCES = [
  { id: 1, name: 'BOSS直聘', authority_score: 0.7, source_type: 'aggregator' },
  { id: 2, name: '拉勾', authority_score: 0.7, source_type: 'aggregator' },
  { id: 3, name: '猎聘', authority_score: 0.7, source_type: 'aggregator' },
  { id: 4, name: 'ESCO', authority_score: 0.9, source_type: 'official' },
]

const MOCK_AUDIT = [
  { id: 1, type: 'skill', name: 'AI Agent开发', trust: 58, status: 'pending' },
  { id: 2, type: 'position', name: '大模型应用工程师', trust: 64, status: 'pending' },
  { id: 3, type: 'skill', name: 'Spring AI', trust: 72, status: 'pending' },
  { id: 4, type: 'skill', name: 'RAG', trust: 45, status: 'pending' },
]

// ═══════════════════════════════════════════
// Handlers（按契约 tag 分组）
// ═══════════════════════════════════════════

export const handlers = [
  // ────────── 系统 ──────────
  http.get('/api/v1/health', () =>
    HttpResponse.json({ status: 'ok', version: '1.0.0', env: 'development' }),
  ),

  // ────────── 信息抽取 ──────────
  // POST /extract/resume — 简历技能抽取
  http.post('/api/v1/extract/resume', () =>
    HttpResponse.json(MOCK_RESUME_EXTRACT),
  ),

  // ────────── 岗位管理 ──────────
  // GET /positions — 岗位列表（含搜索）
  http.get('/api/v1/positions', ({ request }) => {
    const url = new URL(request.url)
    const search = (url.searchParams.get('search') ?? '').toLowerCase()
    const filtered = search
      ? MOCK_POSITIONS.filter(p => p.toLowerCase().includes(search))
      : MOCK_POSITIONS
    const items = filtered.map(name => ({
      position_id: `pos_${name}`,
      name,
      industry: '互联网/IT',
      description: `${name}岗位描述`,
      skills_required: [],
    }))
    return HttpResponse.json({ items, total: items.length, page: 1, page_size: 20 })
  }),

  // ────────── 图谱查询 ──────────
  // GET /graph/query — 全景图谱
  http.get('/api/v1/graph/query', () =>
    HttpResponse.json(MOCK_GRAPH),
  ),

  // GET /graph/position/{position_id}/skills — 从 MOCK_GRAPH 动态推导（唯一数据源）
  http.get('/api/v1/graph/position/:positionId/skills', ({ params }) => {
    const { positionId } = params
    const name = positionId as string

    // 找岗位节点
    const posNode = MOCK_GRAPH.nodes.find(n =>
      n.labels.includes('Position') && n.properties.name === name,
    )
    if (!posNode) {
      return HttpResponse.json({ position: null, skills: [], edges: [] }, { status: 404 })
    }

    // 找所有指向该岗位的边（技能/工具/证书 → 岗位）
    const relatedEdges = MOCK_GRAPH.edges.filter(e =>
      e.target_id === posNode.id && ['REQUIRED_FOR', 'USES', 'REQUIRES_CERT'].includes(e.type),
    )

    // 拼技能列表
    const skills = relatedEdges.map(e => {
      const src = MOCK_GRAPH.nodes.find(n => n.id === e.source_id)
      return {
        skill_id: src?.id ?? e.source_id,
        name: src?.properties.name ?? e.source_id,
        category: src?.labels[0] === 'Tool' ? 'tool' : 'hard_skill',
        proficiency: (src?.properties as any)?.proficiency ?? '了解',
        confidence: e.properties.weight ?? 0.8,
        source_count: (src?.properties as any)?.source_count ?? 0,
      }
    })

    return HttpResponse.json({
      position: {
        position_id: posNode.id,
        name: posNode.properties.name,
        industry: '互联网/IT',
        description: '',
      },
      skills,
      edges: relatedEdges,
    })
  }),

  // ────────── 匹配诊断 ──────────
  // POST /match/position — 人岗匹配
  http.post('/api/v1/match/position', async ({ request }) => {
    const body = await request.json() as any
    const enriched = { ...MOCK_MATCH_RESULT, target_position: body?.target_position ?? '数据分析师' }
    return HttpResponse.json(enriched)
  }),

  // ────────── 演化分析 ──────────
  // GET /evolution/trends — 演化趋势
  http.get('/api/v1/evolution/trends', () =>
    HttpResponse.json(MOCK_EVOLUTION),
  ),

  // ────────── 质量监控 ──────────
  // GET /quality/report — 质量报告（enrich: 合并 stats + 前端展示字段）
  http.get('/api/v1/quality/report', () =>
    HttpResponse.json(MOCK_QUALITY),
  ),

  // ────────── 系统统计 ──────────
  // GET /admin/stats — 系统统计（由 /quality/report 合并返回，此处仅保留独立调用兼容）
  http.get('/api/v1/admin/stats', () => {
    const { total_nodes, total_edges, total_positions, total_skills, avg_confidence, hallucination_rate, pending_review } = MOCK_QUALITY
    return HttpResponse.json({ total_nodes, total_edges, total_positions, total_skills, avg_confidence, hallucination_rate, pending_review })
  }),

  // ────────── 管理后台（⚠️ 契约暂未覆盖，需补充）──────────
  http.get('/api/v1/admin/sources', () =>
    HttpResponse.json({ items: MOCK_SOURCES }),
  ),
  http.get('/api/v1/admin/audit-queue', () =>
    HttpResponse.json({ items: MOCK_AUDIT }),
  ),
  http.post('/api/v1/admin/audit/:id/approve', () =>
    HttpResponse.json({ ok: true }),
  ),
  http.post('/api/v1/admin/audit/:id/reject', () =>
    HttpResponse.json({ ok: true }),
  ),
  http.post('/api/v1/admin/reset-demo', () =>
    HttpResponse.json({ ok: true }),
  ),

  // ────────── JD 列表（契约暂未单独定义，使用 /positions 代替）──────────
  http.get('/api/v1/jd/list', () =>
    HttpResponse.json({ items: MOCK_JD_LIST, total: MOCK_JD_LIST.length }),
  ),
]
