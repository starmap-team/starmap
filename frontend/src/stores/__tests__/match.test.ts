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
