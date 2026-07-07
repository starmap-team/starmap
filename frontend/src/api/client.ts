/**
 * Typed API client — wraps `request` with OpenAPI schema types.
 *
 * Usage:
 *   import { api } from '@/api/client'
 *   const data = await api.extractJd({ body: { jd_text: "..." } })
 *
 * New code should use `api.*` instead of `request.get/post` + `as any`.
 * Existing `as any` casts can be migrated incrementally.
 */
import type { paths } from '@/api/schema'
import request from '@/api/request'

// ── Type helpers ──
type PathsWithMethod<M extends keyof paths[keyof paths]> = {
  [P in keyof paths]: M extends keyof paths[P] ? P : never
}[keyof paths]

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
async function typedGet<P extends PathsWithMethod<'get'>>(
  url: P,
  params?: Record<string, unknown>,
): Promise<ResponseBody<P, 'get'>> {
  return request.get(url as string, { params }) as Promise<ResponseBody<P, 'get'>>
}

async function typedPost<P extends PathsWithMethod<'post'>>(
  url: P,
  body?: RequestBody<P, 'post'>,
): Promise<ResponseBody<P, 'post'>> {
  return request.post(url as string, body) as Promise<ResponseBody<P, 'post'>>
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

  // Match
  runMatch: (body: RequestBody<'/match/run', 'post'>) =>
    typedPost('/match/run', body),

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
