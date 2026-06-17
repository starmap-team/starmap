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
const MOCK_EVOLUTION = {
  items: [
    { skill_name: 'Python', trend: 'rising', confidence: 0.95, related_positions: ['后端开发', '数据分析师', 'AI工程师'] },
    { skill_name: 'Kubernetes', trend: 'rising', confidence: 0.91, related_positions: ['DevOps工程师', '云架构师'] },
    { skill_name: '大模型应用', trend: 'rising', confidence: 0.87, related_positions: ['NLP工程师', '算法工程师'] },
    { skill_name: 'Java', trend: 'stable', confidence: 0.93, related_positions: ['后端开发', '大数据开发'] },
    { skill_name: 'PHP', trend: 'declining', confidence: 0.82, related_positions: ['后端开发'] },
  ],
}

// 契约: 图谱子图
const MOCK_POSITION_SKILLS: Record<string, object> = {
  '数据分析师': {
    position: { position_id: 'pos_data_analyst', name: '数据分析师', industry: '互联网/IT', description: '...' },
    skills: [
      { skill_id: 'skill_python', name: 'Python', category: 'hard_skill', proficiency: '精通', confidence: 0.95, source_count: 15 },
      { skill_id: 'skill_sql', name: 'SQL', category: 'hard_skill', proficiency: '精通', confidence: 0.93, source_count: 18 },
      { skill_id: 'skill_excel', name: 'Excel', category: 'hard_skill', proficiency: '熟悉', confidence: 0.90, source_count: 10 },
      { skill_id: 'skill_stats', name: '统计学', category: 'hard_skill', proficiency: '熟悉', confidence: 0.88, source_count: 12 },
      { skill_id: 'skill_pandas', name: 'Pandas', category: 'hard_skill', proficiency: '熟悉', confidence: 0.87, source_count: 8 },
      { skill_id: 'skill_viz', name: '数据可视化', category: 'hard_skill', proficiency: '了解', confidence: 0.85, source_count: 7 },
    ],
    edges: [
      { source_id: 'skill_python', target_id: 'pos_data_analyst', type: 'REQUIRED_FOR', properties: { weight: 0.9 } },
      { source_id: 'skill_sql', target_id: 'pos_data_analyst', type: 'REQUIRED_FOR', properties: { weight: 0.85 } },
    ],
  },
  '前端开发工程师': {
    position: { position_id: 'pos_frontend', name: '前端开发工程师', industry: '互联网/IT', description: '...' },
    skills: [
      { skill_id: 'skill_js', name: 'JavaScript', category: 'hard_skill', proficiency: '精通', confidence: 0.96, source_count: 20 },
      { skill_id: 'skill_vue', name: 'Vue.js', category: 'hard_skill', proficiency: '精通', confidence: 0.94, source_count: 16 },
      { skill_id: 'skill_css', name: 'CSS', category: 'hard_skill', proficiency: '熟悉', confidence: 0.92, source_count: 14 },
      { skill_id: 'skill_ts', name: 'TypeScript', category: 'hard_skill', proficiency: '熟悉', confidence: 0.90, source_count: 11 },
      { skill_id: 'skill_node', name: 'Node.js', category: 'hard_skill', proficiency: '了解', confidence: 0.82, source_count: 8 },
      { skill_id: 'skill_webpack', name: 'Webpack', category: 'tool', proficiency: '了解', confidence: 0.80, source_count: 6 },
    ],
    edges: [],
  },
  '后端开发工程师': {
    position: { position_id: 'pos_backend', name: '后端开发工程师', industry: '互联网/IT', description: '...' },
    skills: [
      { skill_id: 'skill_java', name: 'Java', category: 'hard_skill', proficiency: '精通', confidence: 0.97, source_count: 22 },
      { skill_id: 'skill_spring', name: 'Spring Boot', category: 'hard_skill', proficiency: '精通', confidence: 0.93, source_count: 17 },
      { skill_id: 'skill_mysql', name: 'MySQL', category: 'hard_skill', proficiency: '熟悉', confidence: 0.91, source_count: 15 },
      { skill_id: 'skill_redis', name: 'Redis', category: 'hard_skill', proficiency: '熟悉', confidence: 0.88, source_count: 12 },
      { skill_id: 'skill_docker', name: 'Docker', category: 'tool', proficiency: '了解', confidence: 0.85, source_count: 10 },
      { skill_id: 'skill_msa', name: '微服务', category: 'hard_skill', proficiency: '了解', confidence: 0.83, source_count: 9 },
    ],
    edges: [],
  },
  '算法工程师': {
    position: { position_id: 'pos_algorithm', name: '算法工程师', industry: '互联网/IT', description: '...' },
    skills: [
      { skill_id: 'skill_py', name: 'Python', category: 'hard_skill', proficiency: '精通', confidence: 0.98, source_count: 20 },
      { skill_id: 'skill_ml', name: '机器学习', category: 'hard_skill', proficiency: '精通', confidence: 0.95, source_count: 18 },
      { skill_id: 'skill_dl', name: '深度学习', category: 'hard_skill', proficiency: '熟悉', confidence: 0.90, source_count: 14 },
      { skill_id: 'skill_torch', name: 'PyTorch', category: 'hard_skill', proficiency: '熟悉', confidence: 0.88, source_count: 10 },
      { skill_id: 'skill_math', name: '数学基础', category: 'hard_skill', proficiency: '精通', confidence: 0.92, source_count: 12 },
      { skill_id: 'skill_dp', name: '数据处理', category: 'hard_skill', proficiency: '熟悉', confidence: 0.85, source_count: 8 },
    ],
    edges: [],
  },
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
  http.get('/api/v1/graph/query', ({ request }) => {
    const url = new URL(request.url)
    const cypher = url.searchParams.get('cypher') ?? ''
    // 忽略具体 cypher，返回固定全景数据
    if (cypher) void 0
    return HttpResponse.json({
      nodes: [
        { id: 'pos-algo', labels: ['Position'], properties: { name: '算法工程师', category: 'AI' } },
        { id: 'pos-data', labels: ['Position'], properties: { name: '数据分析师', category: '数据' } },
        { id: 'pos-fe', labels: ['Position'], properties: { name: '前端开发工程师', category: '前端' } },
        { id: 'pos-be', labels: ['Position'], properties: { name: '后端开发工程师', category: '后端' } },
        { id: 'skill-py', labels: ['Skill'], properties: { name: 'Python', category: 'hard_skill' } },
        { id: 'skill-ml', labels: ['Skill'], properties: { name: '机器学习', category: 'hard_skill' } },
        { id: 'skill-sql', labels: ['Skill'], properties: { name: 'SQL', category: 'hard_skill' } },
        { id: 'skill-js', labels: ['Skill'], properties: { name: 'JavaScript', category: 'hard_skill' } },
        { id: 'skill-java', labels: ['Skill'], properties: { name: 'Java', category: 'hard_skill' } },
      ],
      edges: [
        { source_id: 'skill-py', target_id: 'pos-algo', type: 'REQUIRED_FOR', properties: { weight: 0.95 } },
        { source_id: 'skill-ml', target_id: 'pos-algo', type: 'REQUIRED_FOR', properties: { weight: 0.9 } },
        { source_id: 'skill-py', target_id: 'pos-data', type: 'REQUIRED_FOR', properties: { weight: 0.85 } },
        { source_id: 'skill-sql', target_id: 'pos-data', type: 'REQUIRED_FOR', properties: { weight: 0.8 } },
        { source_id: 'skill-js', target_id: 'pos-fe', type: 'REQUIRED_FOR', properties: { weight: 0.9 } },
        { source_id: 'skill-java', target_id: 'pos-be', type: 'REQUIRED_FOR', properties: { weight: 0.9 } },
      ],
    })
  }),

  // GET /graph/position/{position_id}/skills — 岗位技能子图（双层雷达数据源）
  http.get('/api/v1/graph/position/:positionId/skills', ({ params }) => {
    const { positionId } = params
    // 按名称匹配（positionId 格式为 pos_xxx 或直接用名称）
    const match = MOCK_POSITION_SKILLS[positionId as string]
      ?? Object.values(MOCK_POSITION_SKILLS).find(
        v => (v as any).position?.name === positionId || (v as any).position?.position_id === positionId
      )
    return HttpResponse.json(match ?? {
      position: { position_id: positionId, name: positionId, industry: '互联网/IT', description: '' },
      skills: [
        { skill_id: 'skill_0', name: 'Python', category: 'hard_skill', proficiency: '熟悉', confidence: 0.85, source_count: 5 },
        { skill_id: 'skill_1', name: 'SQL', category: 'hard_skill', proficiency: '了解', confidence: 0.80, source_count: 4 },
      ],
      edges: [],
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
