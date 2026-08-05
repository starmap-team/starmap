import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useMatchStore, type MatchResult } from '../match'

// Mock the request module
vi.mock('@/api/request', () => ({
  default: {
    post: vi.fn(),
    get: vi.fn(),
  },
}))

describe('useMatchStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('should have correct initial state', () => {
    const store = useMatchStore()
    expect(store.result).toBeNull()
    expect(store.loading).toBe(false)
  })

  it('should set loading state during match', () => {
    const store = useMatchStore()
    store.loading = true
    expect(store.loading).toBe(true)
  })

  it('should store match result', () => {
    const store = useMatchStore()
    const mockResult: MatchResult = {
      match_score: 0.85,
      matched_skills: ['Python', 'FastAPI'],
      gap_skills: ['Docker'],
      recommendations: ['学习 Docker 基础'],
      target_position: '后端开发工程师',
    }
    store.result = mockResult
    expect(store.result.match_score).toBe(0.85)
    expect(store.result.matched_skills).toContain('Python')
  })

  it('should clear result', () => {
    const store = useMatchStore()
    store.result = {
      match_score: 0.5,
      matched_skills: [],
      gap_skills: [],
      recommendations: [],
    }
    store.result = null
    expect(store.result).toBeNull()
  })
})

// PLAN-014 批次5: 契约接入回归 — runMatch 后端响应在契约不一致时仍可用 (DEV 仅 warn)
describe('useMatchStore.runMatch with contract validation', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('accepts a well-formed MatchResponse and stores it', async () => {
    const { default: request } = await import('@/api/request')
    const validResponse = {
      match_id: 'm-001',
      match_score: 0.85,
      matched_skills: ['Python'],
      gap_skills: ['Kubernetes'],
      recommendations: ['学 Docker'],
      target_position: '后端工程师',
      note: 'OK',
    }
    vi.mocked(request.post).mockResolvedValue(validResponse as MatchResult)
    const store = useMatchStore()
    await store.runMatch('后端工程师', ['Python'])
    expect(store.result?.match_id).toBe('m-001')
    expect(store.result?.match_score).toBe(0.85)
    expect(store.loading).toBe(false)
  })

  it('still stores drifted-shape response (contract warn only, not block)', async () => {
    const { default: request } = await import('@/api/request')
    // 故意漏掉 match_score — 契约会 warn 但前端不抛
    const drifted = {
      match_id: 'm-002',
      matched_skills: [],
      gap_skills: [],
      recommendations: [],
    }
    vi.mocked(request.post).mockResolvedValue(drifted as unknown as MatchResult)
    const store = useMatchStore()
    await store.runMatch('X', ['Python'])
    expect(store.result).not.toBeNull()
    expect(store.result?.match_id).toBe('m-002')
    // 契约字典点: 必填字段都不应阻断响应使用
    expect(store.loading).toBe(false)
  })
})
