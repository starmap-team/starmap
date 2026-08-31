/**
 * Typed API client — wraps `request` with OpenAPI schema types.
 *
 * Usage:
 * import { api } from '@/api/client'
 * const data = await api.extractJd({ body: { jd_text: "..." } })
 *
 * New code should use `api.*` instead of `request.get/post` + manual casts.
 * All endpoints are now fully typed via OpenAPI schema types.
 */
import type { paths } from '@/api/schema'
import request from '@/api/request'

// ── Type helpers ──
type OpForPath<P extends keyof paths, M extends keyof paths[P]> = paths[P][M]

type RequestBody<
  P extends keyof paths,
  M extends keyof paths[P],
> = OpForPath<P, M> extends { requestBody?: { content: infer C } }
  ? C extends { 'application/json': infer B }
    ? B
    : never
  : never

type ResponseBody<
  P extends keyof paths,
  M extends keyof paths[P],
> = OpForPath<P, M> extends { responses: { 200: { content: infer C } } }
  ? C extends { 'application/json': infer B }
    ? B
    : unknown
  : unknown

// ── Generic typed request ──
// for template-literal URLs that openapi-typescript can't resolve statically.
async function typedGet<P extends string>(
  url: P,
  params?: Record<string, unknown>,
): Promise<P extends keyof paths ? 'get' extends keyof paths[P] ? ResponseBody<P, 'get'> : unknown : unknown> {
  return request.get(url, { params }) as ReturnType<typeof typedGet<P>>
}

async function typedPost<P extends string>(
  url: P,
  body?: P extends keyof paths ? 'post' extends keyof paths[P] ? RequestBody<P, 'post'> : unknown : unknown,
): Promise<P extends keyof paths ? 'post' extends keyof paths[P] ? ResponseBody<P, 'post'> : unknown : unknown> {
  return request.post(url, body) as ReturnType<typeof typedPost<P>>
}

// 模块A 新岗位发现类型（契约未收录 emerging_positions，按实际返回定义）
export interface DiscoverCandidate {
  position: string
  // 中文名兼容：后端暂未返回，前端展示时可选（name_cn || position_name_cn || position）
  name_cn?: string | null
  position_name_cn?: string | null
  industry_scenario: string | null
  emerging_skills: string[]
  emerging_ratio: number
  definition: {
    position_name: string
    required_skills: string[]
    emerging_required: string[]
    // A3 五要素（with_definitions=true 时后端补齐；默认 discover 不带参时不存在）
    industry_scenario?: string | null
    core_responsibilities?: string[]
    bonus_skills?: string[]
    summary?: string | null
  }
}

export interface DiscoverResponse {
  status: string
  emerging_skills: Array<{
    skill: string
    z_score: number
    level: string
    sources: number
    positions: string[]
  }>
  count: number
  skills_analyzed: number
  emerging_positions: DiscoverCandidate[]
  message?: string
}

// ── Convenience methods for most-used endpoints ──
export const api = {
 // Health
  health: () => typedGet('/health'),

 // Extract
  extractJd: (body: RequestBody<'/extract/jd', 'post'>) =>
    typedPost('/extract/jd', body),
  extractResume: (body: RequestBody<'/extract/resume', 'post'>) =>
    typedPost('/extract/resume', body),

 // Positions
  listPositions: (params?: Record<string, unknown>) =>
    typedGet('/positions', params),
  getPositionDetail: (positionId: string) =>
    typedGet(`/positions/${positionId}`),
  // A3 五要素：admin 登录态下带 with_definitions=true，由后端 LLM 补齐
  // 行业场景/核心职责/加分技能/岗位简述（fail-soft，单岗位失败不阻断）
  discoverPositions: (withDefinitions = true) =>
    request.post<DiscoverResponse>('/positions/discover', undefined, {
      params: { with_definitions: withDefinitions },
    }),

 // Match — typed with OpenAPI schema; stores that pass varying shapes
 // should normalize before calling, or use typedPost directly.
  runMatch: (body: RequestBody<'/match/position', 'post'>) =>
    typedPost('/match/position', body),

 // Evolution
  getEvolutionTrends: (params?: Record<string, unknown>) =>
    typedGet('/evolution/trends', params),
  getEvolutionPaths: (positionId: string) =>
    typedGet(`/evolution/paths/${positionId}`),

 // Quality
  getQualityDashboard: () => typedGet('/quality/dashboard'),

 // Graph
  getGraphOverview: () => typedGet('/graph/overview'),

 // Pipeline
  getPipelineStatus: (runId: string) =>
    typedGet(`/pipeline/runs/${runId}`),
} as const

// Re-export the raw request for gradual migration
export { request }
