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
// ponytail: constrain P to `keyof paths` when available, fall back to string
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
