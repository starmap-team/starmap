/**
 * MSW Browser-side initialization (MSW v2).
 * Dev environment intercepts fetch requests and returns mock data.
 * Controlled by VITE_USE_MSW env var:
 *   - true or unset: Enable MSW mock (default)
 *   - false: Disable MSW, use real backend API
 */
import { http, HttpResponse } from 'msw'

// Mock data for positions
const MOCK_POSITIONS = [
  {
    position_id: 'pos-1',
    name: '前端开发工程师',
    industry: '互联网',
    description: '负责Web前端架构设计与开发',
    skills_required: [
      { skill_id: 'sk-1', name: 'Vue.js', category: 'hard_skill', confidence: 0.95, source_count: 10 },
      { skill_id: 'sk-2', name: 'TypeScript', category: 'hard_skill', confidence: 0.9, source_count: 8 },
    ],
    discovered_at: '2026-06-27T09:00:00Z',
  },
  {
    position_id: 'pos-2',
    name: '后端开发工程师',
    industry: '互联网',
    description: '负责后端服务架构设计与开发',
    skills_required: [
      { skill_id: 'sk-3', name: 'Python', category: 'hard_skill', confidence: 0.95, source_count: 15 },
      { skill_id: 'sk-4', name: 'FastAPI', category: 'hard_skill', confidence: 0.9, source_count: 8 },
    ],
    discovered_at: '2026-06-27T09:00:00Z',
  },
  {
    position_id: 'pos-3',
    name: '数据分析师',
    industry: '数据',
    description: '负责数据分析和可视化',
    skills_required: [],
    discovered_at: '2026-06-27T09:00:00Z',
  },
  {
    position_id: 'pos-4',
    name: 'AI工程师',
    industry: '人工智能',
    description: '负责AI模型开发与部署',
    skills_required: [],
    discovered_at: '2026-06-27T09:00:00Z',
  },
  {
    position_id: 'pos-5',
    name: 'DevOps工程师',
    industry: '云计算',
    description: '负责CI/CD和基础设施',
    skills_required: [],
    discovered_at: '2026-06-27T09:00:00Z',
  },
]

// Mock resume parse result
const MOCK_RESUME_RESULT = {
  position_name: '软件开发工程师',
  required_skills: [
    { skill: 'Python', category: 'hard_skill', proficiency: '精通' },
    { skill: 'JavaScript', category: 'hard_skill', proficiency: '熟悉' },
    { skill: 'SQL', category: 'hard_skill', proficiency: '熟悉' },
    { skill: 'Docker', category: 'tool', proficiency: '了解' },
    { skill: 'Git', category: 'tool', proficiency: '熟悉' },
  ],
  preferred_skills: [
    { skill: 'Kubernetes', category: 'tool', proficiency: '了解' },
    { skill: 'Redis', category: 'hard_skill', proficiency: '了解' },
  ],
  experience_required: 3,
  education_required: '本科',
  confidence: 0.85,
  hallucination_score: null,
  normalized_skills: [],
}

// Mock match result
const MOCK_MATCH_RESULT = {
  match_id: 'match-001',
  target_position: '后端开发工程师',
  match_score: 0.65,
  matched_skills: ['Python', 'Docker'],
  gap_skills: ['FastAPI', 'PostgreSQL', 'Redis', 'System Design', 'Kubernetes', 'Microservices'],
  recommendations: [
    '优先补齐 FastAPI：Python → REST API → FastAPI',
    '优先补齐 PostgreSQL：SQL → PostgreSQL',
    '优先补齐 Redis：Python → Redis',
  ],
  missing_required: ['FastAPI', 'PostgreSQL', 'Redis', 'System Design'],
  missing_bonus: ['Kubernetes', 'Microservices'],
  skill_gap_detail: [
    { skill: 'FastAPI', importance: 'required', gap_level: '完全缺失', learning_path: ['Python', 'REST API', 'FastAPI'] },
    { skill: 'PostgreSQL', importance: 'required', gap_level: '完全缺失', learning_path: ['SQL', 'PostgreSQL'] },
    { skill: 'Redis', importance: 'required', gap_level: '完全缺失', learning_path: ['Python', 'Redis'] },
    { skill: 'System Design', importance: 'required', gap_level: '完全缺失', learning_path: ['REST API', 'PostgreSQL', 'System Design'] },
    { skill: 'Kubernetes', importance: 'bonus', gap_level: '完全缺失', learning_path: ['Docker', 'Linux', 'Kubernetes'] },
    { skill: 'Microservices', importance: 'bonus', gap_level: '完全缺失', learning_path: ['REST API', 'Docker', 'Microservices'] },
  ],
  overall_assessment: '基础能力可支撑转岗或进阶，但仍需优先补齐关键缺口。',
  estimated_learning_time: '8-9周（兼职学习）',
}

export const handlers = [
  // Health check
  http.get('/api/v1/health', () =>
    HttpResponse.json({ status: 'ok', version: '1.0.0', env: 'development' }),
  ),

  // Positions list
  http.get('/api/v1/positions', () =>
    HttpResponse.json({
      items: MOCK_POSITIONS,
      total: MOCK_POSITIONS.length,
      page: 1,
      page_size: 100,
    }),
  ),

  // Graph overview
  http.get('/api/v1/graph/overview', () =>
    HttpResponse.json({
      domains: [
        { id: 'ka-1', name: '前端开发', position_count: 25, skill_count: 43, color: '#409EFF' },
        { id: 'ka-2', name: '后端开发', position_count: 42, skill_count: 79, color: '#67C23A' },
      ],
      connections: [
        { source_id: 'ka-1', target_id: 'ka-2', type: 'SHARES_POSITION', properties: { weight: 0.5 } },
      ],
      total_positions: 396,
      total_skills: 610,
    }),
  ),

  // Graph panorama
  http.get('/api/v1/graph/panorama', () =>
    HttpResponse.json({
      nodes: [
        { id: 'ka-1', labels: ['KnowledgeArea'], properties: { name: '前端开发', position_count: 25, skill_count: 43, color: '#409EFF' } },
      ],
      edges: [],
    }),
  ),

  // Quality report
  http.get('/api/v1/quality/report', () =>
    HttpResponse.json({
      report: { precision: 1.0, recall: 1.0, f1: 1.0, warning_level: 'green', details: [] },
      total_nodes: 302,
      total_edges: 360,
      total_positions: 396,
      total_skills: 610,
    }),
  ),

  // Evolution trends
  http.get('/api/v1/evolution/trends', () =>
    HttpResponse.json({
      items: [
        { skill_name: 'Docker', trend: 'rising', confidence: 1.0, points: [202, 194, 186, 178], related_positions: [] },
      ],
    }),
  ),

  // Admin sources
  http.get('/api/v1/admin/sources', () =>
    HttpResponse.json({
      items: [
        { id: 1, name: 'BOSS', authority_score: 0.7, source_type: 'aggregator' },
      ],
    }),
  ),

  // Admin review queue
  http.get('/api/v1/admin/review-queue', () =>
    HttpResponse.json({
      items: [
        { id: 1, type: 'skill', name: 'AI Agent Dev', trust: 58, status: 'pending' },
      ],
    }),
  ),

  // Resume upload (match diagnosis step 0)
  http.post('/api/v1/resume/upload', () =>
    HttpResponse.json(MOCK_RESUME_RESULT),
  ),

  // Position skills (match diagnosis step 1)
  http.get('/api/v1/graph/position/:name/skills', () =>
    HttpResponse.json({
      position: { position_id: 'pos-2', name: '后端开发工程师', industry: '互联网', description: '' },
      skills: [
        { skill_id: 'sk-1', name: 'Python', category: 'hard_skill', proficiency: '精通', confidence: 0.95, source_count: 10 },
        { skill_id: 'sk-2', name: 'FastAPI', category: 'hard_skill', proficiency: '熟悉', confidence: 0.9, source_count: 8 },
        { skill_id: 'sk-3', name: 'PostgreSQL', category: 'hard_skill', proficiency: '熟悉', confidence: 0.9, source_count: 7 },
        { skill_id: 'sk-4', name: 'Redis', category: 'hard_skill', proficiency: '熟悉', confidence: 0.85, source_count: 6 },
        { skill_id: 'sk-5', name: 'Docker', category: 'tool', proficiency: '了解', confidence: 0.8, source_count: 5 },
        { skill_id: 'sk-6', name: 'System Design', category: 'hard_skill', proficiency: '了解', confidence: 0.75, source_count: 4 },
        { skill_id: 'sk-7', name: 'Kubernetes', category: 'tool', proficiency: '了解', confidence: 0.7, source_count: 3 },
        { skill_id: 'sk-8', name: 'Microservices', category: 'hard_skill', proficiency: '了解', confidence: 0.7, source_count: 3 },
      ],
      edges: [],
    }),
  ),

  // Match diagnosis (match diagnosis step 2)
  http.post('/api/v1/match/position', () =>
    HttpResponse.json(MOCK_MATCH_RESULT),
  ),
]

// Export mock data for use in axios interceptor (bypasses MSW service worker for FormData)
export { MOCK_RESUME_RESULT }