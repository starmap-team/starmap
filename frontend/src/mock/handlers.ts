/**
 * MSW Browser-side initialization (MSW v2).
 * Dev environment intercepts fetch requests and returns mock data.
 * Controlled by VITE_USE_MSW env var:
 *   - true or unset: Enable MSW mock (default)
 *   - false: Disable MSW, use real backend API
 */
import { http, HttpResponse } from 'msw'

export const handlers = [
  // Health check
  http.get('/api/v1/health', () =>
    HttpResponse.json({ status: 'ok', version: '1.0.0', env: 'development' }),
  ),

  // Positions list
  http.get('/api/v1/positions', () =>
    HttpResponse.json({
      items: [
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
      ],
      total: 1,
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
]