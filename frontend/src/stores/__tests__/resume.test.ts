import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useResumeStore, type ResumeParseResult } from '../resume'

vi.mock('@/api/request', () => ({
  default: {
    post: vi.fn(),
    get: vi.fn(),
  },
}))

describe('useResumeStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('should have correct initial state', () => {
    const store = useResumeStore()
    expect(store.result).toBeNull()
    expect(store.loading).toBe(false)
  })

  it('should set loading state during parse', () => {
    const store = useResumeStore()
    store.loading = true
    expect(store.loading).toBe(true)
  })

  it('should store parse result', () => {
    const store = useResumeStore()
    const mockResult: ResumeParseResult = {
      position_name: '后端开发工程师',
      required_skills: [
        { skill: 'Python', category: 'hard_skill', proficiency: '精通' },
      ],
      preferred_skills: [],
      experience_required: 3,
      education_required: '本科',
      confidence: 0.9,
      hallucination_score: 0.05,
      normalized_skills: [
        { original: 'Python', normalized: 'Python', method: 'exact', confidence: 1.0 },
      ],
    }
    store.result = mockResult
    expect(store.result.position_name).toBe('后端开发工程师')
    expect(store.result.required_skills).toHaveLength(1)
  })

  it('should clear result', () => {
    const store = useResumeStore()
    store.result = { position_name: 'test' } as any
    store.result = null
    expect(store.result).toBeNull()
  })
})
